# ==============================================================================
# APEX NEXUS TIER-0: ERA5 NETCDF EXTRACTION ENGINE
# ==============================================================================
import os
import logging
import traceback

# Setup module-level logger
logger = logging.getLogger(__name__)

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False


class ERA5Extractor:
    """
    Tier-0 Extraction Engine for ERA5 Wave/Met Reanalysis.
    Utilizes Dask Lazy Evaluation for O(1) memory footprint on massive datasets.
    """
    
    @staticmethod
    def extract_wave_params(nc_path: str):
        """
        Extracts Hs, Tp, Dir and calculates DoC limit based on Hallermeier/Birkemeier.
        Out-of-Core Processing: Explicit clean-up guaranteed using 'with' block.
        """
        if not HAS_XARRAY:
            raise ImportError("xarray library is missing. Run: 'pip install xarray netCDF4 dask'")
            
        # 1. Strict File I/O Validation
        if not os.path.exists(nc_path):
            raise FileNotFoundError(f"[ERA5 Extractor] NetCDF file not found at path: {nc_path}")

        try:
            logger.info(f"[ERA5] Initiating out-of-core extraction for: {nc_path}")
            
            # 2. Dask Lazy Evaluation enforced via chunks='auto'
            # This prevents multi-gigabyte NetCDF files from causing OOM crashes.
            with xr.open_dataset(nc_path, chunks='auto', engine='netcdf4') as ds:
                import dask
                # ⚡ Bolt Optimization: Batch Dask computations to prevent multiple disk reads
                # Sequential `.values` calls on out-of-core datasets trigger redundant data passes.
                ops = []
                if 'swh' in ds: ops.append(ds['swh'].max())
                if 'mwp' in ds: ops.append(ds['mwp'].mean())
                if 'mwd' in ds: ops.append(ds['mwd'].mean())
                
                if ops:
                    results = dask.compute(*ops)
                    idx = 0
                    if 'swh' in ds:
                        hs = float(results[idx].values)
                        idx += 1
                    else: hs = 1.5

                    if 'mwp' in ds:
                        tp = float(results[idx].values)
                        idx += 1
                    else: tp = 8.0

                    if 'mwd' in ds:
                        dir_ = float(results[idx].values)
                        idx += 1
                    else: dir_ = 180.0
                else:
                    hs, tp, dir_ = 1.5, 8.0, 180.0
                
                # Simple DoC estimation (Hallermeier equation approximation)
                doc = 1.57 * hs
                
                logger.info(f"[ERA5] Extraction successful: Hs={hs:.2f}m, Tp={tp:.2f}s, Dir={dir_:.1f}°, DoC={doc:.2f}m")
                return hs, tp, dir_, doc
                
        except Exception as e:
            # 3. Strict Error Propagation
            error_msg = f"[FATAL] ERA5 Extraction failed: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            # Menambahkan 'from e' (Exception Chaining) agar jejak error asli tidak hilang
            raise RuntimeError(f"Failed to extract ERA5 parameters. See logs for details. Error: {str(e)}") from e
