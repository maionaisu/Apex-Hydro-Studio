# ==============================================================================
# APEX NEXUS TIER-0: SPATIAL SEDIMENT WORKER (QThread)
# ==============================================================================
import logging
import traceback
from PyQt6.QtCore import QThread, pyqtSignal
from engines.sediment_mapper import SpatialSedimentEngine

logger = logging.getLogger(__name__)

class SedimentWorker(QThread):
    """
    [TIER-0] Background Worker for Spatial Interpolation of Sediment/Mangrove fields.
    Delegates heavy Delaunay processing to the hardened SpatialSedimentEngine.
    """
    log_signal = pyqtSignal(str)
    plot_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, df, col_x, col_y, col_val, convert_ks, mode_type, epsg):
        super().__init__()
        self.df = df
        self.col_x = col_x
        self.col_y = col_y
        self.col_val = col_val
        self.convert_ks = convert_ks
        self.mode_type = mode_type # 'sediment', 'mangrove', 'submerged'
        self.epsg = epsg

    def run(self) -> None:
        try:
            self.log_signal.emit("■ Inisiasi Ekstraksi & Interpolasi Spasial Aktif...")
            
            if self.mode_type == 'mangrove':
                self.log_signal.emit("  ├ Mode Mangrove: Distribusi spasial densitas Trachytope.")
            elif self.mode_type == 'submerged':
                self.log_signal.emit("  ├ Mode Submerged Vegetation: Distribusi ekosistem bawah laut (Lamun/Karang).")
            else:
                if self.convert_ks:
                    self.log_signal.emit("  ├ Sedimen: Satuan ditransformasi ke Nikuradse (ks=2.5D).")
                else:
                    self.log_signal.emit("  ├ Sedimen: Memproses data matriks spasial Native.")
            
            # Failsafe Guard: Mencegah Engine memproses DataFrame kosong
            if self.df is None or self.df.empty:
                raise ValueError("DataFrame survei dari UI kosong atau tidak terdefinisi.")
                
            # Handoff ke Tier-0 Engine
            plot_path, xyz_path = SpatialSedimentEngine.process_and_interpolate(
                self.df, self.col_x, self.col_y, self.col_val, self.epsg, self.mode_type, self.convert_ks
            )
            
            logger.info(f"[SEDIMENT WORKER] Interpolation successful. Exported to: {xyz_path}")
            self.log_signal.emit(f"✅ Interpolasi Delaunay sukses. Target XYZ: {xyz_path}")
            
            # Transmit sinyal rendering gambar & hasil XYZ ke UI Event Loop
            self.plot_signal.emit(plot_path)
            self.finished_signal.emit(xyz_path)
            
        except Exception as e:
            # Memisahkan traceback panjang (dikirim ke backend log) dari pesan UI yang bersih
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL] Sediment Worker Error: {error_details}")
            
            self.log_signal.emit(f"❌ Error Interpolasi Spasial: {str(e)}")
            self.finished_signal.emit("")
