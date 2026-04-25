# ==============================================================================
# APEX NEXUS TIER-0: ERA5 DOWNLOADER WORKER (QThread)
# ==============================================================================
import os
import logging
import traceback
import calendar
from datetime import datetime, timedelta
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# [ENTERPRISE GUARD]: Isolasi Pustaka Eksternal
try:
    import cdsapi
    HAS_CDSAPI = True
except ImportError:
    HAS_CDSAPI = False

class ERA5DownloaderWorker(QThread):
    """
    [TIER-0] Background Worker untuk mengunduh data iklim dari CDS Copernicus.
    Digabungkan (Merged) & Diperkeras (Hardened) dengan:
    1. Kompatibilitas CDS API v3 (Sistem UUID Baru).
    2. Eksekusi Thread-Safe (quiet=True) mencegah crash sys.stdout GUI.
    3. Auto-Buffer Geospasial (+0.5 Derajat) untuk mencegah Empty MARS Area.
    4. Sistem Pembersihan Mandiri (Clean-Up) untuk file .nc yang korup/gagal unduh.
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

    def run(self) -> None:
        """
        Dieksekusi di thread terpisah. Sama sekali tidak memanipulasi UI secara langsung.
        Mengisolasi kredensial API dengan aman untuk mencegah Race Condition.
        """
        if not HAS_CDSAPI:
            self.log_signal.emit("❌ [FATAL] Pustaka 'cdsapi' tidak ditemukan. Buka terminal dan jalankan: pip install cdsapi")
            self.finished_signal.emit(False, "")
            return

        try:
            self.log_signal.emit("■ Memverifikasi direktori output dan otentikasi CDS API...")
            
            # 1. Validasi Ketat Keamanan Direktori
            out_dir = os.path.dirname(self.out_file)
            if not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            
            self.log_signal.emit("■ Menginisiasi otentikasi CDS API v3 (Sistem UUID)...")
            
            # 2. Inisialisasi Klien API (Thread-Safe)
            # Parameter quiet=True mutlak diperlukan agar cdsapi tidak berusaha melakukan print
            # progress bar ke Terminal GUI yang bernilai None (Mencegah "NoneType object has no attribute write")
            c = cdsapi.Client(
                url="https://cds.climate.copernicus.eu/api",
                key=self.api_key,
                quiet=True, 
                verify=True
            )

            # 3. Solusi Spasial MARS: Mencegah "Empty area crop/mask"
            # ERA5 beresolusi ~27km (0.25 derajat). Membutuhkan buffer area agar piksel satelit tertangkap.
            N = float(self.bbox['N']) + 0.5
            S = float(self.bbox['S']) - 0.5
            E = float(self.bbox['E']) + 0.5
            W = float(self.bbox['W']) - 0.5
            
            # Area Format Copernicus CDS v3: [North, West, South, East]
            area_bounds = [N, W, S, E]
            
            self.log_signal.emit(f"  ├ [BUFFER SPASIAL] Batas satelit diperluas menjadi: N{N:.2f}, S{S:.2f}, E{E:.2f}, W{W:.2f}")

            # 4. Kompilasi Parameter Waktu
            years = list(set([str(y) for y in range(self.dt_start.year, self.dt_end.year + 1)]))
            
            if self.dt_start.year == self.dt_end.year:
                months = list(set([f"{m:02d}" for m in range(self.dt_start.month, self.dt_end.month + 1)]))
            else:
                months = [f"{m:02d}" for m in range(1, 13)]
                
            # Menghindari ralat hari dengan meminta penuh 31 hari. 
            # Server MARS cukup cerdas untuk mengabaikan tanggal tidak valid (seperti 31 Februari)
            days = [f"{d:02d}" for d in range(1, 32)]
            
            # Resolusi waktu 6-jam untuk menyeimbangkan presisi kalibrasi dan kecepatan unduh
            times = ["00:00", "06:00", "12:00", "18:00"]

            # 5. Perakitan Muatan Permintaan (Request Payload)
            req = {
                "product_type": ["reanalysis"],
                "variable": self.params,
                "year": years,
                "month": months,
                "day": days,
                "time": times,
                "area": area_bounds,
                "download_format": "unzipped_netcdf" # Format spesifik CDS API v3 agar tidak menjadi file .zip
            }
            
            str_start = self.dt_start.strftime('%Y-%m-%d')
            str_end = self.dt_end.strftime('%Y-%m-%d')
            self.log_signal.emit(f"■ Menghubungi server Copernicus MARS. Rentang: {str_start} s/d {str_end}...")
            self.log_signal.emit("⏳ Proses ini dapat memakan waktu 1-15 Menit tergantung antrean server (Queue).")
            
            logger.info(f"[ERA5] Memulai request CDS API. Payload: {req}")

            # 6. Eksekusi Permintaan API (Blocking call, aman di dalam QThread)
            c.retrieve("reanalysis-era5-single-levels", req, self.out_file)
            
            # Validasi integritas berkas pasca-unduh
            if not os.path.exists(self.out_file) or os.path.getsize(self.out_file) == 0:
                raise RuntimeError("File hasil unduhan dari CDS kosong atau gagal ditulis secara utuh ke disk.")
            
            self.log_signal.emit("✅ Ekstraksi Satelit Selesai. Data NetCDF berhasil diverifikasi dan disimpan.")
            self.finished_signal.emit(True, self.out_file)
            
        except Exception as e:
            # 7. SECURITY CLEAN-UP: Mencegah file NetCDF yang korup tersisa di memori penyimpanan
            if os.path.exists(self.out_file):
                try:
                    os.remove(self.out_file)
                    logger.debug(f"[ERA5] Membersihkan sisa file yang korup/tidak lengkap: {self.out_file}")
                except Exception as cleanup_err:
                    logger.warning(f"[ERA5] Gagal menghapus file sementara yang korup: {cleanup_err}")
            
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL CDS API] Kegagalan Komunikasi Satelit: {error_details}")
            self.log_signal.emit(f"❌ Kegagalan Koneksi/Sistem CDS MARS: {str(e)}")
            self.finished_signal.emit(False, "")
