# ==============================================================================
# APEX NEXUS TIER-0: SPATIAL SEDIMENT WORKER (QThread)
# ==============================================================================
import logging
import traceback
import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal
from engines.sediment_mapper import SpatialSedimentEngine

logger = logging.getLogger(__name__)

class SedimentWorker(QThread):
    """
    [TIER-0] Background Worker for Spatial Interpolation of Sediment/Mangrove fields.
    Delegates heavy Kriging or Delaunay processing to the SpatialSedimentEngine.
    Thread-safe data isolation implemented to prevent Race Conditions.
    """
    log_signal = pyqtSignal(str)
    plot_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame, col_x: str, col_y: str, col_val: str, convert_ks: bool, mode_type: str, epsg: str, interp_method: str):
        super().__init__()
        # [CRITICAL GUARD]: Deep copy untuk isolasi memori mutlak dari UI Thread
        # Mencegah crash jika pengguna mengotak-atik UI saat proses spasial berjalan
        self.df = df.copy() if df is not None else None
        
        self.col_x = col_x
        self.col_y = col_y
        self.col_val = col_val
        self.convert_ks = convert_ks
        self.mode_type = mode_type # 'sediment', 'mangrove', 'submerged'
        self.epsg = epsg
        self.interp_method = interp_method

    def run(self) -> None:
        try:
            self.log_signal.emit("■ Inisiasi Ekstraksi & Interpolasi Spasial Aktif...")
            
            # [STRICT ROUTING]: Mencegah Miss-Logic jika mode_type tidak dikenali
            if self.mode_type == 'mangrove':
                self.log_signal.emit("  ├ Mode Mangrove: Distribusi spasial densitas Trachytope.")
            elif self.mode_type == 'submerged':
                self.log_signal.emit("  ├ Mode Submerged Vegetation: Distribusi ekosistem bawah laut (Lamun/Karang).")
            elif self.mode_type == 'sediment':
                if self.convert_ks:
                    self.log_signal.emit("  ├ Mode Sedimen: Transformasi D50 ke Nikuradse (ks=2.5D) Aktif.")
                else:
                    self.log_signal.emit("  ├ Mode Sedimen: Memproses data matriks spasial Native.")
            else:
                raise ValueError(f"Tipe mode '{self.mode_type}' tidak diizinkan oleh sistem.")
            
            # Failsafe Guard: Mencegah Engine memproses DataFrame kosong
            if self.df is None or self.df.empty:
                raise ValueError("DataFrame survei dari UI kosong atau tidak terdefinisi.")
                
            # [ENTERPRISE FIX]: Menyuntikkan log_cb agar log dari Engine bisa diteruskan ke UI Terminal
            # Serta menambahkan parsing parameter metode Kriging
            plot_path, xyz_path = SpatialSedimentEngine.process_and_interpolate(
                df=self.df, 
                col_x=self.col_x, 
                col_y=self.col_y, 
                col_val=self.col_val, 
                epsg=self.epsg, 
                mode_type=self.mode_type, 
                apply_ks=self.convert_ks,
                interp_method=self.interp_method,
                log_cb=self.log_signal.emit
            )
            
            logger.info(f"[SEDIMENT WORKER] Interpolation successful. Exported to: {xyz_path}")
            self.log_signal.emit(f"✅ Interpolasi {self.interp_method.split(' ')[0]} sukses. Target XYZ: {xyz_path}")
            
            # Transmit sinyal rendering gambar & hasil XYZ ke UI Event Loop
            self.plot_signal.emit(plot_path)
            self.finished_signal.emit(xyz_path)
            
        except Exception as e:
            # Memisahkan traceback panjang (dikirim ke backend log) dari pesan UI yang bersih
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL] Sediment Worker Error: {error_details}")
            
            self.log_signal.emit(f"❌ Error Interpolasi Spasial: {str(e)}")
            self.finished_signal.emit("")
