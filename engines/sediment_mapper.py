import os
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
import matplotlib
import matplotlib.pyplot as plt
from pyproj import Transformer

matplotlib.use('Agg')

class SpatialSedimentEngine:
    @staticmethod
    def process_and_interpolate(df, col_x, col_y, col_val, epsg, mode_type, apply_ks=False):
        """
        Engine for spatial interpolation of sediment, mangrove, and submerged vegetation.
        mode_type: 'sediment', 'mangrove', 'submerged'
        """
        # Clean data robustly: drop NaN in any relevant columns, then coerce numeric
        df_clean = df[[col_x, col_y, col_val]].copy()
        df_clean[col_val] = pd.to_numeric(df_clean[col_val], errors='coerce')
        df_clean = df_clean.dropna(subset=[col_x, col_y, col_val]).reset_index(drop=True)
        vals = df_clean[col_val].values
        
        # Apply Nikuradse ks transformation if requested
        if mode_type == 'sediment' and apply_ks:
            vals = (vals / 1000.0) * 2.5 # Assuming D50 is in mm, to meters then * 2.5
            
        # EPSG Translation
        tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        ux, uy = tr.transform(df_clean[col_x].values, df_clean[col_y].values)
        
        # Grid Bounding Box creation (+2km padding)
        gx, gy = np.mgrid[np.min(ux)-2000:np.max(ux)+2000:50, np.min(uy)-2000:np.max(uy)+2000:50]
        
        # Delaunay Interpolation
        gz = griddata(np.column_stack((ux, uy)), vals, (gx, gy), method='linear')
        
        # Nearest neighbor fallback for NaNs on the perimeter
        if np.isnan(gz).any(): 
            nan_mask = np.isnan(gz)
            gz[nan_mask] = griddata(np.column_stack((ux, uy)), vals, (gx[nan_mask], gy[nan_mask]), method='nearest')
            
        # Export logic
        out_dir = os.path.join(os.getcwd(), 'Apex_Data_Exports')
        os.makedirs(out_dir, exist_ok=True)
        
        prefix_mapping = {
            'sediment': "Sediment_Roughness",
            'mangrove': "Mangrove_Friction",
            'submerged': "Submerged_Ecosystem"
        }
        out_xyz = os.path.join(out_dir, f"{prefix_mapping.get(mode_type, 'Spatial_Data')}.xyz")
        pd.DataFrame({'X': gx.flatten(), 'Y': gy.flatten(), 'Z': gz.flatten()}).to_csv(out_xyz, sep=' ', header=False, index=False)
        
        # Rendering configuration
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
        
        p_path = os.path.join(out_dir, f"{mode_type}_heatmap.png")
        plt.tight_layout()
        plt.savefig(p_path, dpi=120)
        plt.close(fig)
        
        return p_path, out_xyz
