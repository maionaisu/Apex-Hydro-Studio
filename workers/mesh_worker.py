from PyQt6.QtCore import QThread, pyqtSignal
from engines.mesh_builder import DepthProfileEngine, MeshBuilderEngine
import traceback

class DepthOfClosure2DWorker(QThread):
    log_signal = pyqtSignal(str)
    plot_signal = pyqtSignal(str)
    doc_val_signal = pyqtSignal(float)

    def __init__(self, bathy_file, transect_pts, he, epsg):
        super().__init__()
        self.bathy_file = bathy_file
        self.transect_pts = transect_pts
        self.he = he
        self.epsg = epsg

    def run(self):
        try:
            self.log_signal.emit("■ Mengkalkulasi 2D Cross-Section Morphodynamics & DoC...")
            doc_depth = -1.57 * self.he
            self.log_signal.emit(f"  ├ Limit DoC (Hallermeier/Birkemeier): {doc_depth:.2f} m")
            
            plot_path = DepthProfileEngine.calculate_doc_profile(
                self.bathy_file, self.transect_pts, doc_depth, self.epsg
            )
            
            self.log_signal.emit("✅ Render 2D Cross Section Selesai.")
            self.plot_signal.emit(plot_path)
            self.doc_val_signal.emit(abs(doc_depth))
            
        except Exception as e:
            self.log_signal.emit(f"❌ Error 2D Plot: {traceback.format_exc()}")


class ApexDIMROrchestratorWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str, bool)
    preview_signal = pyqtSignal(str) 

    def __init__(self, params, global_state):
        super().__init__()
        self.params = params
        self.state = global_state 

    def run(self):
        try:
            self.log_signal.emit("■ Inisiasi Pipeline MeshKernel (Unstructured Geometry)...")
            
            MeshBuilderEngine.build_dimr_orchestration(
                params=self.params,
                global_state=self.state,
                progress_cb=self.progress_signal.emit,
                log_cb=self.log_signal.emit,
                preview_cb=self.preview_signal.emit
            )
            
            self.finished_signal.emit("Success", True)
            
        except ImportError as e:
            self.log_signal.emit(f"❌ FATAL: {e}")
            self.finished_signal.emit("Error", False)
            
        except Exception as e:
            self.log_signal.emit(f"\n[ERROR FATAL] Sistem Gagal Melakukan Build:\n{traceback.format_exc()}")
            self.finished_signal.emit("Error", False)
