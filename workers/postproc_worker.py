# ==============================================================================
# APEX NEXUS TIER-0: POST-PROCESSING ANIMATION WORKER (QThread)
# ==============================================================================
import os
import base64
import logging
import traceback
from PyQt6.QtCore import QThread, pyqtSignal
from engines.postproc_engine import PostProcEngine

logger = logging.getLogger(__name__)

class PostProcAnimationWorker(QThread):
    """
    [TIER-0] Background Worker for Dynamic NetCDF Rendering.
    Generates Base64 encoded transparent overlays for immediate injection
    into Leaflet QWebEngineView (bypassing local CORS restrictions).
    """
    log_signal = pyqtSignal(str)
    frame_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(bool)

    def __init__(self, nc_path: str, target_var: str, time_idx: int, epsg: str, out_dir: str):
        super().__init__()
        # FIX: Enforce absolute paths for IO security
        self.nc = os.path.abspath(nc_path)
        self.var = target_var
        self.idx = time_idx
        self.epsg = epsg
        self.out = os.path.abspath(out_dir)

    def run(self) -> None:
        try:
            self.log_signal.emit(f"■ Merender Frame Interpolasi Dinamis T={self.idx} untuk matriks '{self.var}'...")
            
            # Panggilan ke engine fisika Tier-0 (Aman dari Blocking UI)
            res = PostProcEngine.render_overlay(self.nc, self.var, self.idx, self.epsg, self.out)
            
            img_path = res.get('image_path')
            
            # Failsafe Guard: Memastikan file gambar benar-benar tercipta sebelum membacanya
            if not img_path or not os.path.exists(img_path):
                raise FileNotFoundError(f"Gagal memuat gambar render dari path: {img_path}")
            
            # Convert image to base64 to bypass Qt WebEngine local file/CORS restrictions
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            res['base64_img'] = f"data:image/png;base64,{encoded_string}"
            
            # Hapus path gambar asli dari output untuk mencegah konflik pemanggilan di JS
            res.pop('image_path', None)
            
            logger.debug(f"[POSTPROC WORKER] Frame T={self.idx} successfully rendered and encoded.")
            self.frame_signal.emit(res)
            self.finished_signal.emit(True)
            
        except Exception as e:
            # Memisahkan traceback panjang (dikirim ke backend log) dari pesan UI
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL] PostProc Worker Error: {error_details}")
            
            self.log_signal.emit(f"❌ Error Rendering Frame T={self.idx}: {str(e)}")
            self.finished_signal.emit(False)
