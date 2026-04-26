# ==============================================================================
# APEX NEXUS TIER-0: ERA5 DOWNLOADER WORKER (QThread)
# ==============================================================================
import os
import sys
import logging
import traceback
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# [ENTERPRISE GUARD]: Isolasi Pustaka Eksternal
try:
    import cdsapi
    HAS_CDSAPI = True
except ImportError:
    HAS_CDSAPI = False


class BlackholeStream:
    """
    [TIER-0 SAFEGUARD] Menelan semua output/print dari cdsapi & tqdm secara diam-diam.
    Menghancurkan bug mematikan: "NoneType object has no attribute 'write'" di dalam QThread PyQt.
    """
    def write(self, text):
        pass # Buang semua teks progress bar
        
    def flush(self):
        pass # Buang perintah flush


class ERA5DownloaderWorker(QThread):
    """
    [TIER-0] Background Worker untuk mengunduh data iklim dari CDS Copernicus.
    Hardened with:
    1. Stealth .cdsapirc Auto-generation (Like setup_cds.py).
    2. Blackhole Stream to prevent QThread sys.stdout crash.
    3. Old-School Payload compatibility ("data_format": "netcdf", "unarchived").
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, api_key: str, bbox: dict, params: list, dt_start, dt_end, out_file: str):
        super().__init__()
        self.api_key = api_key
        self.bbox = bbox
        self.params = params
        
        # Konversi fleksibel antara QDateTime (PyQt) dan Datetime standar Python
        if hasattr(dt_start, 'toPyDateTime'):
            self.dt_start = dt_start.toPyDateTime()
            self.dt_end = dt_end.toPyDateTime()
        else:
            self.dt_start = dt_start
            self.dt_end = dt_end
            
        self.out_file = os.path.abspath(out_file)

    def setup_cdsapirc(self):
        """Menduplikasi logika setup_cds.py lama milik user secara otomatis di background."""
        home_dir = os.path.expanduser("~")
        file_path = os.path.join(home_dir, ".cdsapirc")
        
        config_content = (
            "url: https://cds.climate.copernicus.eu/api\n"
            f"key: {self.api_key}\n"
        )
        
        with open(file_path, "w") as f:
            f.write(config_content)
            
        self.log_signal.emit("■ Kredensial CDS disuntikkan secara aman via ~/.cdsapirc")

    def run(self) -> None:
        if not HAS_CDSAPI:
            self.log_signal.emit("❌ [FATAL] Pustaka 'cdsapi' tidak ditemukan. Install via: pip install cdsapi")
            self.finished_signal.emit(False, "")
            return

        # [CRITICAL FIX]: Simpan state asli sys.stdout
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            self.log_signal.emit("■ Memverifikasi direktori output dan otentikasi...")
            
            out_dir = os.path.dirname(self.out_file)
            if not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            
            # 1. Eksekusi Setup CDS (seperti setup_cds.py lama)
            self.setup_cdsapirc()
            
            # 2. Pasang Perangkap Output (Blackhole) agar cdsapi tidak crash di UI Thread
            dummy_stream = BlackholeStream()
            sys.stdout = dummy_stream
            sys.stderr = dummy_stream

            # 3. Inisiasi Klien (kini otomatis membaca dari ~/.cdsapirc)
            c = cdsapi.Client(quiet=True, verify=True)

            # 4. Solusi Spasial MARS
            N = float(self.bbox['N'])
            S = float(self.bbox['S'])
            E = float(self.bbox['E'])
            W = float(self.bbox['W'])
            
            area_bounds = [N, W, S, E] # Format Copernicus CDS: [North, West, South, East]
            self.log_signal.emit(f"  ├ Batas satelit dieksekusi pada: N{N:.2f}, S{S:.2f}, E{E:.2f}, W{W:.2f}")

            # 5. Perakitan Parameter Waktu
            years = list(set([str(y) for y in range(self.dt_start.year, self.dt_end.year + 1)]))
            
            if self.dt_start.year == self.dt_end.year:
                months = list(set([f"{m:02d}" for m in range(self.dt_start.month, self.dt_end.month + 1)]))
            else:
                months = [f"{m:02d}" for m in range(1, 13)]
                
            days = [f"{d:02d}" for d in range(1, 32)]
            times = ["00:00", "06:00", "12:00", "18:00"]

            # 6. Perakitan Payload (Menduplikasi era5_download.py lama)
            req = {
                "product_type": ["reanalysis"],
                "variable": self.params,
                "year": years,
                "month": months,
                "day": days,
                "time": times,
                "area": area_bounds,
                "data_format": "netcdf",          # <--- Format sakti dari skrip lama
                "download_format": "unarchived"   # <--- Format sakti dari skrip lama
            }
            
            str_start = self.dt_start.strftime('%Y-%m-%d')
            str_end = self.dt_end.strftime('%Y-%m-%d')
            
            # Kembalikan stdout sejenak hanya untuk print log ke UI
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            self.log_signal.emit(f"■ Menghubungi server CDS. Rentang: {str_start} s/d {str_end}...")
            self.log_signal.emit("⏳ Estimasi waktu: 1-15 Menit. UI tetap responsif, harap bersabar.")
            
            # Matikan lagi stdout sebelum mengeksekusi unduhan yang berat
            sys.stdout = dummy_stream
            sys.stderr = dummy_stream
            
            logger.info(f"[ERA5] Payload: {req}")

            # 7. Eksekusi Unduhan
            c.retrieve("reanalysis-era5-single-levels", req, self.out_file)
            
            # Kembalikan terminal ke kondisi normal pasca-unduh
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            
            if not os.path.exists(self.out_file) or os.path.getsize(self.out_file) < 1000:
                raise RuntimeError("File NetCDF kosong atau gagal diunduh sempurna (< 1KB).")
            
            self.log_signal.emit("✅ Ekstraksi Satelit Selesai. NetCDF berhasil disimpan.")
            self.finished_signal.emit(True, self.out_file)
            
        except Exception as e:
            # Failsafe: Selalu kembalikan terminal jika terjadi error
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            
            if os.path.exists(self.out_file):
                try:
                    os.remove(self.out_file)
                except Exception:
                    pass
            
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL CDS API] Kegagalan Komunikasi: {error_details}")
            self.log_signal.emit(f"❌ Kegagalan Koneksi/Sistem CDS: {str(e)}")
            self.finished_signal.emit(False, "")
