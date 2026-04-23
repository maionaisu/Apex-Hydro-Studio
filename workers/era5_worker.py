# ==============================================================================
# APEX NEXUS TIER-0: ERA5 DOWNLOADER WORKER (QThread)
# ==============================================================================
import os
import logging
import traceback
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

try:
    import cdsapi
    HAS_CDSAPI = True
except ImportError:
    HAS_CDSAPI = False

class ERA5DownloaderWorker(QThread):
    """
    [TIER-0] Background Worker for retrieving Copernicus ERA5 Data.
    Implements CDS API v3 compliance, strict I/O validation, and secure credential isolation.
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, api_key: str, bounds: dict, params: list, d_start, d_end, out_file: str):
        super().__init__()
        self.api_key = api_key
        self.bounds = bounds
        self.params = params
        self.d_start = d_start
        self.d_end = d_end
        self.out_file = os.path.abspath(out_file)

    def run(self) -> None:
        """
        Executed in a separate thread. Never manipulate UI directly from here.
        """
        if not HAS_CDSAPI: 
            self.log_signal.emit("❌ [FATAL] Library 'cdsapi' tidak ditemukan. Jalankan: pip install cdsapi")
            self.finished_signal.emit(False, "")
            return
            
        try:
            self.log_signal.emit("■ Memverifikasi direktori output dan otentikasi CDS API...")
            
            # 1. Strict File/Directory Safety
            out_dir = os.path.dirname(self.out_file)
            if not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            
            # 2. Secure Environment Injection (BUG-03 FIX: API v3 Endpoint)
            os.environ["CDSAPI_URL"] = "https://cds.climate.copernicus.eu/api"
            os.environ["CDSAPI_KEY"] = self.api_key
            
            # Matikan quiet mode agar pesan asli dari server CDS terekam di log terminal
            c = cdsapi.Client(quiet=False)
            
            # 3. Parameter Compilation
            years = list(set([str(y) for y in range(self.d_start.date().year(), self.d_end.date().year() + 1)]))
            
            if self.d_start.date().year() == self.d_end.date().year():
                months = list(set([f"{m:02d}" for m in range(self.d_start.date().month(), self.d_end.date().month() + 1)]))
            else:
                months = [f"{m:02d}" for m in range(1, 13)]
                
            days = [f"{d:02d}" for d in range(1, 32)]
            # Menyediakan resolusi waktu 6-jam untuk memperkecil ukuran file
            times = ["00:00", "06:00", "12:00", "18:00"]
            
            # BUG-03 FIX: Format request wajib mengikuti standar CDS v3 (download_format & list for product_type)
            req = { 
                "product_type": ["reanalysis"], 
                "variable": self.params, 
                "year": years, 
                "month": months, 
                "day": days, 
                "time": times, 
                "area": [
                    float(self.bounds['N']), 
                    float(self.bounds['W']), 
                    float(self.bounds['S']), 
                    float(self.bounds['E'])
                ], 
                "download_format": "unzipped_netcdf" 
            }
            
            self.log_signal.emit(f"■ Menghubungi server satelit Copernicus. Rentang: {self.d_start.toString('yyyy-MM-dd')} s/d {self.d_end.toString('yyyy-MM-dd')}...")
            logger.info(f"[ERA5] Memulai request CDS API. Payload: {req}")
            
            # 4. API Request Execution (Blocking call, safe in QThread)
            c.retrieve("reanalysis-era5-single-levels", req, self.out_file)
            
            if not os.path.exists(self.out_file) or os.path.getsize(self.out_file) == 0:
                raise RuntimeError("File hasil unduhan dari CDS kosong atau gagal ditulis ke disk.")
            
            self.log_signal.emit(f"✅ Unduhan Berhasil. Tersimpan di: {self.out_file}")
            self.finished_signal.emit(True, self.out_file)
            
        except Exception as e: 
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL] Kegagalan CDS API: {error_details}")
            self.log_signal.emit(f"❌ Kegagalan Koneksi/Sistem CDS: {str(e)}")
            self.finished_signal.emit(False, "")
            
        finally:
            # 5. Security Clean-up: Hapus jejak API Key pengguna dari memori global OS
            os.environ.pop("CDSAPI_URL", None)
            os.environ.pop("CDSAPI_KEY", None)
            logger.debug("[ERA5] Environment keys securely cleared.")
