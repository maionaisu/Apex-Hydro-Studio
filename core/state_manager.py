# ==============================================================================
# APEX NEXUS TIER-0: THREAD-SAFE GLOBAL STATE MANAGER (MVVM STORE)
# ==============================================================================
import json
import copy
import logging
import numpy as np
from typing import Any, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker

# Explicit Logger Config for debugging background thread overrides
logger = logging.getLogger(__name__)

class _NumpyEncoder(json.JSONEncoder):
    """
    BUG-14 FIX: Custom JSON encoder that handles numpy scalar and array types
    which are commonly written into app_state by xarray/numpy engine outputs.
    Without this, json.dump raises TypeError on np.float32, np.int64, np.ndarray.
    """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

class StateManager(QObject):
    """
    [TIER-0 OMNI-STATE STORE]
    Thread-safe Global Memory Manager (Singleton/Borg hybrid pattern).
    Implements Mutex locking for strictly safe QThread/Worker cross-communication.
    """
    # Granular signal passing the specific key that was updated
    state_updated = pyqtSignal(str) 
    # Global signal for massive overwrites (e.g., Session Import)
    bulk_state_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        # SECURITY: QMutex guarantees atomic operations across UI and Worker threads
        self._mutex = QMutex()
        
        # Explicit Schema Definition for Clungup Mangrove Conservation (CMC) Physics
        self._state: Dict[str, Any] = {
            'He': 0.0,
            'Hs': 0.0,
            'Tp': 8.0,
            'Dir': 180.0,
            'DoC': 0.0,
            'sediment_xyz': "",
            'tide_bc': "",
            'EPSG': "32749",
            'mesh_bbox': None,
            'transect': [],
            
            # [THESIS ALIGNMENT]: Mangrove Spatial Drag Variables (Baptist Eq / Trachytope)
            'veg_height_hv': 2.0,     # meters
            'veg_density_n': 20.0,    # stems/m2
            'veg_drag_cd': 1.5,       # drag coefficient
            
            # System States
            'dimr_path': "",
            'workspace_dir': ""
        }

    def update(self, key: str, value: Any) -> None:
        """
        O(1) Mutex-locked state mutation. 
        Stores a deepcopy to prevent background workers from mutating the origin object.
        """
        with QMutexLocker(self._mutex):
            self._state[key] = copy.deepcopy(value)
        
        # Emit OUTSIDE the lock to prevent GUI thread deadlocks if UI slots are heavy
        self.state_updated.emit(key)
        logger.debug(f"[STATE] Updated Key: {key}")

    def update_multiple(self, dictionary: Dict[str, Any]) -> None:
        """O(K) Mutex-locked bulk mutation. Used during Session Import or heavy Worker emits."""
        with QMutexLocker(self._mutex):
            for k, v in dictionary.items():
                self._state[k] = copy.deepcopy(v)
        
        self.bulk_state_updated.emit()
        logger.debug(f"[STATE] Bulk update executed for {len(dictionary)} keys.")

    def get(self, key: str, default: Any = None) -> Any:
        """
        O(1) Mutex-locked safe retrieval. 
        Returns deepcopy to completely isolate UI/Worker memory pointers.
        """
        with QMutexLocker(self._mutex):
            val = self._state.get(key, default)
            return copy.deepcopy(val)

    def get_all(self) -> Dict[str, Any]:
        """Returns a complete, thread-safe snapshot of the current state dict."""
        with QMutexLocker(self._mutex):
            return copy.deepcopy(self._state)

    def export_session(self, filepath: str) -> bool:
        """Serializes current state to disk securely."""
        try:
            state_snapshot = self.get_all()
            # Enforce strict UTF-8 encoding for cross-OS compatibility
            # Utilizes the _NumpyEncoder to safely parse xarray/numpy arrays
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state_snapshot, f, indent=4, cls=_NumpyEncoder)
            logger.info(f"[IO] Session successfully exported to {filepath}")
            return True
        except Exception as e:
            logger.error(f"[FATAL] Failed to export session -> {str(e)}")
            return False

    def import_session(self, filepath: str) -> bool:
        """Deserializes state from disk with mutation lock protection."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.update_multiple(data)
            logger.info(f"[IO] Session successfully imported from {filepath}")
            return True
        except Exception as e:
            logger.error(f"[FATAL] Failed to import session -> {str(e)}")
            return False

# Global Singleton Instance mapping
app_state = StateManager()
