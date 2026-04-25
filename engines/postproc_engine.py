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
import matplotlib.tri as tri

# [CRITICAL GUARD]: Memaksa Matplotlib menggunakan backend 'Agg' (Anti-Grain Geometry).
# Ini menjamin Matplotlib tidak akan mencoba membuka jendela GUI (Tkinter/Qt) dari 
# background thread yang dapat menyebabkan aplikasi Force Close (SegFault).
matplotlib.use('Agg')

logger = logging.getLogger(__name__)

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False


class PostProcEngine:
    """
    [TIER-0] Mesin ekstraksi dan rendering NetCDF (.nc) menggunakan Xarray dan Dask.
    Memiliki dua kemampuan utama:
    1. Render Overlay: Memotong frame spasial untuk animasi Leaflet Heatmap.
    2. Point Validation: Mengekstrak time-series 1D untuk dibandingkan dengan observasi CSV.
    """

    @staticmethod
    def render_overlay(nc_path: str, var_name: str, time_idx: int, epsg: str, out_dir: str) -> dict:
        """
        Mengekstrak frame 2D spesifik dari NetCDF, merendernya menjadi gambar transparan (PNG),
        dan mengkalkulasi batas Bounding Box (Lat/Lon) untuk di-overlay ke Leaflet Peta.
        """
        if not HAS_XARRAY: 
            raise ImportError("Library 'xarray' dan 'netCDF4' diperlukan untuk membaca hasil simulasi.")
            
        os.makedirs(out_dir, exist_ok=True)
        out_img = os.path.join(out_dir, f"frame_{var_name}_t{time_idx}.png")
        fig = None

        try:
            logger.debug(f"[POSTPROC] Mengekstrak frame {time_idx} untuk variabel '{var_name}'...")
            
            # Gunakan engine netcdf4 dan hindari memuat seluruh array ke RAM
            with xr.open_dataset(nc_path, engine='netcdf4') as ds:
                if var_name not in ds:
                    raise KeyError(f"Variabel '{var_name}' tidak ditemukan dalam NetCDF.")
                
                # Mengambil informasi waktu
                times = ds['time'].values
                max_time_idx = len(times) - 1
                safe_idx = max(0, min(time_idx, max_time_idx))
                
                time_str = pd.to_datetime(times[safe_idx]).strftime('%Y-%m-%d %H:%M:%S')
                
                # Ekstraksi koordinat jaring (Topology/Mesh)
                if 'mesh2d_face_x' in ds and 'mesh2d_face_y' in ds:
                    # Format D-Flow FM (Flexible Unstructured Mesh)
                    x_vals = ds['mesh2d_face_x'].values
                    y_vals = ds['mesh2d_face_y'].values
                elif 'x' in ds and 'y' in ds:
                    # Format D-Waves / SWAN (Rectilinear Grid)
                    X, Y = np.meshgrid(ds['x'].values, ds['y'].values)
                    x_vals, y_vals = X.flatten(), Y.flatten()
                else:
                    raise KeyError("Sistem koordinat spasial (X/Y) tidak dikenali dalam file NetCDF ini.")

                # Ekstraksi Nilai Z berdasarkan index waktu
                z_array = ds[var_name].isel(time=safe_idx).values.flatten()
                
                # Membersihkan nilai NaN / FillValue (-999.0)
                valid_mask = ~np.isnan(z_array) & (z_array > -900.0)
                if not valid_mask.any():
                    raise ValueError(f"Seluruh frame pada indeks T={safe_idx} bernilai kosong (NaN/Daratan).")
                    
                x_clean = x_vals[valid_mask]
                y_clean = y_vals[valid_mask]
                z_clean = z_array[valid_mask]
                
                v_min, v_max = float(z_clean.min()), float(z_clean.max())

                # Translasi Koordinat (UTM ke WGS84) untuk Bounding Box Leaflet
                tr = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
                lon, lat = tr.transform(x_clean, y_clean)
                
                n, s = float(np.max(lat)), float(np.min(lat))
                e, w = float(np.max(lon)), float(np.min(lon))

                # --- RENDERING GAMBAR (TRANSPARENT BACKGROUND) ---
                # Mematikan axes dan menyisakan murni piksel data untuk overlay peta
                fig, ax = plt.subplots(figsize=(10, 10))
                fig.patch.set_alpha(0.0)
                ax.set_axis_off()
                ax.margins(0)
                
                # Render heatmap (Scatter digunakan agar kompatibel dengan Unstructured Mesh)
                cmap = 'jet' if var_name in ['Hsig', 'Tp'] else 'viridis'
                ax.scatter(lon, lat, c=z_clean, cmap=cmap, s=20, alpha=0.85, edgecolors='none')
                
                plt.savefig(out_img, dpi=120, transparent=True, bbox_inches='tight', pad_inches=0)

                return {
                    'image_path': out_img,
                    'bounds': {'N': n, 'S': s, 'E': e, 'W': w},
                    'time_str': time_str,
                    'max_time': max_time_idx,
                    'v_min': v_min,
                    'v_max': v_max
                }
                
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan Render Overlay pada file {os.path.basename(nc_path)}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal me-render NetCDF overlay: {str(e)}") from e
            
        finally:
            if fig is not None:
                fig.clf() # Clean internal layout
                plt.close(fig) # Prevent Memory Leak
            gc.collect()

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
        fig = None
        
        try:
            logger.info(f"[VALIDATION] Memulai kalibrasi titik stasiun. Model: {nc_path} | Obs: {csv_path}")
            
            # 1. Mapping Variabel UI ke Nama Kolom Asli Model dan Observasi
            var_map = {
                'Hsig (Tinggi Gelombang)': ('Hsig', 'Hs', 'm'),
                'Tp (Periode Puncak)': ('Tp', 'Tp', 's')
            }
            nc_var, csv_var, unit = var_map.get(target_var, ('Hsig', 'Hs', 'm'))
            
            # 2. Baca CSV Observasi (Ground Truth WaveSpectra)
            df_obs = pd.read_csv(csv_path)
            if 'timestamp' not in df_obs.columns:
                raise KeyError("File CSV observasi harus memiliki kolom 'timestamp'.")
                
            # Pastikan kolom timestamp dibaca sebagai Datetime naive (tanpa timezone) dan HARUS TERURUT
            df_obs['timestamp'] = pd.to_datetime(df_obs['timestamp']).dt.tz_localize(None)
            df_obs = df_obs[['timestamp', csv_var]].dropna().sort_values('timestamp')
            
            # 3. Translasi Koordinat Stasiun (WGS84 -> UTM Model)
            tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            target_x, target_y = tr.transform(lon, lat)
            
            # 4. Baca NetCDF Model & Lakukan Ekstraksi (Nearest Neighbor)
            with xr.open_dataset(nc_path, engine='netcdf4') as ds:
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
                
                # Nearest Neighbor Extraction menggunakan Hipotenusa
                dists = np.hypot(ux - target_x, uy - target_y)
                min_idx = np.nanargmin(dists)
                closest_dist = dists[min_idx]
                
                logger.info(f"[VALIDATION] Titik terdekat ditemukan pada jarak {closest_dist:.2f} meter dari koordinat input.")
                
                # Ekstrak rentetan waktu model
                model_times = pd.to_datetime(ds['time'].values).tz_localize(None)
                
                # Mengambil nilai time-series di node/face spesifik (min_idx)
                try:
                    if len(ds[nc_var].dims) == 2:
                        # Asumsi [time, face]
                        model_vals = ds[nc_var].isel({ds[nc_var].dims[1]: min_idx}).values
                    else:
                        # Flattening paksa jika dimensi kompleks
                        val_array = ds[nc_var].values
                        val_array_2d = val_array.reshape(len(model_times), -1)
                        model_vals = val_array_2d[:, min_idx]
                except Exception as ex:
                    raise ValueError(f"Struktur dimensi {nc_var} tidak didukung: {ex}")
                
                df_model = pd.DataFrame({'timestamp': model_times, 'model_val': model_vals})
                # Membuang fill values dan memastikan baris terurut (Prasyarat mutlak merge_asof)
                df_model = df_model[(df_model['model_val'] > -900) & (~df_model['model_val'].isna())]
                df_model = df_model.sort_values('timestamp')
                
            # 5. Sinkronisasi Waktu (Merge Asof)
            # Mencari waktu observasi dan model yang beririsan (toleransi max 2 jam)
            df_merge = pd.merge_asof(
                df_obs, df_model, 
                on='timestamp', direction='nearest', 
                tolerance=pd.Timedelta('2h')
            ).dropna()
            
            if df_merge.empty:
                raise ValueError("TIDAK ADA IRISAN WAKTU. Tanggal/Jam observasi dan hasil model tidak selaras. Harap periksa input Anda.")
                
            y_obs = df_merge[csv_var].values
            y_mod = df_merge['model_val'].values
            times = df_merge['timestamp'].values
            
            # 6. Komputasi Statistik Matematika
            rmse = np.sqrt(np.mean((y_mod - y_obs)**2))
            bias = np.mean(y_mod - y_obs)
            
            r2 = 0.0
            if np.std(y_obs) > 0 and np.std(y_mod) > 0:
                r2 = np.corrcoef(y_obs, y_mod)[0, 1] ** 2
                
            # 7. Render Plot Validasi (Fintech Slate Style)
            out_plot = os.path.join(out_dir, f"Validation_{csv_var}_Plot.png")
            
            fig = plt.figure(figsize=(12, 6))
            fig.patch.set_facecolor('#1E2128') # Sesuai QGroupBox pane UI Modul 6
            
            # --- Subplot 1: Time Series Overlay ---
            ax1 = plt.subplot(1, 2, 1)
            ax1.set_facecolor('#0F172A')
            ax1.plot(times, y_obs, 'o-', color='#F7C159', label='Observasi Lapangan', linewidth=2, markersize=4)
            ax1.plot(times, y_mod, '-', color='#38BDF8', label='Simulasi Model', linewidth=2.5)
            ax1.set_title(f"Time Series Overlay - {nc_var}", color='#FFFFFF', fontweight='bold', pad=10)
            ax1.set_ylabel(f"{nc_var} ({unit})", color='#9CA3AF')
            ax1.tick_params(colors='#9CA3AF', rotation=45)
            ax1.grid(color='#3A3F4A', linestyle='--', alpha=0.7)
            ax1.legend(facecolor='#1E2128', edgecolor='#3A3F4A', labelcolor='white')
            for spine in ax1.spines.values(): spine.set_edgecolor('#3A3F4A')
            
            # --- Subplot 2: Scatter Plot ---
            ax2 = plt.subplot(1, 2, 2)
            ax2.set_facecolor('#0F172A')
            ax2.scatter(y_obs, y_mod, color='#42E695', s=40, alpha=0.8, edgecolor='#0F172A')
            
            # Garis Identitas (1:1 Line)
            min_val = min(np.min(y_obs), np.min(y_mod))
            max_val = max(np.max(y_obs), np.max(y_mod))
            ax2.plot([min_val, max_val], [min_val, max_val], 'r--', label='1:1 Perfect Match', alpha=0.7)
            
            ax2.set_title(f"Korelasi Scatter Plot (R² = {r2:.3f})", color='#FFFFFF', fontweight='bold', pad=10)
            ax2.set_xlabel(f"Observasi {nc_var} ({unit})", color='#9CA3AF')
            ax2.set_ylabel(f"Model {nc_var} ({unit})", color='#9CA3AF')
            ax2.tick_params(colors='#9CA3AF')
            ax2.grid(color='#3A3F4A', linestyle='--', alpha=0.7)
            ax2.legend(facecolor='#1E2128', edgecolor='#3A3F4A', labelcolor='white')
            for spine in ax2.spines.values(): spine.set_edgecolor('#3A3F4A')
            
            plt.tight_layout()
            plt.savefig(out_plot, dpi=150, bbox_inches='tight')
                
            logger.info(f"[VALIDATION] Komputasi sukses. RMSE: {rmse:.3f}, Bias: {bias:.3f}, R2: {r2:.3f}")
            return {
                'rmse': float(rmse),
                'bias': float(bias),
                'r2': float(r2),
                'plot_path': out_plot,
                'dist': float(closest_dist)
            }
            
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan Ekstraksi/Validasi Point: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal melakukan validasi data: {str(e)}") from e
            
        finally:
            if fig is not None:
                fig.clf()
                plt.close(fig)
            gc.collect() # Safeguard from Pandas/Matplotlib memory bloat
