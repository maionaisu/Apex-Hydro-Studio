# ==============================================================================
# APEX NEXUS TIER-0: NETCDF POST-PROCESSING & RENDERING ENGINE
# ==============================================================================
import os
import logging
import traceback
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from pyproj import Transformer
try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False

# Strictly enforce non-interactive backend to prevent GUI Thread locking
matplotlib.use('Agg')
logger = logging.getLogger(__name__)

class PostProcEngine:
    """
    Tier-0 Rendering Engine for D-Flow FM and SWAN Output.
    Generates transparent heatmap overlays mapped to precise bounds.
    """
    
    @staticmethod
    def render_overlay(nc_path: str, target_var: str, time_idx: int, epsg: str, out_dir: str) -> dict:
        if not HAS_XARRAY: 
            raise ImportError("Library 'xarray' dan 'netCDF4' diperlukan untuk module post-processing.")
            
        # 1. Strict I/O Validation
        if not os.path.exists(nc_path):
            raise FileNotFoundError(f"File NetCDF tidak ditemukan di: {nc_path}")
            
        os.makedirs(out_dir, exist_ok=True)
            
        try:
            logger.info(f"[POSTPROC] Membaca {nc_path} | Target: {target_var} | Time Index Request: {time_idx}")
            
            with xr.open_dataset(nc_path) as ds:
                # 2. Detect Topology Coordinates (Flexible Mesh vs Gridded)
                if 'mesh2d_face_x' in ds:
                    ux = ds['mesh2d_face_x'].values
                    uy = ds['mesh2d_face_y'].values
                elif 'mesh2d_node_x' in ds:
                    ux = ds['mesh2d_node_x'].values
                    uy = ds['mesh2d_node_y'].values
                else:
                    # Fallback untuk SWAN gridded output
                    if 'x' in ds and 'y' in ds:
                        X, Y = np.meshgrid(ds.x.values, ds.y.values)
                        ux, uy = X.flatten(), Y.flatten()
                    else:
                        raise KeyError("Geometri mesh (mesh2d_face_x/y atau x/y) tidak terdeteksi dalam NetCDF ini.")

                # 3. BUG-06 FIX: Stationary output guard (SWAN tanpa time dimension)
                has_time = 'time' in ds and getattr(ds['time'], 'ndim', 0) >= 1 and len(ds['time']) > 0
                num_time_steps = len(ds['time']) if has_time else 1
                
                # Memastikan time_idx selalu dalam batas array yang aman (Clamping)
                safe_time_idx = max(0, min(time_idx, num_time_steps - 1))

                # 4. Extract Target Variable Data
                if target_var not in ds:
                    available_vars = list(ds.data_vars.keys())
                    raise KeyError(f"Variabel '{target_var}' tidak ada. Variabel tersedia: {available_vars[:5]}...")
                
                var_data = ds[target_var]
                if has_time and 'time' in var_data.dims:
                    vals = var_data.isel(time=safe_time_idx).values.flatten()
                else:
                    vals = var_data.values.flatten()
                    
                # Mitigasi darurat jika ukuran grid topologi dan data val tidak sinkron
                if len(vals) != len(ux):
                    logger.warning(f"[POSTPROC] Dimensi tidak sinkron (Vals:{len(vals)} vs Coords:{len(ux)}). Memangkas data berlebih.")
                    min_len = min(len(vals), len(ux))
                    vals = vals[:min_len]
                    ux = ux[:min_len]
                    uy = uy[:min_len]

                # 5. Masking Nilai NaN
                valid_mask = ~np.isnan(vals)
                ux = ux[valid_mask]
                uy = uy[valid_mask]
                vals = vals[valid_mask]
                
                if len(ux) == 0:
                    raise ValueError(f"Seluruh frame untuk variabel {target_var} bernilai NaN. Tidak ada yang bisa dirender.")
                    
                # 6. Transformasi EPSG ke LatLon (WGS84) untuk Leaflet
                try:
                    tr = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
                except Exception as e:
                    raise ValueError(f"Kode EPSG tidak valid: {epsg}") from e
                    
                lon, lat = tr.transform(ux, uy)
                
                # Memaksa tipe float absolut untuk keamanan Serialisasi JSON
                w, e = float(lon.min()), float(lon.max())
                s, n = float(lat.min()), float(lat.max())

                # 7. Safe Matplotlib Rendering
                fig = None
                out_img = os.path.join(out_dir, f"overlay_frame_{safe_time_idx}.png")
                
                try:
                    fig = plt.figure(figsize=(10, 10), frameon=False)
                    ax = fig.add_axes([0, 0, 1, 1])
                    ax.axis('off')
                    
                    # Membatasi outlier dengan kuantil ke-2 dan ke-98 untuk representasi warna yang natural
                    v_min, v_max = float(np.percentile(vals, 2)), float(np.percentile(vals, 98))
                    
                    # Estetika Skripsi CMC Mangrove - Pilihan warna cerdas berdasarkan parameter
                    cmap_choice = 'jet'
                    var_lower = target_var.lower()
                    if 'hs' in var_lower or 'swh' in var_lower or 'sig' in var_lower: 
                        cmap_choice = 'ocean_r'
                    elif 'ucy' in var_lower or 'ucx' in var_lower or 'vel' in var_lower: 
                        cmap_choice = 'twilight'
                    elif 'sed' in var_lower or 'bed' in var_lower or 'depth' in var_lower: 
                        cmap_choice = 'copper'
                    
                    # Membuat scatter plot transparan sebagai heatmap overlay
                    ax.scatter(lon, lat, c=vals, cmap=cmap_choice, s=8, alpha=0.85, vmin=v_min, vmax=v_max)
                    ax.set_xlim(w, e)
                    ax.set_ylim(s, n)
                    
                    plt.savefig(out_img, transparent=True, pad_inches=0, bbox_inches='tight', dpi=200)
                    logger.debug(f"[POSTPROC] Frame ke-{safe_time_idx} berhasil di-render.")
                    
                finally:
                    # Memory Leak Guard
                    if fig is not None:
                        plt.close(fig)
                        
                # Ekstraksi timestamp jika ada
                time_str = str(ds['time'].values[safe_time_idx]) if has_time else 'Static Frame (Stationary)'
                
                return {
                    'image_path': out_img,
                    'bounds': {'N': n, 'S': s, 'E': e, 'W': w},
                    'time_str': time_str,
                    'max_time': num_time_steps - 1,
                    'v_min': v_min,
                    'v_max': v_max
                }
                
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan Post-Processing pada file {os.path.basename(nc_path)}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal me-render NetCDF overlay: {str(e)}") from e

    @staticmethod
    def run_point_validation(nc_path: str, csv_path: str, target_var: str, lat: float, lon: float, epsg: str, out_dir: str) -> dict:
        """
        Mengekstrak time-series NetCDF pada titik stasiun terdekat (Nearest Neighbor),
        melakukan sinkronisasi waktu (merge_asof) dengan data CSV Observasi,
        menghitung matriks error (RMSE, Bias, R2), dan merender Plot Overlay.
        """
        if not HAS_XARRAY: 
            raise ImportError("Library 'xarray' dan 'pandas' diperlukan untuk validasi.")
            
        os.makedirs(out_dir, exist_ok=True)
        import pandas as pd
        
        try:
            logger.info(f"[VALIDATION] Memulai kalibrasi titik. Model: {nc_path} | Obs: {csv_path}")
            
            # 1. Mapping Variabel UI ke Nama Kolom Asli
            var_map = {
                'Hsig (Tinggi Gelombang)': ('Hsig', 'Hs', 'm'),
                'Tp (Periode Puncak)': ('Tp', 'Tp', 's')
            }
            nc_var, csv_var, unit = var_map.get(target_var, ('Hsig', 'Hs', 'm'))
            
            # 2. Baca CSV Observasi (Ground Truth)
            df_obs = pd.read_csv(csv_path)
            # Pastikan kolom timestamp dibaca sebagai Datetime naive (tanpa timezone)
            df_obs['timestamp'] = pd.to_datetime(df_obs['timestamp']).dt.tz_localize(None)
            df_obs = df_obs[['timestamp', csv_var]].dropna().sort_values('timestamp')
            
            # 3. Baca NetCDF Model dan Transformasi Koordinat Stasiun
            tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            target_x, target_y = tr.transform(lon, lat)
            
            with xr.open_dataset(nc_path) as ds:
                if nc_var not in ds:
                    raise KeyError(f"Variabel Model '{nc_var}' tidak ditemukan di NetCDF.")
                    
                # Deteksi Topologi Grid
                if 'mesh2d_face_x' in ds:
                    ux, uy = ds['mesh2d_face_x'].values, ds['mesh2d_face_y'].values
                elif 'x' in ds and 'y' in ds:
                    X, Y = np.meshgrid(ds.x.values, ds.y.values)
                    ux, uy = X.flatten(), Y.flatten()
                else:
                    raise KeyError("Geometri mesh tidak terdeteksi untuk ekstraksi titik.")
                
                # 4. Nearest Neighbor Extraction (Titik terdekat)
                dists = np.hypot(ux - target_x, uy - target_y)
                min_idx = np.nanargmin(dists)
                closest_dist = dists[min_idx]
                
                logger.info(f"[VALIDATION] Titik terdekat ditemukan pada jarak {closest_dist:.2f} meter dari koordinat input.")
                
                # Ekstrak rentetan waktu
                model_times = pd.to_datetime(ds['time'].values).tz_localize(None)
                
                # Reshape array ke 2D (Time, Space) untuk mengekstrak titik spesifik secara konsisten
                val_array = ds[nc_var].values
                val_array_2d = val_array.reshape(len(model_times), -1)
                model_vals = val_array_2d[:, min_idx]
                
                df_model = pd.DataFrame({'timestamp': model_times, 'model_val': model_vals})
                df_model = df_model.dropna().sort_values('timestamp')
                
            # 5. Sinkronisasi Waktu (Merge Asof - Mencari waktu beririsan terdekat toleransi 2 jam)
            df_merge = pd.merge_asof(
                df_obs, df_model, 
                on='timestamp', direction='nearest', 
                tolerance=pd.Timedelta('2h')
            ).dropna()
            
            if df_merge.empty:
                raise ValueError("Tidak ada irisan waktu (Timestamp) yang cocok antara Model ERA5 dan Data Wave Gauge Observasi.")
                
            y_obs = df_merge[csv_var].values
            y_mod = df_merge['model_val'].values
            times = df_merge['timestamp'].values
            
            # 6. Komputasi Statistik Matematika
            rmse = np.sqrt(np.mean((y_mod - y_obs)**2))
            bias = np.mean(y_mod - y_obs)
            # Mencegah pembagian nol pada korelasi
            r2 = 0.0
            if np.std(y_obs) > 0 and np.std(y_mod) > 0:
                r2 = np.corrcoef(y_obs, y_mod)[0, 1] ** 2
                
            # 7. Render Plot Validasi (Enterprise Fintech Slate Style)
            fig = None
            out_plot = os.path.join(out_dir, f"Validation_{csv_var}_Plot.png")
            
            try:
                fig = plt.figure(figsize=(12, 6))
                fig.patch.set_facecolor('#1E2128') # Sesuai QGroupBox pane
                
                # Subplot 1: Time Series Overlay
                ax1 = plt.subplot(1, 2, 1)
                ax1.set_facecolor('#0F172A')
                ax1.plot(times, y_obs, 'o-', color='#F7C159', label='Observasi (Wave Gauge)', linewidth=2, markersize=4)
                ax1.plot(times, y_mod, '-', color='#38BDF8', label='Simulasi (D-WAVES)', linewidth=2.5)
                ax1.set_title(f"Time Series Overlay - {nc_var}", color='#FFFFFF', fontweight='bold')
                ax1.set_ylabel(f"{nc_var} ({unit})", color='#9CA3AF')
                ax1.tick_params(colors='#9CA3AF', rotation=45)
                ax1.grid(color='#3A3F4A', linestyle='--', alpha=0.7)
                ax1.legend(facecolor='#1E2128', edgecolor='#3A3F4A', labelcolor='white')
                for spine in ax1.spines.values(): spine.set_edgecolor('#3A3F4A')
                
                # Subplot 2: Scatter Plot
                ax2 = plt.subplot(1, 2, 2)
                ax2.set_facecolor('#0F172A')
                ax2.scatter(y_obs, y_mod, color='#42E695', s=30, alpha=0.8, edgecolor='#0F172A')
                
                # Garis Identitas (1:1 Line)
                min_val = min(np.min(y_obs), np.min(y_mod))
                max_val = max(np.max(y_obs), np.max(y_mod))
                ax2.plot([min_val, max_val], [min_val, max_val], 'r--', label='1:1 Perfect Match', alpha=0.7)
                
                ax2.set_title(f"Scatter Plot (R² = {r2:.3f})", color='#FFFFFF', fontweight='bold')
                ax2.set_xlabel(f"Observasi {nc_var}", color='#9CA3AF')
                ax2.set_ylabel(f"Model {nc_var}", color='#9CA3AF')
                ax2.tick_params(colors='#9CA3AF')
                ax2.grid(color='#3A3F4A', linestyle='--', alpha=0.7)
                ax2.legend(facecolor='#1E2128', edgecolor='#3A3F4A', labelcolor='white')
                for spine in ax2.spines.values(): spine.set_edgecolor('#3A3F4A')
                
                plt.tight_layout()
                plt.savefig(out_plot, dpi=150, bbox_inches='tight')
                
            finally:
                if fig is not None:
                    plt.close(fig)
                    
            logger.info(f"[VALIDATION] Komputasi sukses. RMSE: {rmse:.3f}, Bias: {bias:.3f}, R2: {r2:.3f}")
            return {
                'rmse': rmse,
                'bias': bias,
                'r2': r2,
                'plot_path': out_plot,
                'dist': closest_dist
            }
            
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan Ekstraksi/Validasi Point: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal melakukan validasi data: {str(e)}") from e
