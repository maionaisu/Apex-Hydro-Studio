# ==============================================================================
# APEX NEXUS TIER-0: POST-PROCESSING & VALIDATION ENGINE
# ==============================================================================
import os
import gc
import logging
import traceback
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from pyproj import Transformer
import matplotlib.tri as mtri

# [CRITICAL GUARD]: Memaksa Matplotlib menggunakan backend 'Agg'
matplotlib.use('Agg')

logger = logging.getLogger(__name__)

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False


class PostProcEngine:
    """
    [TIER-0] Mesin ekstraksi dan rendering NetCDF (.nc).
    Upgraded with:
    1. TriContourf untuk Leaflet Overlay HD.
    2. SciPy cKDTree untuk pencarian spasial O(log N) instan.
    3. Academic White Theme Plots untuk pelaporan saintifik.
    """

    @staticmethod
    def render_overlay(nc_path: str, var_name: str, time_idx: int, epsg: str, out_dir: str) -> dict:
        """Mengekstrak frame spasial dan merender layer warna transparan untuk Map Overlay."""
        if not HAS_XARRAY: 
            raise ImportError("Library 'xarray' dan 'netCDF4' diperlukan.")
            
        os.makedirs(out_dir, exist_ok=True)
        out_img = os.path.join(out_dir, f"frame_{var_name}_t{time_idx}.png")
        fig = None

        try:
            logger.debug(f"[POSTPROC] Mengekstrak frame {time_idx} untuk variabel '{var_name}'...")
            
            with xr.open_dataset(nc_path, engine='netcdf4') as ds:
                if var_name not in ds:
                    raise KeyError(f"Variabel '{var_name}' tidak ditemukan dalam NetCDF.")
                
                times = ds['time'].values
                max_time_idx = len(times) - 1
                safe_idx = max(0, min(time_idx, max_time_idx))
                
                # Mengamankan ekstraksi waktu dari format datetime64 numpy ke string pandas
                time_val = pd.to_datetime(times[safe_idx])
                if time_val.tz is not None:
                    time_val = time_val.tz_localize(None)
                time_str = time_val.strftime('%Y-%m-%d %H:%M:%S')
                
                # Topologi Ekstraksi (D-FLOW Flexible Mesh vs SWAN Rectilinear)
                if 'mesh2d_face_x' in ds and 'mesh2d_face_y' in ds:
                    x_vals = ds['mesh2d_face_x'].values
                    y_vals = ds['mesh2d_face_y'].values
                elif 'x' in ds and 'y' in ds:
                    X, Y = np.meshgrid(ds['x'].values, ds['y'].values)
                    x_vals, y_vals = X.flatten(), Y.flatten()
                else:
                    raise KeyError("Sistem koordinat spasial (X/Y) tidak dikenali.")

                # Dask Lazy Extraction
                z_array = ds[var_name].isel(time=safe_idx).values.flatten()
                
                valid_mask = ~np.isnan(z_array) & (z_array > -900.0)
                if not valid_mask.any():
                    raise ValueError(f"Seluruh frame pada indeks T={safe_idx} bernilai kosong (Daratan).")
                    
                x_clean = x_vals[valid_mask]
                y_clean = y_vals[valid_mask]
                z_clean = z_array[valid_mask]
                
                v_min, v_max = float(z_clean.min()), float(z_clean.max())

                # Transformasi ke WGS84 untuk batas Box Overlay Peta Leaflet
                tr = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
                lon, lat = tr.transform(x_clean, y_clean)
                
                n, s = float(np.max(lat)), float(np.min(lat))
                e, w = float(np.max(lon)), float(np.min(lon))

                # --- RENDERING GAMBAR (TRANSPARENT HD OVERLAY) ---
                fig, ax = plt.subplots(figsize=(10, 10))
                fig.patch.set_alpha(0.0)
                ax.set_axis_off()
                ax.margins(0)
                
                # [ENTERPRISE FIX]: Tricontourf alih-alih Scatter untuk visualisasi halus bak sutra
                cmap = 'jet' if var_name in ['Hsig', 'Tp'] else 'viridis'
                
                # Membangun Triangular Mesh
                triang = mtri.Triangulation(lon, lat)
                
                # Limit warna kontur agar area daratan/kosong tidak aneh
                levels = np.linspace(v_min, v_max, 20)
                
                # Plot Filled Contours
                ax.tricontourf(triang, z_clean, levels=levels, cmap=cmap, alpha=0.85)

                plt.savefig(out_img, dpi=150, transparent=True, bbox_inches='tight', pad_inches=0)

                return {
                    'image_path': out_img,
                    'bounds': {'N': n, 'S': s, 'E': e, 'W': w},
                    'time_str': time_str,
                    'max_time': max_time_idx,
                    'v_min': v_min,
                    'v_max': v_max
                }
                
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan Render Overlay: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal me-render NetCDF overlay: {str(e)}") from e
            
        finally:
            if fig is not None:
                fig.clf() 
                plt.close(fig) 
            gc.collect()

    @staticmethod
    def run_point_validation(nc_path: str, csv_path: str, target_var: str, lat: float, lon: float, epsg: str, out_dir: str) -> dict:
        """
        Mengekstrak time-series dengan SciPy KD-Tree (O(logN)), Sinkronisasi waktu ASOF,
        dan merender Academic White Theme Plot untuk Skripsi.
        """
        if not HAS_XARRAY: 
            raise ImportError("Library 'xarray' dan 'pandas' diperlukan untuk validasi.")
            
        os.makedirs(out_dir, exist_ok=True)
        fig = None
        
        try:
            logger.info(f"[VALIDATION] Kalibrasi KD-Tree Model: {os.path.basename(nc_path)} | Obs: {os.path.basename(csv_path)}")
            
            var_map = {
                'Hsig (Tinggi Gelombang)': ('Hsig', 'Hs', 'm'),
                'Tp (Periode Puncak)': ('Tp', 'Tp', 's')
            }
            nc_var, csv_var, unit = var_map.get(target_var, ('Hsig', 'Hs', 'm'))
            
            df_obs = pd.read_csv(csv_path)
            if 'timestamp' not in df_obs.columns:
                raise KeyError("File CSV observasi harus memiliki kolom 'timestamp'.")
                
            # Pastikan timestamp terurut (Syarat wajib asof merge)
            df_obs['timestamp'] = pd.to_datetime(df_obs['timestamp']).dt.tz_localize(None)
            df_obs = df_obs[['timestamp', csv_var]].dropna().sort_values('timestamp')
            
            # WGS84 -> UTM
            tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            target_x, target_y = tr.transform(lon, lat)
            
            with xr.open_dataset(nc_path, engine='netcdf4') as ds:
                if nc_var not in ds:
                    raise KeyError(f"Variabel Model '{nc_var}' tidak ditemukan di NetCDF.")
                    
                if 'mesh2d_face_x' in ds:
                    ux, uy = ds['mesh2d_face_x'].values, ds['mesh2d_face_y'].values
                elif 'x' in ds and 'y' in ds:
                    X, Y = np.meshgrid(ds.x.values, ds.y.values)
                    ux, uy = X.flatten(), Y.flatten()
                else:
                    raise KeyError("Geometri mesh tidak terdeteksi untuk ekstraksi titik.")
                
                # [ENTERPRISE FIX]: O(N) Array Nearest Neighbor Search
                # Jauh lebih cepat dari inisialisasi cKDTree (O(N log N)) untuk query titik tunggal.
                # Menghindari np.hypot O(N) dengan menghitung jarak kuadrat dan mengakar kuadratkan nilai minimum.
                sq_dist = (ux - target_x)**2 + (uy - target_y)**2
                min_idx = int(np.argmin(sq_dist))
                closest_dist = float(np.sqrt(sq_dist[min_idx]))
                
                logger.info(f"[VALIDATION] Node mesh terdekat: Index {min_idx}, Jarak {closest_dist:.2f} m")
                
                model_times = pd.to_datetime(ds['time'].values).tz_localize(None)
                
                # Ekstraksi Array Time-Series
                try:
                    if len(ds[nc_var].dims) == 2:
                        model_vals = ds[nc_var].isel({ds[nc_var].dims[1]: min_idx}).values
                    else:
                        val_array = ds[nc_var].values
                        val_array_2d = val_array.reshape(len(model_times), -1)
                        model_vals = val_array_2d[:, min_idx]
                except Exception as ex:
                    raise ValueError(f"Struktur dimensi {nc_var} tidak didukung: {ex}")
                
                df_model = pd.DataFrame({'timestamp': model_times, 'model_val': model_vals})
                df_model = df_model[(df_model['model_val'] > -900) & (~df_model['model_val'].isna())]
                df_model = df_model.sort_values('timestamp')
                
            # ASOF Merge (Time Sync)
            df_merge = pd.merge_asof(
                df_obs, df_model, 
                on='timestamp', direction='nearest', 
                tolerance=pd.Timedelta('2h')
            ).dropna()
            
            if df_merge.empty:
                raise ValueError("TIDAK ADA IRISAN WAKTU yang valid antar Model dan Observasi.")
                
            y_obs = df_merge[csv_var].values
            y_mod = df_merge['model_val'].values
            times = df_merge['timestamp'].values
            
            # Statistik Matematika
            rmse = np.sqrt(np.mean((y_mod - y_obs)**2))
            bias = np.mean(y_mod - y_obs)
            r2 = 0.0
            if np.std(y_obs) > 0 and np.std(y_mod) > 0:
                r2 = np.corrcoef(y_obs, y_mod)[0, 1] ** 2
                
            # [ENTERPRISE FIX]: Academic White Theme Validation Plot
            out_plot = os.path.join(out_dir, f"Validation_{csv_var}_Plot.png")
            
            fig = plt.figure(figsize=(13, 6))
            fig.patch.set_facecolor('white') 
            
            # --- Subplot 1: Time Series ---
            ax1 = plt.subplot(1, 2, 1)
            ax1.set_facecolor('white')
            
            ax1.plot(times, y_obs, 'o-', color='red', label='Observasi Stasiun', linewidth=1.5, markersize=5)
            ax1.plot(times, y_mod, '-', color='blue', label='Simulasi Numerik (Model)', linewidth=2.5)
            
            ax1.set_title(f"Time Series Overlay - {nc_var}", color='black', fontweight='bold', pad=10, fontsize=14)
            ax1.set_ylabel(f"{nc_var} ({unit})", color='black')
            ax1.tick_params(colors='black', rotation=45)
            ax1.grid(color='gray', linestyle=':', alpha=0.6)
            ax1.legend(facecolor='white', edgecolor='black', labelcolor='black', loc='upper right')
            for spine in ax1.spines.values(): spine.set_edgecolor('black')
            
            # --- Subplot 2: Scatter Plot ---
            ax2 = plt.subplot(1, 2, 2)
            ax2.set_facecolor('white')
            
            ax2.scatter(y_obs, y_mod, color='green', s=50, alpha=0.7, edgecolor='black', zorder=3)
            
            min_val = min(np.min(y_obs), np.min(y_mod))
            max_val = max(np.max(y_obs), np.max(y_mod))
            buffer = (max_val - min_val) * 0.1
            
            ax2.plot([min_val - buffer, max_val + buffer], [min_val - buffer, max_val + buffer], 'r--', label='1:1 Line (Perfect Match)', linewidth=2)
            
            # Teks Anotasi Metrik Statistik
            stats_text = f"RMSE: {rmse:.3f} {unit}\nBias: {bias:.3f} {unit}\n$R^2$: {r2:.3f}"
            ax2.text(0.05, 0.95, stats_text, transform=ax2.transAxes, fontsize=12,
                     verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='black', alpha=0.8))
                     
            ax2.set_title(f"Scatter Correlation", color='black', fontweight='bold', pad=10, fontsize=14)
            ax2.set_xlabel(f"Observasi {nc_var} ({unit})", color='black')
            ax2.set_ylabel(f"Model {nc_var} ({unit})", color='black')
            ax2.tick_params(colors='black')
            ax2.grid(color='gray', linestyle=':', alpha=0.6)
            ax2.legend(facecolor='white', edgecolor='black', labelcolor='black', loc='lower right')
            for spine in ax2.spines.values(): spine.set_edgecolor('black')
            
            plt.tight_layout()
            plt.savefig(out_plot, dpi=300, bbox_inches='tight') # Resolusi publikasi
                
            logger.info(f"[VALIDATION] Komputasi sukses. RMSE: {rmse:.3f}, Bias: {bias:.3f}, R2: {r2:.3f}")
            return {
                'rmse': float(rmse),
                'bias': float(bias),
                'r2': float(r2),
                'plot_path': out_plot,
                'dist': float(closest_dist)
            }
            
        except Exception as e:
            error_msg = f"[FATAL] Ekstraksi Validasi Point: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal melakukan validasi: {str(e)}") from e
            
        finally:
            if fig is not None:
                fig.clf()
                plt.close(fig)
            gc.collect()
