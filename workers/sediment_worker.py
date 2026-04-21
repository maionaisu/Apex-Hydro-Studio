from PyQt6.QtCore import QThread, pyqtSignal
from engines.sediment_mapper import SpatialSedimentEngine
import traceback

class SedimentWorker(QThread):
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

    def run(self):
        try:
            self.log_signal.emit("■ Interpolasi Spasial Aktif...")
            
            if self.mode_type == 'mangrove':
                self.log_signal.emit("  ├ Mode Mangrove: Distribusi spasial densitas Trachytope.")
            elif self.mode_type == 'submerged':
                self.log_signal.emit("  ├ Mode Submerged Vegetation: Distribusi ekosistem bawah laut (Lamun/Karang).")
            else:
                if self.convert_ks:
                    self.log_signal.emit("  ├ Sedimen: Satuan ditransformasi ke Nikuradse (ks=2.5D).")
                else:
                    self.log_signal.emit("  ├ Sedimen: Memproses data matriks spasial Native.")
                    
            plot_path, xyz_path = SpatialSedimentEngine.process_and_interpolate(
                self.df, self.col_x, self.col_y, self.col_val, self.epsg, self.mode_type, self.convert_ks
            )
            
            self.log_signal.emit(f"✅ Interpolasi Delaunay sukses. Target XYZ: {xyz_path}")
            self.plot_signal.emit(plot_path)
            self.finished_signal.emit(xyz_path)
            
        except Exception as e:
            self.log_signal.emit(f"❌ Error Interpolasi Spasial: {e}\n{traceback.format_exc()}")
            self.finished_signal.emit("")
