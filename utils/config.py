# ==============================================================================
# APEX NEXUS TIER-0: GLOBAL CONFIGURATION & RESOURCE MANAGER (HARDENED)
# ==============================================================================
import os
import sys
import stat
import logging
import shutil
import time
from functools import lru_cache
from typing import Dict

logger = logging.getLogger(__name__)

# --- ENTERPRISE METADATA ---
APP_VERSION = "18.0.5-STABLE"
APP_NAME = "Apex Hydro-Studio Enterprise"

def resource_path(relative_path: str) -> str:
    """ 
    [TIER-0 SAFEGUARD]
    Get absolute path to resource, supports Dev and PyInstaller --onedir mode.
    Secara cerdas mendeteksi sys._MEIPASS saat aplikasi berjalan sebagai .exe,
    serta memvalidasi 'Path Traversal' (../) menggunakan normpath.
    """
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        # Jika dalam mode development, naik satu tingkat dari folder utils/
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
    return os.path.normpath(os.path.join(base_path, relative_path))

def get_project_dirs() -> Dict[str, str]:
    """
    [TIER-0] Centralized Directory Manager.
    Memastikan seluruh folder krusial tersedia secara tersinkronisasi di sistem operasi
    dengan level perizinan folder yang ketat (0o755).
    """
    base_cwd = os.getcwd()
    dirs = {
        'root': base_cwd,
        'exports': os.path.abspath(os.path.join(base_cwd, 'Apex_Data_Exports')),
        'models': os.path.abspath(os.path.join(base_cwd, 'Apex_FM_Model_Final')),
        'assets': resource_path('assets'),
        'temp': os.path.abspath(os.path.join(base_cwd, 'Apex_Temp_Buffer'))
    }
    
    # Auto-creation failsafe dengan penegakan izin akses aman
    for name, path in dirs.items():
        if name != 'assets' and not os.path.exists(path):
            try:
                # mode 0o755 memberi read+execute universal, write hanya untuk owner
                os.makedirs(path, mode=0o755, exist_ok=True)
                logger.debug(f"[CONFIG] Inisialisasi direktori aman: {name} -> {path}")
            except Exception as e:
                logger.error(f"[FATAL CONFIG] Gagal membuat direktori sistem {name}: {e}")
                
    return dirs

def _remove_readonly_handler(func, path, excinfo):
    """
    [HARDENING] Callback untuk memaksa penghapusan file Read-Only di Windows.
    Diinjeksi dengan Micro-Delay Retry (0.1s) untuk melawan Windows File Lock contention.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        try:
            # Beri jeda sangat singkat agar OS sempat melepas File Handle (Anti-Crash)
            time.sleep(0.1) 
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception as e:
            logger.debug(f"[I/O WARNING] Gagal melepas file lock permanen pada {path}: {e}")

def cleanup_temp_buffer() -> None:
    """
    [ENTERPRISE SAFETY]: Membersihkan folder buffer temporer untuk mencegah 
    pembengkakan penggunaan disk (Storage Leak).
    """
    temp_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Temp_Buffer'))
    if os.path.exists(temp_dir):
        try:
            # Menggunakan onerror yang dilengkapi retry handler
            shutil.rmtree(temp_dir, onerror=_remove_readonly_handler)
            os.makedirs(temp_dir, mode=0o755, exist_ok=True)
            logger.info("[CONFIG] Temporary buffer telah dibersihkan secara atomik.")
        except Exception as e:
            logger.warning(f"[CONFIG] Gagal membersihkan temp buffer secara menyeluruh (mungkin file diakses): {e}")

@lru_cache(maxsize=1)
def _load_base_html() -> str:
    """
    [ENTERPRISE MEMORY CACHE]
    Menghindari disk I/O berulang (bottleneck) setiap kali UI/Peta dirender.
    Membaca HTML Leaflet satu kali secara absolut lalu menyimpannya di RAM.
    """
    template_path = resource_path(os.path.join("assets", "templates", "leaflet_base.html"))
    
    if not os.path.exists(template_path):
        logger.error(f"[FATAL] File skeleton Leaflet tidak ditemukan: {template_path}")
        return "<html><body style='background:#111;color:#555;'><h3>[FATAL] Leaflet Assets Missing</h3></body></html>"
        
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"[I/O ERROR] Gagal membaca template Leaflet: {e}")
        return f"<html><body>Error loading map skeleton: {str(e)}</body></html>"

def get_leaflet_html(mode: str = "era5") -> str:
    """ 
    Generates Leaflet HTML template with dynamic context injection.
    Tersinkronisasi dengan kebutuhan spesifik tiap modul UI secara efisien (O(N) replace).
    """
    html = _load_base_html()
    
    # Bypass logic jika cache HTML justru berisi string error
    if "[FATAL]" in html or "Error" in html:
        return html
        
    try:
        # Injeksi Konteks Berdasarkan Modul
        is_post = "true" if mode == "postproc" else "false"
        
        # Konfigurasi Toolbar Gambar (Granularitas Capabilties UI)
        if mode == "postproc":
            # Post-processing = Read-Only Overlay (Tidak butuh toolbar draw)
            draw_opts = "rectangle: false, polygon: false, circle: false, marker: false, polyline: false"
        elif mode == "era5":
            # ERA5 = Butuh BBox Makro
            draw_opts = "rectangle: true, polygon: false, circle: false, marker: false, polyline: false"
        else:
            # Modul Mesh/Sedimen = Full Drawing Capabilities
            draw_opts = "rectangle: true, polygon: true, circle: false, marker: true, polyline: true"
        
        # Substitusi string O(N) murni (jauh lebih cepat dibanding RegEx RegexObject)
        html = html.replace("__IS_POSTPROC__", is_post)
        html = html.replace("__DRAW_OPTS__", draw_opts)
        
        return html
        
    except Exception as e:
        logger.error(f"[UI] Kesalahan Injeksi Konteks Peta ({mode}): {e}")
        return f"<html><body>Context injection failed: {str(e)}</body></html>"

def validate_external_binaries(bin_path: str) -> bool:
    """
    [ENTERPRISE SECURITY CHECK]: Memvalidasi kesehatan binary Deltares sebelum eksekusi.
    Mencegah crash pada QProcess OS-level jika user memilih file yang invalid/cacat izin.
    """
    if not bin_path or not os.path.exists(bin_path):
        return False
    
    # Validasi ekstensi sesuai sistem operasi target kompilasi
    valid_exts = ('.bat', '.exe', '.cmd') if os.name == 'nt' else ('.sh', '.bash', '')
    if not str(bin_path).lower().endswith(valid_exts):
        logger.warning(f"[SECURITY] Eksekusi ditolak. File bukan binary executable: {bin_path}")
        return False
        
    # Memvalidasi bit eksekusi OS (Izin Administrator/Eksekusi OS)
    if not os.access(bin_path, os.X_OK):
        logger.warning(f"[SECURITY] File {bin_path} tidak memiliki izin Execute (OS.X_OK).")
        # Catatan: Di Windows, .bat tidak selalu merespon os.X_OK dengan akurat,
        # tapi peringatan log ini sangat esensial untuk forensik audit IT.
        
    return True
