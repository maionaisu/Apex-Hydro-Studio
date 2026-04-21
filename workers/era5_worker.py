import os
try:
    import cdsapi
    HAS_CDSAPI = True
except ImportError:
    HAS_CDSAPI = False

from PyQt6.QtCore import QThread, pyqtSignal

class ERA5DownloaderWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, api_key, bounds, params, d_start, d_end, out_file):
        super().__init__()
        self.api_key = api_key
        self.bounds = bounds
        self.params = params
        self.d_start = d_start
        self.d_end = d_end
        self.out_file = out_file

    def run(self):
        if not HAS_CDSAPI: 
            self.log_signal.emit("❌ Library 'cdsapi' missing.")
            self.finished_signal.emit(False, "")
            return
            
        try:
            self.log_signal.emit("■ Menginisiasi otentikasi Copernicus CDS API...")
            os.environ["CDSAPI_URL"] = "https://cds.climate.copernicus.eu/api/v2"
            os.environ["CDSAPI_KEY"] = self.api_key
            c = cdsapi.Client()
            
            years = list(set([str(y) for y in range(self.d_start.date().year(), self.d_end.date().year() + 1)]))
            
            if self.d_start.date().year() == self.d_end.date().year():
                months = list(set([f"{m:02d}" for m in range(self.d_start.date().month(), self.d_end.date().month() + 1)]))
            else:
                months = list(set([f"{m:02d}" for m in range(1, 13)]))
                
            days = [f"{d:02d}" for d in range(1, 32)]
            times = ["00:00", "06:00", "12:00", "18:00"]
            
            req = { 
                "product_type": "reanalysis", 
                "variable": self.params, 
                "year": years, 
                "month": months, 
                "day": days, 
                "time": times, 
                "area": [self.bounds['N'], self.bounds['W'], self.bounds['S'], self.bounds['E']], 
                "format": "netcdf" 
            }
            
            self.log_signal.emit(f"■ Downloading data range {self.d_start.toString('yyyy-MM-dd')} s/d {self.d_end.toString('yyyy-MM-dd')}...")
            c.retrieve("reanalysis-era5-single-levels", req, self.out_file)
            
            self.log_signal.emit(f"✅ Download Sukses: {self.out_file}")
            self.finished_signal.emit(True, self.out_file)
            
        except Exception as e: 
            self.log_signal.emit(f"❌ Error CDS: {e}")
            self.finished_signal.emit(False, "")
