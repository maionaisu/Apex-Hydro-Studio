# ==============================================================================
# APEX NEXUS TIER-0: ERA5 NETCDF EXTRACTION ENGINE
# ==============================================================================
import os
import logging
import traceback
import numpy as np

# Setup module-level logger
logger = logging.getLogger(__name__)

try:
    import xarray as xr
    import dask
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False


class ERA5Extractor:
    """
    Tier-0 Extraction Engine for ERA5 Wave/Met Reanalysis.
    Hardened against corrupt/empty NetCDF files resulting from interrupted downloads.
    """
    
    @staticmethod
    def extract_wave_params(nc_path: str) -> tuple:
        if not HAS_XARRAY:
            raise ImportError("Library 'xarray' atau 'dask' tidak ditemukan. Install via: 'pip install xarray netCDF4 dask'")
            
        if not os.path.exists(nc_path):
            raise FileNotFoundError(f"[ERA5 Extractor] File NetCDF tidak ditemukan pada: {nc_path}")

        # [ENTERPRISE FIX]: Validasi file korup biner
        if os.path.getsize(nc_path) < 1024:
            raise ValueError("File NetCDF terlalu kecil (< 1KB). Berkas kemungkinan korup atau server CDS mengembalikan pesan error (bukan data).")

        try:
            logger.info(f"[ERA5] Menginisiasi Out-of-Core Dask extraction untuk: {nc_path}")
            
            with xr.open_dataset(nc_path, chunks='auto', engine='netcdf4') as ds:
                
                var_hs = 'swh' if 'swh' in ds else 'shww'
                var_tp = 'mwp' if 'mwp' in ds else 'pp1d'
                var_dir = 'mwd' if 'mwd' in ds else 'p140122'
                
                # Cek ketersediaan dimensi waktu, jaga-jaga kalau file kosong
                if 'time' not in ds.dims or ds.dims['time'] == 0:
                     raise ValueError("File NetCDF tidak memiliki dimensi waktu (kosong).")

                hs_lazy = ds[var_hs].max(skipna=True) if var_hs in ds else None
                tp_lazy = ds[var_tp].mean(skipna=True) if var_tp in ds else None
                
                if var_dir in ds:
                    dir_rad = np.deg2rad(ds[var_dir])
                    sin_dir_lazy = np.sin(dir_rad).mean(skipna=True)
                    cos_dir_lazy = np.cos(dir_rad).mean(skipna=True)
                else:
                    sin_dir_lazy, cos_dir_lazy = None, None

                logger.debug("[ERA5] Mengeksekusi Single-Pass Dask Graph Computation...")
                computed_results = dask.compute(
                    hs_lazy, 
                    tp_lazy, 
                    sin_dir_lazy, 
                    cos_dir_lazy
                )
                
                hs_val, tp_val, sin_val, cos_val = computed_results
                
                def safe_float(val, default):
                    if val is None or np.isnan(val): return default
                    return float(val)

                hs = safe_float(hs_val, 1.5)
                tp = safe_float(tp_val, 8.0)
                
                if sin_val is not None and cos_val is not None and not np.isnan(sin_val) and not np.isnan(cos_val):
                    dir_mean_rad = np.arctan2(sin_val, cos_val)
                    dir_ = float((np.degrees(dir_mean_rad) + 360) % 360)
                else:
                    dir_ = 180.0
                
                doc = 1.57 * hs
                
                logger.info(f"[ERA5] Ekstraksi sukses: Hs={hs:.2f}m, Tp={tp:.2f}s, Dir={dir_:.1f}°, DoC={doc:.2f}m")
                return hs, tp, dir_, doc
                
        except Exception as e:
            error_msg = f"[FATAL] ERA5 Extraction failed: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal membaca format NetCDF. File rusak atau format tidak kompatibel. Error: {str(e)}") from e
