import json
import os
from PyQt6.QtCore import QObject, pyqtSignal

class StateManager(QObject):
    """
    Global Memory Manager (Singleton pattern) for Apex Hydro-Studio.
    Handles states, variables, and cross-module communications.
    """
    state_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.state = {
            'He': 0.0,
            'Hs': 0.0,
            'Tp': 8.0,
            'Dir': 180.0,
            'DoC': 0.0,
            'sediment_xyz': "",
            'tide_bc': "",
            'EPSG': "32749",
            'mesh_bbox': None,
            'transect': []
        }
        
    def update(self, key, value):
        self.state[key] = value
        self.state_updated.emit()
        
    def update_multiple(self, dictionary):
        self.state.update(dictionary)
        self.state_updated.emit()
        
    def get(self, key, default=None):
        return self.state.get(key, default)
        
    def export_session(self, filepath):
        try:
            with open(filepath, 'w') as f:
                json.dump(self.state, f, indent=4)
            return True
        except Exception as e:
            print(f"Error exporting session: {e}")
            return False
            
    def import_session(self, filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.update_multiple(data)
            return True
        except Exception as e:
            print(f"Error importing session: {e}")
            return False

# Create a singleton instance to be used across the app
app_state = StateManager()
