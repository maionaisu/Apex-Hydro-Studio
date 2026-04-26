# ==============================================================================
# APEX NEXUS TIER-0: MESH & DIMR ORCHESTRATION WORKER (QThread)
# ==============================================================================
import os
import copy
import logging
import traceback
from PyQt6.QtCore import QThread, pyqtSignal
from engines.mesh_builder import DepthProfileEngine, MeshBuilderEngine

logger = logging.getLogger(__name__)

class DepthOfClosure2DWorker(QThread):
    """
    [TIER-0] Background Worker for 2D Cross-Section Morphodynamics.
    Calculates Hallermeier/Birkemeier limits and generates visual spatial profiles.
    """
    log_signal = pyqtSignal(str)
    plot_signal = pyqtSignal(str)
    doc_val_signal = pyqtSignal(float)
    finished_signal = pyqtSignal(bool)

    def __init__(self, bathy_file, transect_pts, he, epsg):
        super().__init__()
        self.bathy_file = bathy_file
        # Strict copy to avoid UI thread race condition
        self.transect_pts = copy.deepcopy(transect_pts) if transect_pts else []
        self.he = he
        self.epsg = epsg

    def run(self) -> None:
        try:
            self.log_signal.emit("■ Mengkalkulasi 2D Cross-Section Morphodynamics & DoC...")
            
            he_val = float(self.he)
            doc_depth = -1.57 * he_val
            
            self.log_signal.emit(f"  ├ Limit DoC (Hallermeier/Birkemeier): {doc_depth:.2f} m")
            
            plot_path = DepthProfileEngine.calculate_doc_profile(
                self.bathy_file, self.transect_pts, doc_depth, self.epsg
            )
            
            logger.info("[MESH WORKER] 2D Cross-Section berhasil digenerate.")
            self.log_signal.emit("✅ Render 2D Cross Section Selesai (Academic Theme).")
            
            self.plot_signal.emit(plot_path)
            self.doc_val_signal.emit(abs(doc_depth))
            self.finished_signal.emit(True)
            
        except Exception as e:
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL] DoC Worker Error: {error_details}")
            
            self.log_signal.emit(f"❌ Error Kalkulasi DoC: {str(e)}")
            self.plot_signal.emit("")
            self.finished_signal.emit(False)


class ApexDIMROrchestratorWorker(QThread):
    """
    [TIER-0] The Master Background Worker.
    Orchestrates MeshKernel Adaptive Refinement, Delft3D-FM, and SWAN coupling operations.
    Safe state dict isolation.
    """
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str, bool)
    preview_signal = pyqtSignal(str) 

    def __init__(self, params: dict, global_state: dict):
        super().__init__()
        # Isolated references
        self.params = copy.deepcopy(params) if params else {}
        self.state = copy.deepcopy(global_state) if global_state else {}

    def run(self) -> None:
        try:
            b_mode = self.params.get('build_mode', 'coupled')
            
            if b_mode == 'dflow_only':
                self.log_signal.emit("■ Inisiasi Pipeline MeshKernel untuk D-FLOW (MDU Standalone)...")
            elif b_mode == 'dwaves_only':
                self.log_signal.emit("■ Inisiasi Pipeline MeshKernel untuk D-WAVES (MDW Standalone)...")
            else:
                self.log_signal.emit("■ Inisiasi Pipeline MeshKernel (Full Coupling DIMR)...")
            
            # Panggilan aman ke Engine
            MeshBuilderEngine.build_dimr_orchestration(
                params=self.params,
                global_state=self.state,
                progress_cb=self.progress_signal.emit,
                log_cb=self.log_signal.emit,
                preview_cb=self.preview_signal.emit
            )
            
            if b_mode == 'dflow_only':
                msg = "Arsitektur D-FLOW (MDU & Ext) berhasil dirakit."
            elif b_mode == 'dwaves_only':
                msg = "Arsitektur D-WAVES (MDW) berhasil dirakit."
            else:
                msg = "Seluruh model Coupling (MDU, MDW, XML, EXT) berhasil dirakit."
                
            logger.info(f"[DIMR ORCHESTRATOR] {msg}")
            self.finished_signal.emit(msg, True)
            
        except ImportError as e:
            logger.error(f"[FATAL] Missing Environment Library: {str(e)}")
            self.log_signal.emit(f"❌ [FATAL] Pustaka sistem tidak lengkap: {str(e)}")
            self.finished_signal.emit("Error", False)
            
        except Exception as e:
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL] DIMR Orchestrator Gagal: {error_details}")
            
            self.log_signal.emit(f"\n❌ [ERROR FATAL] Sistem Gagal Melakukan Build: {str(e)}")
            self.log_signal.emit("Silakan periksa log aplikasi atau spesifikasi input Anda.")
            self.finished_signal.emit("Error", False)
