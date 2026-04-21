try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False

class ERA5Extractor:
    @staticmethod
    def extract_wave_params(nc_path):
        """
        Extracts Hs, Tp, Dir and calculates DoC limit based on Hallermeier/Birkemeier.
        Out-of-Core Processing: Explicit clean-up guaranteed using 'with' block.
        """
        if not HAS_XARRAY:
            raise ImportError("xarray library is missing. 'pip install xarray netCDF4'")
            
        with xr.open_dataset(nc_path) as ds:
            hs = float(ds['swh'].max().values) if 'swh' in ds else 1.5
            tp = float(ds['mwp'].mean().values) if 'mwp' in ds else 8.0
            dir_ = float(ds['mwd'].mean().values) if 'mwd' in ds else 180.0
            
            # Simple DoC estimation
            doc = 1.57 * hs
            
            return hs, tp, dir_, doc
