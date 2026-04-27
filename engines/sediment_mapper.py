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

# [CRITICAL GUARD]: Memaksa backend Non-Interactive agar UI tidak Freeze/Crash
matplotlib.use('Agg')
logger = logging.getLogger(__name__)

from core.state_manager import app_state

class SpatialSedimentEngine:
    """
    Tier-0 Engine for 2D spatial interpolation.
    Enterprise Features:
    - [ADAPTIVE TRIPLE-KRIGING]: Otomatis mencari kolom Cd, DBH, dan Densitas (N).
    - [BIFURCATED PHYSICS]: Memecah output untuk SWAN (Dalrymple) dan D-FLOW (Trachytope).
    - [RAY-CASTING MASKING]: Strict CRS Synchronization dengan .gpkg/.shp.
    """
    
    @staticmethod
    def _execute_interpolation(ux, uy, raw_vals, x_coords, y_coords, gx, gy, interp_method, log_cb):
        """Helper Internal: Eksekusi Kriging / Delaunay Murni O(N^3)"""
        if "Kriging" in interp_method:
            max_kriging_points = 2500
            if len(ux) > max_kriging_points:
                idx_sample = np.random.choice(len(ux), max_kriging_points, replace=False)
                ux_k, uy_k, vals_k = ux[idx_sample], uy[idx_sample], raw_vals[idx_sample]
            else:
                ux_k, uy_k, vals_k = ux, uy, raw_vals

            try:
                from pykrige.ok import OrdinaryKriging
                v_model = 'spherical'
                if 'Exponential' in interp_method: v_model = 'exponential'
                elif 'Gaussian' in interp_method: v_model = 'gaussian'
                
                OK = OrdinaryKriging(ux_k, uy_k, vals_k, variogram_model=v_model, verbose=False, enable_plotting=False)
                z_grid, ss = OK.execute('grid', x_coords, y_coords)
                gz_raw = z_grid.data if hasattr(z_grid, 'data') else z_grid
                
                if np.isnan(gz_raw).any():
                    nan_mask = np.isnan(gz_raw)
                    gz_raw[nan_mask] = griddata(np.column_stack((ux_k, uy_k)), vals_k, (gx[nan_mask], gy[nan_mask]), method='nearest')
            except Exception as k_err:
                log_cb(f"  ├ [KRIGING ERROR] Gagal konvergensi ({k_err}). Mengalihkan ke Delaunay...")
                gz_raw = griddata(np.column_stack((ux, uy)), raw_vals, (gx, gy), method='linear')
        else:
            gz_raw = griddata(np.column_stack((ux, uy)), raw_vals, (gx, gy), method='linear')
            
        if np.isnan(gz_raw).any(): 
            nan_mask = np.isnan(gz_raw)
            gz_raw[nan_mask] = griddata(np.column_stack((ux, uy)), raw_vals, (gx[nan_mask], gy[nan_mask]), method='nearest')

        # Batasi agar ekstrapolasi Kriging tidak menghasilkan angka liar di luar batas data asli
        return np.clip(gz_raw, np.min(raw_vals), np.max(raw_vals))

    @staticmethod
    def _render_map(gx, gy, plot_z, ux, uy, gdf_bnd, epsg, cmap_choice, label_text, title_text, out_path):
        """Helper Internal: Rendering Peta Resolusi Tinggi Academic Theme"""
        fig = None
        try:
            fig, ax = plt.subplots(figsize=(8, 6))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('white')
            
            valid_z = plot_z[~np.isnan(plot_z)]
            if len(valid_z) > 0:
                min_z, max_z = np.min(valid_z), np.max(valid_z)
                if min_z == max_z: max_z = min_z + 0.1 
                
                levels = np.linspace(min_z, max_z, 15)
                cf = ax.contourf(gx, gy, plot_z, levels=levels, cmap=cmap_choice, extend='both', alpha=0.85)
                ax.contour(gx, gy, plot_z, levels=levels, colors='black', linewidths=0.5, alpha=0.7)
                
                cb = plt.colorbar(cf, ax=ax, pad=0.02)
                cb.set_label(label_text, color='black', fontweight='bold')
                cb.ax.yaxis.set_tick_params(color='black')
                plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color='black')
            
            if gdf_bnd is not None:
                gdf_bnd.boundary.plot(ax=ax, color='black', linewidth=1.5, zorder=4, label='Batas GPKG/SHP (Mask)')
            
            ax.scatter(ux, uy, c='red', s=25, edgecolors='black', linewidths=0.8, label='Titik LiDAR/Transek', zorder=5)
            
            ax.set_title(title_text, color='black', fontweight='bold', pad=15, fontsize=14)
            ax.tick_params(colors='black')
            ax.grid(True, color='gray', linestyle=':', alpha=0.4)
            
            ax.set_xlabel(f"Easting (EPSG:{epsg})", color='black')
            ax.set_ylabel(f"Northing (EPSG:{epsg})", color='black')
            ax.legend(facecolor='white', edgecolor='black', labelcolor='black', loc='upper right')
            
            plt.tight_layout()
            plt.savefig(out_path, dpi=300) 
        finally:
            if fig is not None:
                fig.clf()
                plt.close(fig)
            gc.collect()

    @staticmethod
    def process_and_interpolate(df: pd.DataFrame, col_x: str, col_y: str, col_val: str, epsg: str, mode_type: str, apply_ks: bool = False, interp_method: str = "Delaunay", boundary_file: str = None, log_cb=None) -> tuple:
        
        def _log(msg):
            logger.info(msg)
            if log_cb: log_cb(msg)
            
        try:
            _log(f"[SEDIMENT] Memulai komputasi geometri & Interpolasi mode: {mode_type}")
            
            if df is None or df.empty:
                raise ValueError("DataFrame input kosong.")
                
            # [ADAPTIVE SENSING]: Otomatis melacak kolom Fisika tambahan untuk Triple-Kriging
            if 'CDx' in df.columns and 'CDy' in df.columns and 'Cd_Average' not in df.columns:
                df['Cd_Average'] = (pd.to_numeric(df['CDx'], errors='coerce') + pd.to_numeric(df['CDy'], errors='coerce')) / 2.0
                if col_val in ['CDx', 'CDy']: col_val = 'Cd_Average' 
                
            col_dbh, col_n = None, None
            for col in df.columns:
                cl = str(col).lower()
                if 'dbh' in cl: col_dbh = col
                if 'dens' in cl or 'n_veg' in cl or 'n_pohon' in cl or col.strip() == 'N': col_n = col
                    
            cols_to_keep = [col_x, col_y, col_val]
            if col_dbh: cols_to_keep.append(col_dbh)
            if col_n: cols_to_keep.append(col_n)
                
            df_clean = df[cols_to_keep].copy()
            for c in cols_to_keep:
                df_clean[c] = pd.to_numeric(df_clean[c], errors='coerce')
            df_clean = df_clean.dropna()
            
            # Singular Matrix Guard (Averaging duplicate coordinates)
            df_clean = df_clean.groupby([col_x, col_y], as_index=False).mean()

            if len(df_clean) < 3:
                raise ValueError(f"Jumlah titik unik ({len(df_clean)}) < 3. Tidak dapat diinterpolasi.")
                
            raw_vals = df_clean[col_val].to_numpy(dtype=np.float64)
                
            # Transformasi EPSG Geospasial
            max_x, max_y = df_clean[col_x].abs().max(), df_clean[col_y].abs().max()
            if max_x > 180 or max_y > 90:
                ux = df_clean[col_x].to_numpy(dtype=np.float64)
                uy = df_clean[col_y].to_numpy(dtype=np.float64)
            else:
                _log(f"  ├ [TRANSFORM] WGS84 -> EPSG:{epsg} (UTM)...")
                tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
                ux, uy = tr.transform(df_clean[col_x].values, df_clean[col_y].values)
                ux, uy = np.asarray(ux, dtype=np.float64), np.asarray(uy, dtype=np.float64)
            
            x_min, x_max = np.min(ux) - 2000, np.max(ux) + 2000
            y_min, y_max = np.min(uy) - 2000, np.max(uy) + 2000
            
            step = 50.0
            while ((x_max - x_min) / step) * ((y_max - y_min) / step) > 4000000: step += 25.0
                
            x_coords, y_coords = np.arange(x_min, x_max, step), np.arange(y_min, y_max, step)
            gx, gy = np.meshgrid(x_coords, y_coords)
            
            # --- 1. KRIGING: TARGET UTAMA (Cd_Average / D50) ---
            _log(f"  ├ [LAYER 1] Mengeksekusi interpolasi untuk Variabel Utama ({col_val})...")
            gz_main = SpatialSedimentEngine._execute_interpolation(ux, uy, raw_vals, x_coords, y_coords, gx, gy, interp_method, _log)
            
            # --- 2. KRIGING: DBH (Jika ada & mode Mangrove) ---
            gz_dbh = None
            if mode_type in ['mangrove', 'submerged'] and col_dbh is not None:
                _log(f"  ├ [LAYER 2] Mengeksekusi interpolasi untuk Diameter Batang ({col_dbh})...")
                dbh_raw = df_clean[col_dbh].to_numpy(dtype=np.float64)
                if np.mean(dbh_raw) > 2.0: dbh_raw = dbh_raw / 100.0 # cm -> m
                gz_dbh = SpatialSedimentEngine._execute_interpolation(ux, uy, dbh_raw, x_coords, y_coords, gx, gy, interp_method, _log)

            # --- 3. KRIGING: DENSITAS N (Jika ada hasil GEE MVI) ---
            gz_n = None
            if mode_type in ['mangrove', 'submerged'] and col_n is not None:
                _log(f"  ├ [LAYER 3] Mengeksekusi interpolasi Spasial Densitas ({col_n})...")
                n_raw = df_clean[col_n].to_numpy(dtype=np.float64)
                gz_n = SpatialSedimentEngine._execute_interpolation(ux, uy, n_raw, x_coords, y_coords, gx, gy, interp_method, _log)

            # ==============================================================================
            # STRICT CRS SPATIAL CLIPPING / MASKING
            # ==============================================================================
            gdf_bnd = None
            if boundary_file and os.path.exists(boundary_file):
                try:
                    import geopandas as gpd
                    from shapely.prepared import prep
                    from shapely.geometry import Point
                    
                    _log(f"  ├ [MASKING] Memuat poligon digitasi: {os.path.basename(boundary_file)}")
                    gdf_bnd = gpd.read_file(boundary_file)
                    
                    if gdf_bnd.crs is None: gdf_bnd = gdf_bnd.set_crs(epsg=4326)
                    target_epsg = int(epsg)
                    if gdf_bnd.crs.to_epsg() != target_epsg: gdf_bnd = gdf_bnd.to_crs(epsg=target_epsg)
                        
                    polygon_union = gdf_bnd.geometry.unary_union
                    prepared_polygon = prep(polygon_union)
                    
                    _log("  ├ Memotong Multi-Layer Grid berdasarkan batas area (Ray-Casting)...")
                    pts = np.column_stack((gx.flatten(), gy.flatten()))
                    mask = np.array([prepared_polygon.contains(Point(x, y)) for x, y in pts])
                    
                    def apply_mask(grid):
                        if grid is None: return None
                        grid_flat = grid.flatten()
                        grid_flat[~mask] = np.nan
                        return grid_flat.reshape(grid.shape)

                    # Membuang (NaN-kan) nilai Z di luar poligon
                    gz_main = apply_mask(gz_main)
                    gz_dbh = apply_mask(gz_dbh)
                    gz_n = apply_mask(gz_n)
                    
                    _log("  ├ [MASKING SUCCESS] Data berhasil dilokalisasi pada zona pesisir.")
                except ImportError:
                    _log("  ├ [WARNING] Pustaka 'geopandas' atau 'shapely' tidak ditemukan. Masking dibatalkan.")
                except Exception as e:
                    _log(f"  ├ [WARNING] Gagal mengeksekusi masking poligon: {e}")

            # ==============================================================================
            # BIFURCATED PHYSICS EXPORT & MAP GENERATION
            # ==============================================================================
            out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))
            os.makedirs(out_dir, exist_ok=True)
            
            x_flat, y_flat = gx.flatten(), gy.flatten()
            plot_paths = []
            
            if mode_type == 'sediment':
                # ========================== JALUR SEDIMEN ==========================
                gz_ks = np.copy(gz_main)
                if apply_ks:
                    mean_val = np.nanmean(gz_ks)
                    if mean_val > 10: gz_ks = (gz_ks / 1000000.0) * 2.5
                    elif mean_val > 0.05: gz_ks = (gz_ks / 1000.0) * 2.5
                    else: gz_ks = gz_ks * 2.5
                
                out_xyz = os.path.join(out_dir, "Sediment_Nikuradse_ks.xyz")
                pd.DataFrame({'X': x_flat, 'Y': y_flat, 'Z': gz_ks.flatten()}).dropna().to_csv(out_xyz, sep=' ', header=False, index=False, float_format='%.4f')
                
                p1 = os.path.join(out_dir, "Sediment_Contours.png")
                SpatialSedimentEngine._render_map(gx, gy, gz_ks, ux, uy, gdf_bnd, epsg, 'YlOrBr', 'Kekasaran Nikuradse (ks) [m]', 'Distribusi Friksi Dasar Sedimen (van Rijn)', p1)
                plot_paths.append(p1)
                
            elif mode_type in ['mangrove', 'submerged']:
                # ========================== JALUR VEGETASI ==========================
                _log(f"  ├ [BIFURCATION] Memecah matriks fisika vegetasi menjadi multi-layer:")
                
                # 1. PETA CD (DRAG COEFFICIENT) -> Untuk SWAN
                out_cd = os.path.join(out_dir, f"{mode_type.capitalize()}_RawData_Cd.xyz")
                pd.DataFrame({'X': x_flat, 'Y': y_flat, 'Z': gz_main.flatten()}).dropna().to_csv(out_cd, sep=' ', header=False, index=False, float_format='%.4f')
                _log(f"    1. Input SWAN Eq 2.20 (Cd) -> {os.path.basename(out_cd)}")
                
                p1 = os.path.join(out_dir, "Mangrove_Map1_CD.png")
                SpatialSedimentEngine._render_map(gx, gy, gz_main, ux, uy, gdf_bnd, epsg, 'Reds', 'Koefisien Drag (Cd)', 'Distribusi Koefisien Drag Spasial (Dalrymple)', p1)
                plot_paths.append(p1)
                
                # 2. PETA DBH (DIAMETER BATANG)
                if gz_dbh is None:
                    _log("  ├ Kolom DBH tidak ditemukan di CSV. Memakai nilai konstan (State Manager).")
                    db_val = app_state.get('veg_stem_diameter_m', 0.15)
                    gz_dbh = np.full_like(gz_main, db_val)
                    gz_dbh[np.isnan(gz_main)] = np.nan 
                else:
                    p2 = os.path.join(out_dir, "Mangrove_Map2_DBH.png")
                    SpatialSedimentEngine._render_map(gx, gy, gz_dbh, ux, uy, gdf_bnd, epsg, 'Oranges', 'Diameter Batang (m)', 'Distribusi Spasial Diameter Batang', p2)
                    plot_paths.append(p2)
                    
                # 3. PETA DENSITAS N
                if gz_n is None:
                    _log("  ├ Kolom Densitas tidak ditemukan di CSV. Memakai nilai konstan (State Manager).")
                    n_val = app_state.get('veg_density_n', 20.0)
                    gz_n = np.full_like(gz_main, n_val)
                    gz_n[np.isnan(gz_main)] = np.nan 
                else:
                    _log(f"  ├ [SPATIAL N DETECTED] Densitas menggunakan Interpolasi Kriging (Horstman et al., 2014)!")
                    p3 = os.path.join(out_dir, "Mangrove_Map3_Density.png")
                    SpatialSedimentEngine._render_map(gx, gy, gz_n, ux, uy, gdf_bnd, epsg, 'PuRd', 'Densitas (n/m²)', 'Distribusi Kerapatan Vegetasi Pesisir', p3)
                    plot_paths.append(p3)

                # 4. PETA EQUIVALENT NIKURADSE (TRACHYTOPE D-FLOW)
                # Baptist Proxy: ks = Cd * D * N (Spatially Multiplied Array-to-Array)
                gz_ks = gz_main * gz_dbh * gz_n
                gz_ks = np.clip(gz_ks, 0.0, 3.0) 
                
                out_xyz = os.path.join(out_dir, f"{mode_type.capitalize()}_Equivalent_ks.xyz")
                pd.DataFrame({'X': x_flat, 'Y': y_flat, 'Z': gz_ks.flatten()}).dropna().to_csv(out_xyz, sep=' ', header=False, index=False, float_format='%.4f')
                _log(f"    2. Input D-FLOW Arus (ks)  -> {os.path.basename(out_xyz)}")
                
                p4 = os.path.join(out_dir, "Mangrove_Map4_Equivalent_Ks.png")
                density_str = "Variatif Spasial" if col_n else f"Tetap: {n_val}/m²"
                SpatialSedimentEngine._render_map(gx, gy, gz_ks, ux, uy, gdf_bnd, epsg, 'Greens', 'Equivalent Nikuradse (ks) [m]', f'Kekasaran Dasar Ekuivalen D-FLOW (Densitas {density_str})', p4)
                plot_paths.append(p4)

            # [ENTERPRISE FIX]: Harus Mengembalikan TYPE 'List' of Strings agar Carousel UI tidak Crash
            return plot_paths, out_xyz
            
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan komputasi spasial fisik ({mode_type}): {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal memproses interpolasi fisik: {str(e)}") from e
