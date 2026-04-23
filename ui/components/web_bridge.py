# ==============================================================================
# APEX NEXUS TIER-0: QWEBCHANNEL BRIDGE (PYTHON <-> JAVASCRIPT)
# ==============================================================================
import json
import logging
import traceback
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)

class WebBridge(QObject):
    """
    [TIER-0] QWebChannel Bridge for two-way communication between PyQt6 Python and Leaflet JavaScript.
    Hardened with strict JSON payload validation to prevent Event Loop crashes.
    """
    bbox_drawn = pyqtSignal(dict)
    transect_drawn = pyqtSignal(list)
    
    @pyqtSlot(str)
    def receive_bbox(self, data_json: str) -> None: 
        """
        Menerima koordinat Bounding Box dari kotak yang digambar user di Leaflet.
        """
        try:
            parsed_data = json.loads(data_json)
            
            # Failsafe Guard: Tipe data Bounding Box harus selalu berupa Dictionary
            if not isinstance(parsed_data, dict):
                raise ValueError(f"Payload Bounding Box harus berupa dictionary, menerima: {type(parsed_data)}")
                
            logger.debug(f"[WEB BRIDGE] BBox received: {parsed_data}")
            self.bbox_drawn.emit(parsed_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"[FATAL JS-BRIDGE] Invalid JSON format for BBox: {str(e)}\nRaw data: {data_json}")
        except Exception as e:
            logger.error(f"[FATAL JS-BRIDGE] Galat saat memproses BBox: {str(e)}\n{traceback.format_exc()}")
            
    @pyqtSlot(str)
    def receive_transect(self, data_json: str) -> None: 
        """
        Menerima deretan koordinat (Lat/Lon) dari garis Polyline yang digambar user di Leaflet.
        """
        try:
            parsed_data = json.loads(data_json)
            
            # Failsafe Guard: Tipe data Transect harus berupa List / Array
            if not isinstance(parsed_data, list):
                raise ValueError(f"Payload Transek harus berupa list/array, menerima: {type(parsed_data)}")
                
            logger.debug(f"[WEB BRIDGE] Transect received: {len(parsed_data)} nodes")
            self.transect_drawn.emit(parsed_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"[FATAL JS-BRIDGE] Invalid JSON format for Transect: {str(e)}\nRaw data: {data_json}")
        except Exception as e:
            logger.error(f"[FATAL JS-BRIDGE] Galat saat memproses Transect: {str(e)}\n{traceback.format_exc()}")
