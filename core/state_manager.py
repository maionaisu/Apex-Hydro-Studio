# ==============================================================================
# APEX NEXUS TIER-0: THREAD-SAFE GLOBAL STATE MANAGER (MVVM STORE)
# ==============================================================================
import os
import json
import copy
import logging
import numpy as np
from typing import Any, Dict
from PyQt6.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker

logger = logging.getLogger(__name__)

class _NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy scalar and array types."""
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)

class StateManager(QObject):
    """
    [TIER-0 OMNI-STATE STORE]
    Thread-safe Global Memory Manager with True Singleton Enforcement, 
    Strict Schema Guards, Smart Copying, and Atomic I/O Operations.
    """
    _instance = None
    _init_lock = QMutex()

    state_updated = pyqtSignal(str) 
    bulk_state_updated = pyqtSignal()

    def __new__(cls):
        # [ENTERPRISE FIX 1]: True Singleton Enforcement
        # Mencegah instansiasi ganda secara absolut di seluruh thread
        with QMutexLocker(cls._init_lock):
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Mencegah reset memori jika __init__ terpanggil berulang kali
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        super().__init__()
        self._mutex = QMutex()
        
        # [ENTERPRISE FIX 2]: STRICT SCHEMA GUARD
        # Daftar putih (Whitelist) parameter absolut yang diizinkan beredar di RAM
        self._schema_keys = {
            'He', 'Hs', 'Tp', 'Dir', 'DoC',
            'sim_start_time', 'sim_end_time',
            'sediment_xyz', 'tide_bc', 'EPSG',
            'mesh_bbox', 'inner_bbox', 'transect',
            'veg_height_hv', 'veg_density_n', 'veg_stem_diameter_m', 'veg_drag_cd',
            'dimr_path', 'workspace_dir', 'compute_backend'
        }
        
        self._state: Dict[str, Any] = {
            'He': 0.0, 'Hs': 0.0, 'Tp': 8.0, 'Dir': 180.0, 'DoC': 0.0,
            'sim_start_time': "", 'sim_end_time': "",
            'sediment_xyz': "", 'tide_bc': "", 'EPSG': "32749",
            'mesh_bbox': None, 'inner_bbox': None, 'transect': [],
            'veg_height_hv': 2.0, 'veg_density_n': 20.0, 'veg_stem_diameter_m': 0.15, 'veg_drag_cd': 1.5,
            'dimr_path': "", 'workspace_dir': "", 'compute_backend': "CPU"
        }
        self._initialized = True

    def _safe_copy(self, val: Any) -> Any:
        """
        [ENTERPRISE FIX 3]: Smart Copying. 
        Tipe data primitif (int/float/str) tidak butuh deepcopy. 
        Menghemat komputasi CPU yang sangat signifikan saat loop berjalan.
        """
        if isinstance(val, (int, float, str, bool, type(None))):
            return val
        return copy.deepcopy(val)

    def update(self, key: str, value: Any) -> None:
        """O(1) Mutex-locked state mutation dengan Schema Guard."""
        if key not in self._schema_keys:
            logger.warning(f"[STATE GUARD] Percobaan injeksi key tidak dikenal ('{key}') digagalkan. Mencegah Silent Bug.")
            return
            
        with QMutexLocker(self._mutex):
            self._state[key] = self._safe_copy(value)
        
        self.state_updated.emit(key)

    def update_multiple(self, dictionary: Dict[str, Any]) -> None:
        """O(K) Mutex-locked bulk mutation dengan filter Schema Guard."""
        updated_keys = []
        with QMutexLocker(self._mutex):
            for k, v in dictionary.items():
                if k in self._schema_keys:
                    self._state[k] = self._safe_copy(v)
                    updated_keys.append(k)
                else:
                    logger.warning(f"[STATE GUARD] Injeksi bulk key tidak dikenal ('{k}') diabaikan.")
        
        if updated_keys:
            self.bulk_state_updated.emit()

    def get(self, key: str, default: Any = None) -> Any:
        """O(1) Mutex-locked safe retrieval. Menjamin isolasi pointer memori."""
        with QMutexLocker(self._mutex):
            val = self._state.get(key, default)
            return self._safe_copy(val)

    def get_all(self) -> Dict[str, Any]:
        """Snapshot State utuh."""
        with QMutexLocker(self._mutex):
            return copy.deepcopy(self._state)

    def export_session(self, filepath: str) -> bool:
        """
        [ENTERPRISE FIX 4]: ATOMIC I/O OPERATION.
        Mencegah korupsi data permanen jika aplikasi/OS crash tepat saat operasi `write` berlangsung.
        """
        try:
            state_snapshot = self.get_all()
            temp_path = f"{filepath}.tmp"
            
            # Tulis ke file temporer terlebih dahulu
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(state_snapshot, f, indent=4, cls=_NumpyEncoder)
                
            # Gantikan (replace) file asli seketika. Operasi OS atomik.
            os.replace(temp_path, filepath) 
            logger.info(f"[IO] Sesi riset Apex berhasil diamankan ke: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"[FATAL] Gagal mengekspor sesi -> {str(e)}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path) # Cleanup sampah I/O
            return False

    def import_session(self, filepath: str) -> bool:
        if not os.path.exists(filepath):
            logger.error(f"[IO] File Sesi tidak ditemukan: {filepath}")
            return False
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.update_multiple(data)
            logger.info(f"[IO] Sesi riset Apex berhasil dipulihkan dari: {filepath}")
            return True
        except Exception as e:
            logger.error(f"[FATAL] Gagal memulihkan sesi -> {str(e)}")
            return False

# Global Singleton Instance mapping
app_state = StateManager()
