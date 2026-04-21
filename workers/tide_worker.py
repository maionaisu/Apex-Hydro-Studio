import os
from PyQt6.QtCore import QThread, pyqtSignal
from engines.tide_lsha import TideAnalyzerEngine

class TideAnalyzerWorker(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(str)

    def __init__(self, df, col_time, col_z):
        super().__init__()
        self.df = df
        self.col_time = col_time
        self.col_z = col_z

    def run(self):
        try:
            self.log_signal.emit("■ Inisiasi Ekstraksi Least Squares Harmonic Analysis (LSHA)...")
            
            msl, constituents = TideAnalyzerEngine.extract_harmonics(self.df, self.col_time, self.col_z)
            
            self.log_signal.emit("■ Memecah Matriks Regresi Linear Inversi (SVD)...")
            self.log_signal.emit(f"  ├ MSL (Z0): {msl:.4f} m")
            
            for name, val in constituents.items():
                self.log_signal.emit(f"  ├ {name.ljust(3)} -> Amp: {val['amp']:.4f}m, Phase: {val['pha']:.2f}°")
                
            self.result_signal.emit(constituents)
            self.finished_signal.emit("SUCCESS")
            
        except Exception as e:
            self.log_signal.emit(f"❌ Error Analisis Pasut: {e}")
            self.finished_signal.emit("")


class TideGeneratorWorker(QThread):
    finished_signal = pyqtSignal(str)

    def __init__(self, constituents, out_dir):
        super().__init__()
        self.constituents = constituents
        self.out_dir = out_dir

    def run(self):
        if not os.path.exists(self.out_dir): 
            os.makedirs(self.out_dir)
            
        bc_file = os.path.join(self.out_dir, "apex_forcing.bc")
        
        try:
            with open(bc_file, "w") as f:
                f.write("[forcing]\n")
                f.write("Name                            = South_Ocean_Boundary_0001\n")
                f.write("Function                        = astronomic\n")
                f.write("Quantity                        = astronomic component\n")
                f.write("Unit                            = m\n")
                
                for const, values in self.constituents.items():
                    amp = float(values['amp'])
                    pha = float(values['pha'])
                    if amp > 0.0001: 
                        f.write(f"{const.ljust(4)} {amp:.6f}  {pha:.2f}\n")
                        
            self.finished_signal.emit(bc_file)
        except Exception: 
            self.finished_signal.emit("")
