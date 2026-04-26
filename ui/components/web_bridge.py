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
    Hardened with strict JSON payload validation, type assertion, and deep data inspection
    to prevent Event Loop crashes and Malicious/Malformed JS payload injection.
    """
    bbox_drawn = pyqtSignal(dict)
    transect_drawn = pyqtSignal(list)
    bridge_ready = pyqtSignal()

    @pyqtSlot(str)
    def ping(self, message: str) -> None:
        """[HEALTH CHECK] Memastikan jembatan IPC aktif dari WebEngine."""
        logger.debug(f"[WEB BRIDGE] Health check ping received: {message}")
        self.bridge_ready.emit()

    @pyqtSlot(str)
    def receive_bbox(self, data_json: str) -> None: 
        """
        Menerima koordinat Bounding Box dari kotak yang digambar user di Leaflet.
        Melakukan validasi O(1) untuk kunci dan casting tipe data paksa.
        """
        try:
            # [ENTERPRISE SAFEGUARD 1]: Validasi String Kosong
            if not data_json or not data_json.strip():
                raise ValueError("Menerima payload JSON kosong dari UI Peta.")

            parsed_data = json.loads(data_json)
            
            # Failsafe Guard: Tipe data Bounding Box harus selalu berupa Dictionary
            if not isinstance(parsed_data, dict):
                raise TypeError(f"Payload Bounding Box harus berupa dictionary, menerima: {type(parsed_data).__name__}")
                
            # Failsafe Guard: Validasi Kunci Absolut
            required_keys = {'N', 'S', 'E', 'W'}
            if not required_keys.issubset(parsed_data.keys()):
                raise KeyError(f"Payload kehilangan kunci koordinat wajib. Memiliki: {list(parsed_data.keys())}")
                
            # [ENTERPRISE SAFEGUARD 2]: Deep Validation & Floating Point Casting
            # Memastikan koordinat adalah numerik dan masuk akal secara geografis
            sanitized_data = {}
            for k in required_keys:
                try:
                    val = float(parsed_data[k])
                    sanitized_data[k] = val
                except (ValueError, TypeError):
                    raise ValueError(f"Nilai koordinat '{k}' bukan numerik valid: {parsed_data[k]}")
            
            # [ENTERPRISE SAFEGUARD 3]: Auto-Correction Logika BBox
            # Memastikan North selalu > South, dan East selalu > West
            # Mencegah crash pembentukan grid di MeshKernel
            if sanitized_data['N'] <= sanitized_data['S']:
                logger.warning(f"[WEB BRIDGE] BBox vertikal terbalik. Melakukan Auto-Koreksi N/S.")
                temp = sanitized_data['N']
                sanitized_data['N'] = sanitized_data['S']
                sanitized_data['S'] = temp
                
            if sanitized_data['E'] <= sanitized_data['W']:
                logger.warning(f"[WEB BRIDGE] BBox horizontal terbalik. Melakukan Auto-Koreksi E/W.")
                temp = sanitized_data['E']
                sanitized_data['E'] = sanitized_data['W']
                sanitized_data['W'] = temp

            logger.debug(f"[WEB BRIDGE] BBox sanitized & received: {sanitized_data}")
            self.bbox_drawn.emit(sanitized_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"[FATAL JS-BRIDGE] Invalid JSON format for BBox: {str(e)} | Raw: {data_json}")
        except Exception as e:
            logger.error(f"[FATAL JS-BRIDGE] Galat saat memproses BBox: {str(e)}\n{traceback.format_exc()}")
            
    @pyqtSlot(str)
    def receive_transect(self, data_json: str) -> None: 
        """
        Menerima deretan koordinat (Lat/Lon) dari garis Polyline yang digambar user di Leaflet.
        Memastikan setiap simpul (node) adalah sepasang numerik yang valid.
        """
        try:
            if not data_json or not data_json.strip():
                raise ValueError("Menerima payload JSON kosong dari UI Peta.")

            parsed_data = json.loads(data_json)
            
            # Failsafe Guard: Tipe data Transect harus berupa List / Array
            if not isinstance(parsed_data, list):
                raise TypeError(f"Payload Transek harus berupa list/array, menerima: {type(parsed_data).__name__}")
                
            # [ENTERPRISE SAFEGUARD 4]: Deep Validation Matriks 2D
            sanitized_transect = []
            for i, node in enumerate(parsed_data):
                if not isinstance(node, (list, tuple)) or len(node) != 2:
                    raise ValueError(f"Node transek ke-{i} tidak valid (bukan pasangan koordinat 2D): {node}")
                
                try:
                    lat, lon = float(node[0]), float(node[1])
                    
                    # Validasi batas bumi geografis (WGS84)
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        logger.warning(f"[WEB BRIDGE] Koordinat transek ke-{i} di luar batas wajar WGS84: Lat={lat}, Lon={lon}")
                        
                    sanitized_transect.append([lat, lon])
                except (ValueError, TypeError):
                    raise ValueError(f"Nilai koordinat pada node ke-{i} bukan numerik: {node}")

            # Mencegah komputasi DoC jika garis hanya berupa 1 titik
            if len(sanitized_transect) < 2:
                raise ValueError("Garis transek harus memiliki setidaknya 2 titik (Awal dan Akhir).")

            logger.debug(f"[WEB BRIDGE] Transect sanitized & received: {len(sanitized_transect)} nodes")
            self.transect_drawn.emit(sanitized_transect)
            
        except json.JSONDecodeError as e:
            logger.error(f"[FATAL JS-BRIDGE] Invalid JSON format for Transect: {str(e)} | Raw: {data_json}")
        except Exception as e:
            logger.error(f"[FATAL JS-BRIDGE] Galat saat memproses Transect: {str(e)}\n{traceback.format_exc()}")
