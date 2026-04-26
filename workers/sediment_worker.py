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
    Meneruskan parameter land_boundary file ke dalam Engine.
    """
    log_signal = pyqtSignal(str)
    plot_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame, col_x: str, col_y: str, col_val: str, convert_ks: bool, mode_type: str, epsg: str, interp_method: str, boundary_file: str = None):
        super().__init__()
        self.df = df.copy() if df is not None else None
        
        self.col_x = col_x
        self.col_y = col_y
        self.col_val = col_val
        self.convert_ks = convert_ks
        self.mode_type = mode_type
        self.epsg = epsg
        self.interp_method = interp_method
        self.boundary_file = boundary_file

    def run(self) -> None:
        try:
            self.log_signal.emit("■ Inisiasi Ekstraksi & Interpolasi Contours...")
            
            if self.df is None or self.df.empty:
                raise ValueError("DataFrame survei dari UI kosong atau tidak terdefinisi.")
                
            plot_path, xyz_path = SpatialSedimentEngine.process_and_interpolate(
                df=self.df, 
                col_x=self.col_x, 
                col_y=self.col_y, 
                col_val=self.col_val, 
                epsg=self.epsg, 
                mode_type=self.mode_type, 
                apply_ks=self.convert_ks,
                interp_method=self.interp_method,
                boundary_file=self.boundary_file,
                log_cb=self.log_signal.emit
            )
            
            logger.info(f"[SEDIMENT WORKER] Interpolation successful. Exported to: {xyz_path}")
            self.log_signal.emit(f"✅ Interpolasi Contours sukses. Disimpan di: {xyz_path}")
            
            self.plot_signal.emit(plot_path)
            self.finished_signal.emit(xyz_path)
            
        except Exception as e:
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[FATAL] Sediment Worker Error: {error_details}")
            
            self.log_signal.emit(f"❌ Error Spasial: {str(e)}")
            self.finished_signal.emit("")
