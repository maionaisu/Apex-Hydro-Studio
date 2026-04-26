# ==============================================================================
# APEX NEXUS TIER-0: TIDAL HARMONIC WORKERS (QThread)
# ==============================================================================
import os
import logging
import traceback
import copy
import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal

from engines.tide_lsha import TideAnalyzerEngine

logger = logging.getLogger(__name__)

class TideAnalyzerWorker(QThread):
    """
    [TIER-0] Background Worker for Tidal Harmonic Extraction.
    Delegates heavy LSHA matrix computation to the optimized TideAnalyzerEngine.
    Thread-safe data isolation implemented.
    """
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame, col_time: str, col_z: str):
        super().__init__()
        # [CRITICAL GUARD]: Deep copy untuk mencegah Race Condition dengan UI Thread
        self.df = df.copy() if df is not None else None
        self.col_time = col_time
        self.col_z = col_z

    def run(self) -> None:
        try:
            self.log_signal.emit("■ Inisiasi Ekstraksi Least Squares Harmonic Analysis (LSHA)...")
            
            if self.df is None or self.df.empty:
                raise ValueError("DataFrame observasi dari UI kosong atau tidak terdefinisi.")
            
            # Panggilan ke engine fisika Tier-0
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
            self.finished_signal.emit("ERROR")


class TideGeneratorWorker(QThread):
    """
    [TIER-0] Background Worker for generating DELFT3D-FM Astronomic Boundary files (.bc).
    """
    finished_signal = pyqtSignal(str)

    def __init__(self, constituents: dict, out_dir: str, t_start: str, t_end: str):
        super().__init__()
        self.constituents = copy.deepcopy(constituents) if constituents else {}
        self.out_dir = os.path.abspath(out_dir)
        self.t_start = t_start
        self.t_end = t_end

    def run(self) -> None:
        try:
            if not self.constituents:
                raise ValueError("Kamus parameter konstanta harmonik kosong. Jalankan LSHA terlebih dahulu.")
                
            if not os.path.exists(self.out_dir): 
                os.makedirs(self.out_dir, exist_ok=True)
                
            bc_file = os.path.join(self.out_dir, "apex_forcing.bc")
            
            with open(bc_file, "w", encoding="utf-8") as f:
                f.write(f"# APEX NEXUS TIER-0 FORCING METADATA\n")
                f.write(f"# SIMULATION TIME WINDOW: {self.t_start} TO {self.t_end}\n")
                f.write(f"# BOUNDARY TYPE: ASTRONOMIC GENERATED VIA LSHA\n\n")
                
                f.write("[forcing]\n")
                f.write("Name                            = South_Ocean_Boundary\n")
                f.write("Function                        = astronomic\n")
                f.write("Quantity                        = astronomic component\n")
                f.write("Unit                            = m\n")
                
                for const, values in self.constituents.items():
                    amp = float(values['amp'])
                    pha = float(values['pha'])
                    
                    if amp > 0.0001: 
                        f.write(f"{const.ljust(4)} {amp:.6f}  {pha:.2f}\n")
                        
            logger.info(f"[TIDE WORKER] Boundary Condition (.bc) file generated: {bc_file}")
            self.finished_signal.emit(bc_file)
            
        except Exception as e: 
            logger.error(f"[FATAL] Tide Generator Worker Error: {str(e)}\n{traceback.format_exc()}")
            self.finished_signal.emit("")
