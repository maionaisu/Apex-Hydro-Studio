import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from pyproj import Transformer
try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False

matplotlib.use('Agg')

class PostProcEngine:
    @staticmethod
    def render_overlay(nc_path, target_var, time_idx, epsg, out_dir):
        if not HAS_XARRAY: 
            raise ImportError("Library xarray diperlukan untuk post-processing.")
            
        with xr.open_dataset(nc_path) as ds:
            # Detect Coordinates Type of DFM or SWAN
            if 'mesh2d_face_x' in ds:
                ux = ds['mesh2d_face_x'].values
                uy = ds['mesh2d_face_y'].values
            elif 'mesh2d_node_x' in ds:
                ux = ds['mesh2d_node_x'].values
                uy = ds['mesh2d_node_y'].values
            else:
                # If SWAN uses gridded
                if 'x' in ds and 'y' in ds:
                    X, Y = np.meshgrid(ds.x.values, ds.y.values)
                    ux, uy = X.flatten(), Y.flatten()
                else:
                    raise KeyError("Tidak menemukan node geometri X/Y di dalam NetCDF.")

            # Grab Values
            num_time_steps = len(ds.time)
            
            if target_var in ds:
                # Handling multidimension if time exists
                var_data = ds[target_var]
                if 'time' in var_data.dims:
                    vals = var_data.isel(time=time_idx).values.flatten()
                else:
                    vals = var_data.values.flatten()
            else:
                raise KeyError(f"Variabel {target_var} tidak ditemukan di NetCDF.")
            
            # Mask NaNs
            valid_mask = ~np.isnan(vals)
            ux = ux[valid_mask]
            uy = uy[valid_mask]
            vals = vals[valid_mask]
            
            if len(ux) == 0:
                raise ValueError("Data frame saat ini kosong atau seluruhnya NaN.")
                
            # EPSG Translate to LatLon for Leaflet bounds
            tr = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
            lon, lat = tr.transform(ux, uy)
            
            w, e, s, n = lon.min(), lon.max(), lat.min(), lat.max()

            # Plot purely the transparent heatmap image
            fig = plt.figure(figsize=(10, 10), frameon=False)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.axis('off')
            
            v_min, v_max = float(np.percentile(vals, 2)), float(np.percentile(vals, 98))
            
            # Colormaps based on typical physics parameter
            cmap_choice = 'jet'
            if 'Hs' in target_var or 'SWH' in target_var: cmap_choice = 'ocean_r'
            if 'ucy' in target_var or 'ucx' in target_var: cmap_choice = 'twilight'
            if 'sed' in target_var or 'bed' in target_var: cmap_choice = 'copper'
            
            sc = ax.scatter(lon, lat, c=vals, cmap=cmap_choice, s=8, alpha=0.85, vmin=v_min, vmax=v_max)
            ax.set_xlim(w, e)
            ax.set_ylim(s, n)
            
            out_img = os.path.join(out_dir, f"overlay_frame_{time_idx}.png")
            plt.savefig(out_img, transparent=True, pad_inches=0, bbox_inches='tight', dpi=200)
            plt.close(fig)
            
            time_str = str(ds.time.values[time_idx]) if ('time' in ds and len(ds.time) > time_idx) else 'Static Frame'
            return {
                'image_path': out_img,
                'bounds': {'N': float(n), 'S': float(s), 'E': float(e), 'W': float(w)},
                'time_str': time_str,
                'max_time': num_time_steps - 1,
                'v_min': v_min,
                'v_max': v_max
            }
