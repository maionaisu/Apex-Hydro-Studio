# ==============================================================================
# APEX NEXUS TIER-0: SPATIAL SEDIMENT & VEGETATION MAPPER
# ==============================================================================
import os
import gc
import logging
import traceback
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
import matplotlib
import matplotlib.pyplot as plt
from pyproj import Transformer

# Strictly enforce non-interactive backend to prevent Main Thread locking
matplotlib.use('Agg')
logger = logging.getLogger(__name__)

class SpatialSedimentEngine:
    """
    Tier-0 Engine for 2D spatial interpolation.
    Upgrades:
    - Filled Contours (S2/S3 Thesis Standard Plotting).
    - Shapely Ray-Casting Masking (Clipping Grid with Shapefiles).
    """
    @staticmethod
    def process_and_interpolate(df: pd.DataFrame, col_x: str, col_y: str, col_val: str, epsg: str, mode_type: str, apply_ks: bool = False, interp_method: str = "Delaunay", boundary_file: str = None, log_cb=None) -> tuple:
        
        def _log(msg):
            logger.info(msg)
            if log_cb: log_cb(msg)
            
        fig = None
        try:
            _log(f"[SEDIMENT] Memulai komputasi geometri & Kriging mode: {mode_type}")
            
            if df is None or df.empty:
                raise ValueError("DataFrame input kosong.")
                
            df_clean = df[[col_x, col_y, col_val]].copy()
            df_clean[col_x] = pd.to_numeric(df_clean[col_x], errors='coerce')
            df_clean[col_y] = pd.to_numeric(df_clean[col_y], errors='coerce')
            df_clean[col_val] = pd.to_numeric(df_clean[col_val], errors='coerce')
            df_clean = df_clean.dropna()
            
            # [CRITICAL FIX]: Singular Matrix Guard for Kriging
            df_clean = df_clean.groupby([col_x, col_y], as_index=False).mean()

            if len(df_clean) < 3:
                raise ValueError(f"Jumlah titik unik ({len(df_clean)}) < 3. Tidak dapat diinterpolasi.")
                
            vals = df_clean[col_val].to_numpy(dtype=np.float64)
            
            if mode_type == 'sediment' and apply_ks:
                mean_val = vals.mean()
                if mean_val > 100:
                    vals = (vals / 1000000.0) * 2.5
                elif mean_val < 0.01:
                    vals = vals * 2.5
                else:
                    vals = (vals / 1000.0) * 2.5 
                
            # EPSG Translation & UTM Auto-Detection
            max_x = df_clean[col_x].abs().max()
            max_y = df_clean[col_y].abs().max()
            
            if max_x > 180 or max_y > 90:
                ux = df_clean[col_x].to_numpy(dtype=np.float64)
                uy = df_clean[col_y].to_numpy(dtype=np.float64)
            else:
                _log(f"  ├ [TRANSFORM] WGS84 -> EPSG:{epsg} (UTM)...")
                tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
                ux, uy = tr.transform(df_clean[col_x].values, df_clean[col_y].values)
                ux = np.asarray(ux, dtype=np.float64)
                uy = np.asarray(uy, dtype=np.float64)
            
            # Base Grid Bounding Box (+2km buffer untuk aman sebelum di-clip)
            x_min, x_max = np.min(ux) - 2000, np.max(ux) + 2000
            y_min, y_max = np.min(uy) - 2000, np.max(uy) + 2000
            
            step = 50.0
            while ((x_max - x_min) / step) * ((y_max - y_min) / step) > 4000000:
                step += 25.0
                
            x_coords = np.arange(x_min, x_max, step)
            y_coords = np.arange(y_min, y_max, step)
            gx, gy = np.meshgrid(x_coords, y_coords)
            
            # Interpolasi Spasial
            if "Kriging" in interp_method:
                max_kriging_points = 2500
                if len(ux) > max_kriging_points:
                    _log(f"  ├ [OOM GUARD] Kriging Matrix Inversion disampel ke {max_kriging_points} titik.")
                    idx_sample = np.random.choice(len(ux), max_kriging_points, replace=False)
                    ux_k, uy_k, vals_k = ux[idx_sample], uy[idx_sample], vals[idx_sample]
                else:
                    ux_k, uy_k, vals_k = ux, uy, vals

                try:
                    from pykrige.ok import OrdinaryKriging
                    v_model = 'spherical'
                    if 'Exponential' in interp_method: v_model = 'exponential'
                    elif 'Gaussian' in interp_method: v_model = 'gaussian'
                    
                    _log(f"  ├ Mengeksekusi Ordinary Kriging ({v_model.capitalize()})...")
                    OK = OrdinaryKriging(
                        ux_k, uy_k, vals_k, variogram_model=v_model,
                        verbose=False, enable_plotting=False, exact_values=False
                    )
                    z_grid, ss = OK.execute('grid', x_coords, y_coords)
                    gz = z_grid.data if hasattr(z_grid, 'data') else z_grid
                    
                    if np.isnan(gz).any():
                        nan_mask = np.isnan(gz)
                        gz[nan_mask] = griddata(np.column_stack((ux_k, uy_k)), vals_k, (gx[nan_mask], gy[nan_mask]), method='nearest')
                        
                except Exception as k_err:
                    _log(f"  ├ [KRIGING ERROR] Gagal konvergensi ({k_err}). Mengalihkan ke Delaunay...")
                    gz = griddata(np.column_stack((ux, uy)), vals, (gx, gy), method='linear')
                    if np.isnan(gz).any():
                        nan_mask = np.isnan(gz)
                        gz[nan_mask] = griddata(np.column_stack((ux, uy)), vals, (gx[nan_mask], gy[nan_mask]), method='nearest')
            else:
                _log("  ├ Mengeksekusi Fast Delaunay Triangulation (Linear)...")
                gz = griddata(np.column_stack((ux, uy)), vals, (gx, gy), method='linear')
                if np.isnan(gz).any(): 
                    nan_mask = np.isnan(gz)
                    gz[nan_mask] = griddata(np.column_stack((ux, uy)), vals, (gx[nan_mask], gy[nan_mask]), method='nearest')

            # ==============================================================================
            # [ENTERPRISE FEATURE]: SPATIAL CLIPPING / MASKING WITH GEOPANDAS & SHAPELY
            # ==============================================================================
            gdf_bnd = None
            if boundary_file and os.path.exists(boundary_file):
                try:
                    import geopandas as gpd
                    from shapely.prepared import prep
                    from shapely.geometry import Point
                    
                    _log(f"  ├ [MASKING] Memotong grid menggunakan batas poligon: {os.path.basename(boundary_file)}")
                    gdf_bnd = gpd.read_file(boundary_file)
                    
                    if gdf_bnd.crs is None or gdf_bnd.crs.to_epsg() != int(epsg):
                        _log(f"  ├ [CRS SYNC] Menyesuaikan proyeksi Polygon ke EPSG:{epsg}...")
                        gdf_bnd = gdf_bnd.to_crs(epsg=int(epsg))
                        
                    # Menggabungkan seluruh poligon menjadi satu kesatuan (Unary Union)
                    polygon_union = gdf_bnd.geometry.unary_union
                    
                    # Optimalisasi Ray-Casting Point-in-Polygon (C++)
                    prepared_polygon = prep(polygon_union)
                    
                    _log("  ├ Mengeksekusi algoritma Ray-Casting untuk memfilter jutaan titik...")
                    # Flattening & vektorisasi (Dapat memakan waktu 2-10 detik tergantung resolusi)
                    pts = np.column_stack((gx.flatten(), gy.flatten()))
                    mask = np.array([prepared_polygon.contains(Point(x, y)) for x, y in pts])
                    
                    # Membuang (NaN-kan) nilai Z yang jatuh di luar lautan / AOI
                    gz_flat = gz.flatten()
                    gz_flat[~mask] = np.nan
                    gz = gz_flat.reshape(gz.shape)
                    _log("  ├ [MASKING SUCCESS] Pesisir/Daratan telah di-clipping secara geometris.")
                    
                except ImportError:
                    _log("  ├ [WARNING] Pustaka 'geopandas' atau 'shapely' tidak ditemukan. Masking dibatalkan.")
                except Exception as e:
                    _log(f"  ├ [WARNING] Gagal mengeksekusi masking poligon: {e}")

            # Export Logic
            out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))
            os.makedirs(out_dir, exist_ok=True)
            
            filename_prefix = {'sediment': "Sed_Rough", 'mangrove': "Mangrove_Fric", 'submerged': "Sub_Eco"}.get(mode_type, 'Spatial_Data')
            out_xyz = os.path.join(out_dir, f"{filename_prefix}.xyz")
            
            _log(f"  ├ Menulis matriks (XYZ) bersih -> {os.path.basename(out_xyz)}")
            df_export = pd.DataFrame({'X': gx.flatten(), 'Y': gy.flatten(), 'Z': gz.flatten()})
            df_export.dropna().to_csv(out_xyz, sep=' ', header=False, index=False, float_format='%.3f')
            del df_export; gc.collect()
            
            # ==============================================================================
            # [ENTERPRISE FEATURE]: FILLED CONTOURS (S2/S3 THESIS LEVEL AESTHETICS)
            # ==============================================================================
            _log("  ├ Merender Spasial Filled Contours HD...")
            p_path = os.path.join(out_dir, f"{mode_type}_contours.png")
            
            try:
                fig, ax = plt.subplots(figsize=(7, 6))
                fig.patch.set_facecolor('#0B0F19')
                ax.set_facecolor('#030712')
                
                cmap_choice, label_text, title_text = 'YlOrBr_r', 'Friction (ks)', 'Distribusi Sedimen Dasar Laut'
                if mode_type == 'mangrove':
                    cmap_choice, label_text, title_text = 'Greens', 'Densitas (n/m2)', 'Distribusi Vegetasi Mangrove'
                elif mode_type == 'submerged':
                    cmap_choice, label_text, title_text = 'GnBu', 'Densitas (n/m2)', 'Distribusi Submerged Vegetation'
                    
                # Menentukan interval garis kontur agar terlihat elegan
                valid_z = gz[~np.isnan(gz)]
                if len(valid_z) > 0:
                    levels = np.linspace(np.min(valid_z), np.max(valid_z), 15)
                    # 1. Gambar Area Kontur Berwarna
                    cf = ax.contourf(gx, gy, gz, levels=levels, cmap=cmap_choice, extend='both', alpha=0.9)
                    # 2. Gambar Garis Kontur Pemisah
                    ax.contour(gx, gy, gz, levels=levels, colors='black', linewidths=0.3, alpha=0.5)
                    
                    cb = plt.colorbar(cf, ax=ax, pad=0.02)
                    cb.set_label(label_text, color='w', fontweight='bold')
                    cb.ax.yaxis.set_tick_params(color='w')
                    plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color='w')
                
                # 3. Plot Land Boundary / Shapefile Overlay (Jika ada) untuk visual referensi daratan
                if gdf_bnd is not None:
                    # Gambar outline poligon dengan garis emas/kuning agar terlihat batasnya
                    gdf_bnd.boundary.plot(ax=ax, color='#F59E0B', linewidth=1.5, zorder=4)
                
                # 4. Plot Titik Survei
                ax.scatter(ux, uy, c='#EF4444', s=15, edgecolors='white', linewidths=0.5, label='Titik Survei', zorder=5)
                
                ax.set_title(title_text, color='w', fontweight='bold', pad=15, fontsize=14)
                ax.tick_params(colors='w')
                ax.grid(True, color='#1E293B', linestyle=':', alpha=0.7)
                
                # Tweak layout
                ax.set_xlabel("Easting (m)", color='w')
                ax.set_ylabel("Northing (m)", color='w')
                ax.legend(facecolor='#020617', edgecolor='#1E293B', labelcolor='w', loc='upper right')
                
                plt.tight_layout()
                plt.savefig(p_path, dpi=300) # Output resolusi sangat tinggi (300 DPI) untuk skripsi
                
            finally:
                if fig is not None:
                    fig.clf()
                    plt.close(fig)
                gc.collect()
            
            return p_path, out_xyz
            
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan komputasi spasial ({mode_type}): {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal memproses interpolasi spasial: {str(e)}") from e
