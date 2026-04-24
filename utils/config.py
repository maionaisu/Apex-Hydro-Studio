# ==============================================================================
# APEX NEXUS TIER-0: GLOBAL CONFIGURATION & RESOURCE MANAGER (HARDENED)
# ==============================================================================
import os
import sys
import logging
import shutil

logger = logging.getLogger(__name__)

# --- ENTERPRISE METADATA ---
APP_VERSION = "18.0.5-STABLE"
APP_NAME = "Apex Hydro-Studio Enterprise"

def resource_path(relative_path: str) -> str:
    """ 
    Get absolute path to resource, supports Dev and PyInstaller --onedir mode.
    Secara cerdas mendeteksi sys._MEIPASS saat aplikasi berjalan sebagai .exe.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    # Jika dalam mode development, naik satu tingkat dari folder utils/
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', relative_path))

def get_project_dirs() -> dict:
    """
    [TIER-0] Centralized Directory Manager.
    Memastikan seluruh folder krusial tersedia secara tersinkronisasi di sistem operasi.
    """
    base_cwd = os.getcwd()
    dirs = {
        'root': base_cwd,
        'exports': os.path.abspath(os.path.join(base_cwd, 'Apex_Data_Exports')),
        'models': os.path.abspath(os.path.join(base_cwd, 'Apex_FM_Model_Final')),
        'assets': resource_path('assets'),
        'temp': os.path.abspath(os.path.join(base_cwd, 'Apex_Temp_Buffer'))
    }
    
    # Auto-creation failsafe dengan pengecekan izin akses
    for name, path in dirs.items():
        if name != 'assets' and not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                logger.debug(f"[CONFIG] Inisialisasi direktori: {name} -> {path}")
            except Exception as e:
                logger.error(f"[CONFIG] Gagal membuat direktori {name}: {e}")
                
    return dirs

def cleanup_temp_buffer() -> None:
    """
    [ENTERPRISE SAFETY]: Membersihkan folder buffer temporer untuk mencegah 
    pembengkakan penggunaan disk setelah proses interpolasi spasial yang berat.
    """
    temp_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Temp_Buffer'))
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            os.makedirs(temp_dir, exist_ok=True)
            logger.info("[CONFIG] Temporary buffer telah dibersihkan secara aman.")
        except Exception as e:
            logger.warning(f"[CONFIG] Gagal membersihkan temp buffer: {e}")

def get_leaflet_html(mode: str = "era5") -> str:
    """ 
    Generates Leaflet HTML template with dynamic context injection.
    Tersinkronisasi dengan kebutuhan spesifik tiap modul UI.
    """
    template_path = resource_path(os.path.join("assets", "templates", "leaflet_base.html"))
    
    if not os.path.exists(template_path):
        logger.error(f"Leaflet template missing: {template_path}")
        return "<html><body style='background:#111;color:#555;'><h3>[FATAL] Leaflet Assets Missing</h3></body></html>"
        
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
            
        # Injeksi Konteks Berdasarkan Modul
        is_post = "true" if mode == "postproc" else "false"
        
        # Konfigurasi Toolbar Gambar (Granularitas Capabilties)
        if mode == "postproc":
            # Post-processing tidak butuh fitur menggambar (read-only overlay)
            draw_opts = "rectangle: false, polygon: false, circle: false, marker: false, polyline: false"
        elif mode == "era5":
            # ERA5 hanya butuh rectangle untuk batas download
            draw_opts = "rectangle: true, polygon: false, circle: false, marker: false, polyline: false"
        else:
            # Modul Mesh/Sedimen butuh polygon dan polyline (transek)
            draw_opts = "rectangle: true, polygon: true, circle: false, marker: true, polyline: true"
        
        html = html.replace("__IS_POSTPROC__", is_post)
        html = html.replace("__DRAW_OPTS__", draw_opts)
        
        return html
    except Exception as e:
        logger.error(f"[UI] Template Rendering Error: {e}")
        return f"<html><body>Error loading map: {str(e)}</body></html>"

def validate_external_binaries(bin_path: str) -> bool:
    """
    [ENTERPRISE CHECK]: Memvalidasi kesehatan binary Deltares sebelum eksekusi.
    Mencegah crash pada QProcess jika user memilih file yang bukan executable.
    """
    if not bin_path or not os.path.exists(bin_path):
        return False
    
    # Validasi ekstensi berdasarkan platform (Windows-centric untuk Delft3D)
    valid_exts = ('.bat', '.exe', '.cmd') if os.name == 'nt' else ('.sh',)
    if not bin_path.lower().endswith(valid_exts):
        return False
        
    return True
