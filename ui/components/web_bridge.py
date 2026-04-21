import json
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

class WebBridge(QObject):
    """
    QWebChannel Bridge for two-way communication between PyQt6 Python and Leaflet JavaScript.
    """
    bbox_drawn = pyqtSignal(dict)
    transect_drawn = pyqtSignal(list)
    
    @pyqtSlot(str)
    def receive_bbox(self, data_json): 
        self.bbox_drawn.emit(json.loads(data_json))
        
    @pyqtSlot(str)
    def receive_transect(self, data_json): 
        self.transect_drawn.emit(json.loads(data_json))
