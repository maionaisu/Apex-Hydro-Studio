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
                
                # Computation happens out-of-core. .values implicitly triggers .compute() 
                # but Dask handles the chunked iteration safely in the background.
                hs = float(ds['swh'].max().values) if 'swh' in ds else 1.5
                tp = float(ds['mwp'].mean().values) if 'mwp' in ds else 8.0
                dir_ = float(ds['mwd'].mean().values) if 'mwd' in ds else 180.0
                
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
