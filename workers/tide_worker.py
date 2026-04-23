# ==============================================================================
# APEX NEXUS TIER-0: TIDAL HARMONIC WORKERS (QThread)
# ==============================================================================
import os
import logging
import traceback
from PyQt6.QtCore import QThread, pyqtSignal
from engines.tide_lsha import TideAnalyzerEngine

logger = logging.getLogger(__name__)

class TideAnalyzerWorker(QThread):
    """
    [TIER-0] Background Worker for Tidal Harmonic Extraction.
    Delegates heavy LSHA matrix computation to the optimized TideAnalyzerEngine.
    """
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(str)

    def __init__(self, df, col_time, col_z):
        super().__init__()
        self.df = df
        self.col_time = col_time
        self.col_z = col_z

    def run(self) -> None:
        try:
            self.log_signal.emit("■ Inisiasi Ekstraksi Least Squares Harmonic Analysis (LSHA)...")
            
            # Panggilan ke engine fisika Tier-0 (Aman dari Blocking UI)
            msl, constituents = TideAnalyzerEngine.extract_harmonics(self.df, self.col_time, self.col_z)
            
            self.log_signal.emit("■ Memecah Matriks Regresi Linear Inversi (SVD)...")
            self.log_signal.emit(f"  ├ MSL (Z0): {msl:.4f} m")
            
            for name, val in constituents.items():
                self.log_signal.emit(f"  ├ {name.ljust(3)} -> Amp: {val['amp']:.4f}m, Phase: {val['pha']:.2f}°")
                
            logger.info("[TIDE WORKER] LSHA Extraction successfully finished.")
            self.result_signal.emit(constituents)
            self.finished_signal.emit("SUCCESS")
            
        except Exception as e:
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL] Tide Analyzer Worker Error: {error_details}")
            self.log_signal.emit(f"❌ Error Analisis Pasut: {str(e)}")
            self.finished_signal.emit("")


class TideGeneratorWorker(QThread):
    """
    [TIER-0] Background Worker for generating DELFT3D-FM Astronomic Boundary files (.bc).
    """
    finished_signal = pyqtSignal(str)

    def __init__(self, constituents: dict, out_dir: str):
        super().__init__()
        self.constituents = constituents
        self.out_dir = os.path.abspath(out_dir)

    def run(self) -> None:
        try:
            # FIX: File I/O Safety (Mencegah FileExistsError jika folder sudah terbentuk)
            if not os.path.exists(self.out_dir): 
                os.makedirs(self.out_dir, exist_ok=True)
                
            bc_file = os.path.join(self.out_dir, "apex_forcing.bc")
            
            # FIX: Menambahkan encoding="utf-8" untuk mencegah korupsi format Windows
            with open(bc_file, "w", encoding="utf-8") as f:
                f.write("[forcing]\n")
                f.write("Name                            = South_Ocean_Boundary\n")
                f.write("Function                        = astronomic\n")
                f.write("Quantity                        = astronomic component\n")
                f.write("Unit                            = m\n")
                
                for const, values in self.constituents.items():
                    amp = float(values['amp'])
                    pha = float(values['pha'])
                    
                    # Menyaring amplitudo mikroskopis (noise) agar efisien dibaca Delft3D-FM
                    if amp > 0.0001: 
                        f.write(f"{const.ljust(4)} {amp:.6f}  {pha:.2f}\n")
                        
            logger.info(f"[TIDE WORKER] Boundary Condition (.bc) file generated: {bc_file}")
            self.finished_signal.emit(bc_file)
            
        except Exception as e: 
            # FIX: Menghapus bare `except:` dan menambahkan exception chaining log
            logger.error(f"[FATAL] Tide Generator Worker Error: {str(e)}\n{traceback.format_exc()}")
            self.finished_signal.emit("")
