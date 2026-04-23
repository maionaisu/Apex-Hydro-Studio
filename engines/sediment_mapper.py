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
    """
    @staticmethod
    def process_and_interpolate(df: pd.DataFrame, col_x: str, col_y: str, col_val: str, epsg: str, mode_type: str, apply_ks: bool = False) -> tuple:
        try:
            logger.info(f"[SEDIMENT] Memulai proses interpolasi spasial mode: {mode_type}")
            
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
            
            # 2. BUG-09 FIX: Nikuradse ks validation and transformation
            if mode_type == 'sediment' and apply_ks:
                # Cek anomali: Jika rata-rata D50 > 100, kemungkinan besar user memakai satuan mikrometer (µm)
                if vals.mean() > 100:
                    raise ValueError(
                        "Data D50 terdeteksi dalam satuan mikrometer (µm) atau bernilai tidak wajar (>100). "
                        "Algoritma Nikuradse D-Flow FM mengasumsikan input dalam milimeter (mm). "
                        "Harap perbaiki satuan data Anda sebelum memproses."
                    )
                # Asumsi D50 mm -> konversi ke m (/1000) lalu ke ks (*2.5)
                vals = (vals / 1000.0) * 2.5 
                
            # 3. EPSG Translation (WGS84 -> Target EPSG)
            try:
                # always_xy=True memastikan input format (Lon, Lat) konsisten
                tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            except Exception as e:
                raise ValueError(f"Kode EPSG tidak valid atau tidak dikenali: {epsg}") from e
                
            ux, uy = tr.transform(df_clean[col_x].values, df_clean[col_y].values)
            
            # 4. Grid Bounding Box creation (+2km padding for boundary condition safety)
            gx, gy = np.mgrid[np.min(ux)-2000:np.max(ux)+2000:50, np.min(uy)-2000:np.max(uy)+2000:50]
            
            # 5. Delaunay Interpolation
            logger.debug("[SEDIMENT] Menjalankan interpolasi linear griddata...")
            gz = griddata(np.column_stack((ux, uy)), vals, (gx, gy), method='linear')
            
            # Nearest neighbor fallback for NaNs on the perimeter (Ekstrapolasi)
            if np.isnan(gz).any(): 
                logger.debug("[SEDIMENT] Menambal NaN di perimeter dengan nearest neighbor fallback...")
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
            
            logger.info(f"[SEDIMENT] Mengekspor grid ke {out_xyz}")
            pd.DataFrame({'X': gx.flatten(), 'Y': gy.flatten(), 'Z': gz.flatten()}).to_csv(out_xyz, sep=' ', header=False, index=False)
            
            # 7. Safe Matplotlib Rendering (Memory Leak Prevention)
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
                ax.scatter(ux, uy, c='red', s=20, label='Titik Survei')
                
                cb = plt.colorbar(sc, ax=ax)
                cb.set_label(label_text, color='w')
                cb.ax.yaxis.set_tick_params(color='w')
                plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color='w')
                
                ax.set_title(title_text, color='w', fontweight='bold', pad=15)
                ax.tick_params(colors='w')
                ax.grid(True, color='#1E293B', linestyle=':', alpha=0.7)
                ax.legend(facecolor='#020617', labelcolor='w')
                
                plt.tight_layout()
                plt.savefig(p_path, dpi=120)
                logger.info(f"[SEDIMENT] Heatmap berhasil di-render: {p_path}")
                
            finally:
                # GUARANTEED cleanup: Figure akan selalu ditutup di memori bahkan jika terjadi error di ax.plot
                if fig is not None:
                    plt.close(fig)
            
            return p_path, out_xyz
            
        except Exception as e:
            error_msg = f"[FATAL] Kegagalan komputasi spasial ({mode_type}): {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            # Exception Chaining
            raise RuntimeError(f"Gagal memproses interpolasi spasial: {str(e)}") from e
