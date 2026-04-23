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
