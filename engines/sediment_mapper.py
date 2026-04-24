# ==============================================================================
# APEX NEXUS TIER-0: SPATIAL SEDIMENT & VEGETATION MAPPER
# ==============================================================================
import os
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
    Tier-0 Engine for 2D spatial interpolation (Delaunay) of sediment,
    mangrove density, and submerged vegetation fields.
    Upgraded with OOM (Out Of Memory) protection and Smart Auto-Correction logic.
    """
    @staticmethod
    def process_and_interpolate(df: pd.DataFrame, col_x: str, col_y: str, col_val: str, epsg: str, mode_type: str, apply_ks: bool = False, log_cb=None) -> tuple:
        
        def _log(msg):
            """Fungsi helper agar pesan sinkron masuk ke backend logger dan UI (jika callback tersedia)"""
            logger.info(msg)
            if log_cb: log_cb(msg)
            
        try:
            _log(f"[SEDIMENT] Memulai proses interpolasi spasial mode: {mode_type}")
            
            # 1. Strict Validation & Pre-processing
            if df is None or df.empty:
                raise ValueError("DataFrame input kosong atau tidak valid.")
                
            df_clean = df[[col_x, col_y, col_val]].copy()
            
            # Paksa konversi ke numeric, karakter non-angka menjadi NaN
            df_clean[col_x] = pd.to_numeric(df_clean[col_x], errors='coerce')
            df_clean[col_y] = pd.to_numeric(df_clean[col_y], errors='coerce')
            df_clean[col_val] = pd.to_numeric(df_clean[col_val], errors='coerce')
            
            df_clean = df_clean.dropna(subset=[col_x, col_y, col_val]).reset_index(drop=True)
            
            # Delaunay griddata memerlukan setidaknya 3 titik tidak segaris
            if len(df_clean) < 3:
                raise ValueError(f"Jumlah titik data valid ({len(df_clean)}) tidak mencukupi untuk interpolasi 2D Delaunay (Minimal 3 titik).")
                
            vals = df_clean[col_val].values
            
            # 2. SMART AUTO-CORRECTION: Nikuradse ks validation and transformation
            if mode_type == 'sediment' and apply_ks:
                mean_val = vals.mean()
                if mean_val > 100:
                    _log(f"  ├ [AUTO-CORRECT] Anomali D50 terdeteksi (Mean: {mean_val:.1f} > 100). Asumsi satuan mikrometer (µm).")
                    _log("  ├ Mengonversi µm -> mm -> m, lalu mengkalkulasi ks (2.5D)...")
                    vals = (vals / 1000000.0) * 2.5
                elif mean_val < 0.01:
                    _log("  ├ [AUTO-CORRECT] D50 terdeteksi dalam satuan meter (m). Mengkalkulasi ks (2.5D)...")
                    vals = vals * 2.5
                else:
                    _log("  ├ [AUTO-CORRECT] D50 terdeteksi dalam satuan milimeter (mm). Mengkalkulasi ks (2.5D)...")
                    vals = (vals / 1000.0) * 2.5 
                
            # 3. EPSG Translation (WGS84 -> Target EPSG)
            try:
                # always_xy=True memastikan input format (Lon, Lat) konsisten
                tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            except Exception as e:
                raise ValueError(f"Kode EPSG tidak valid atau tidak dikenali: {epsg}") from e
                
            ux, uy = tr.transform(df_clean[col_x].values, df_clean[col_y].values)
            
            # 4. RAM OOM GUARD: Dynamic Grid Bounding Box creation (+2km padding)
            x_min, x_max = np.min(ux) - 2000, np.max(ux) + 2000
            y_min, y_max = np.min(uy) - 2000, np.max(uy) + 2000
            
            step = 50.0
            # Mencegah pembuatan grid lebih dari 4 Juta titik (Batas aman RAM standar 16GB)
            while ((x_max - x_min) / step) * ((y_max - y_min) / step) > 4000000:
                step += 25.0
                
            if step > 50.0:
                _log(f"  ├ [OOM GUARD] Area terlalu luas. Resolusi grid diturunkan ke {int(step)}m untuk mencegah Crash RAM.")
            
            gx, gy = np.mgrid[x_min:x_max:step, y_min:y_max:step]
            
            # 5. Delaunay Interpolation
            _log("  ├ Menjalankan algoritma interpolasi Delaunay (Linear)...")
            gz = griddata(np.column_stack((ux, uy)), vals, (gx, gy), method='linear')
            
            # Nearest neighbor fallback for NaNs on the perimeter (Ekstrapolasi)
            if np.isnan(gz).any(): 
                _log("  ├ Menambal area kosong (Perimeter) dengan Nearest Neighbor Fallback...")
                nan_mask = np.isnan(gz)
                gz[nan_mask] = griddata(np.column_stack((ux, uy)), vals, (gx[nan_mask], gy[nan_mask]), method='nearest')
                
            # 6. File I/O Safety & Export Logic
            # Menggunakan jalur absolut yang aman dari root cwd
            out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))
            os.makedirs(out_dir, exist_ok=True)
            
            prefix_mapping = {
                'sediment': "Sediment_Roughness",
                'mangrove': "Mangrove_Friction",
                'submerged': "Submerged_Ecosystem"
            }
            filename_prefix = prefix_mapping.get(mode_type, 'Spatial_Data')
            out_xyz = os.path.join(out_dir, f"{filename_prefix}.xyz")
            
            _log(f"  ├ Menulis matriks spasial ke format Delft3D XYZ -> {os.path.basename(out_xyz)}")
            
            # Formating ekspor ketat 3 desimal untuk efisiensi parsing mesin C++ Delft3D
            df_export = pd.DataFrame({'X': gx.flatten(), 'Y': gy.flatten(), 'Z': gz.flatten()})
            df_export.dropna().to_csv(out_xyz, sep=' ', header=False, index=False, float_format='%.3f')
            
            # 7. Safe Matplotlib Rendering (Strict Memory Leak Prevention)
            _log("  ├ Merender Heatmap Visualisasi...")
            p_path = os.path.join(out_dir, f"{mode_type}_heatmap.png")
            fig = None
            
            try:
                fig, ax = plt.subplots(figsize=(6, 5))
                fig.patch.set_facecolor('#0B0F19')
                ax.set_facecolor('#030712')
                
                cmap_choice = 'copper'
                label_text = 'Friction (ks)'
                title_text = 'Distribusi Sedimen Dasar Laut'
                
                if mode_type == 'mangrove':
                    cmap_choice = 'Greens'
                    label_text = 'Densitas (n/m2)'
                    title_text = 'Distribusi Vegetasi Mangrove'
                elif mode_type == 'submerged':
                    cmap_choice = 'GnBu'
                    label_text = 'Densitas (n/m2)'
                    title_text = 'Distribusi Submerged Vegetation'
                    
                sc = ax.scatter(gx.flatten(), gy.flatten(), c=gz.flatten(), cmap=cmap_choice, s=5)
                # Mark observasi dengan outline putih kontras
                ax.scatter(ux, uy, c='#EF4444', s=20, edgecolors='white', linewidths=0.5, label='Titik Survei')
                
                cb = plt.colorbar(sc, ax=ax)
                cb.set_label(label_text, color='w')
                cb.ax.yaxis.set_tick_params(color='w')
                plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color='w')
                
                ax.set_title(title_text, color='w', fontweight='bold', pad=15)
                ax.tick_params(colors='w')
                ax.grid(True, color='#1E293B', linestyle=':', alpha=0.7)
                ax.legend(facecolor='#020617', edgecolor='#1E293B', labelcolor='w')
                
                plt.tight_layout()
                plt.savefig(p_path, dpi=120)
                
            finally:
                # GUARANTEED cleanup: Memutus referensi dan membersihkan frame buffer OS
                if fig is not None:
                    fig.clear()
                    plt.close(fig)
            
            return p_path, out_xyz
            
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan komputasi spasial ({mode_type}): {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            # Exception Chaining untuk debugging
            raise RuntimeError(f"Gagal memproses interpolasi spasial: {str(e)}") from e
