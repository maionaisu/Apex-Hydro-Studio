import base64
from PyQt6.QtCore import QThread, pyqtSignal
from engines.postproc_engine import PostProcEngine
import traceback

class PostProcAnimationWorker(QThread):
    log_signal = pyqtSignal(str)
    frame_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(bool)

    def __init__(self, nc_path, target_var, time_idx, epsg, out_dir):
        super().__init__()
        self.nc = nc_path
        self.var = target_var
        self.idx = time_idx
        self.epsg = epsg
        self.out = out_dir

    def run(self):
        try:
            self.log_signal.emit(f"■ Merender Frame Interpolasi Dinamis T={self.idx} untuk matriks '{self.var}'...")
            res = PostProcEngine.render_overlay(self.nc, self.var, self.idx, self.epsg, self.out)
            
            # Convert image to base64 to bypass Qt WebEngine local file restrictions
            with open(res['image_path'], "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            res['base64_img'] = f"data:image/png;base64,{encoded_string}"
            
            self.frame_signal.emit(res)
            self.finished_signal.emit(True)
            
        except Exception as e:
            self.log_signal.emit(f"❌ Error PostProc: {e}\n{traceback.format_exc()}")
            self.finished_signal.emit(False)
