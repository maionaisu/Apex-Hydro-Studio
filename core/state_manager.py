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
    Thread-safe Global Memory Manager.
    Menggunakan pola 'Module-Level Singleton' dengan pengaman PyQt6 asli.
    """
    _instance = None
    
    state_updated = pyqtSignal(str) 
    bulk_state_updated = pyqtSignal()

    def __init__(self):
        # [ENTERPRISE FIX]: PyQt Safe Singleton Guard
        # Alih-alih memanipulasi __new__ (yang dibenci oleh PyQt C++ Engine),
        # Kita melarang keras instansiasi ganda langsung dari akar __init__.
        if StateManager._instance is not None:
            raise RuntimeError("[FATAL] StateManager adalah Singleton! Gunakan 'from core.state_manager import app_state'")
            
        super().__init__()
        StateManager._instance = self
        
        self._mutex = QMutex()
        
        # STRICT SCHEMA GUARD: Whitelist parameter absolut di RAM
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

    def _safe_copy(self, val: Any) -> Any:
        """Smart Copying: Hemat CPU cycle dengan menghindari deepcopy pada tipe primitif."""
        if isinstance(val, (int, float, str, bool, type(None))):
            return val
        return copy.deepcopy(val)

    def update(self, key: str, value: Any) -> None:
        """O(1) Mutex-locked state mutation dengan Schema Guard."""
        if key not in self._schema_keys:
            logger.warning(f"[STATE GUARD] Injeksi key tidak dikenal ('{key}') digagalkan.")
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
            return self._safe_copy(self._state.get(key, default))

    def get_all(self) -> Dict[str, Any]:
        """Snapshot State utuh."""
        with QMutexLocker(self._mutex):
            return copy.deepcopy(self._state)

    def export_session(self, filepath: str) -> bool:
        """ATOMIC I/O OPERATION. Mencegah korupsi data jika OS crash saat Write."""
        try:
            state_snapshot = self.get_all()
            temp_path = f"{filepath}.tmp"
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(state_snapshot, f, indent=4, cls=_NumpyEncoder)
                
            os.replace(temp_path, filepath) 
            logger.info(f"[IO] Sesi riset Apex berhasil diamankan ke: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"[FATAL] Gagal mengekspor sesi -> {str(e)}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except Exception: pass
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

# Murni Module-Level Singleton. Instansiasi ini hanya dieksekusi 1 kali seumur hidup aplikasi.
app_state = StateManager()
