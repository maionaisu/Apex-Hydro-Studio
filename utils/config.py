# ==============================================================================
# APEX NEXUS TIER-0: GLOBAL CONFIGURATION & RESOURCE MANAGER (HARDENED)
# ==============================================================================
import os
import sys
import logging

logger = logging.getLogger(__name__)

def resource_path(relative_path: str) -> str:
    """ 
    Get absolute path to resource, supports Dev and PyInstaller --onedir mode.
    """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    return os.path.join(base_path, relative_path)

def get_project_dirs() -> dict:
    """
    [TIER-0] Centralized Directory Manager.
    Memastikan seluruh folder krusial tersedia secara tersinkronisasi.
    """
    base_cwd = os.getcwd()
    dirs = {
        'root': base_cwd,
        'exports': os.path.abspath(os.path.join(base_cwd, 'Apex_Data_Exports')),
        'models': os.path.abspath(os.path.join(base_cwd, 'Apex_FM_Model_Final')),
        'assets': resource_path('assets'),
        'temp': os.path.abspath(os.path.join(base_cwd, 'Apex_Temp_Buffer'))
    }
    
    # Auto-creation failsafe
    for name, path in dirs.items():
        if name != 'assets' and not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                logger.error(f"[CONFIG] Gagal membuat direktori {name}: {e}")
                
    return dirs

def get_leaflet_html(mode: str = "era5") -> str:
    """ 
    Generates Leaflet HTML template with dynamic context injection.
    """
    template_path = resource_path(os.path.join("assets", "templates", "leaflet_base.html"))
    
    if not os.path.exists(template_path):
        logger.error(f"Leaflet template missing: {template_path}")
        return "<html><body><h3 style='color:red;'>[FATAL] Leaflet Assets Missing</h3></body></html>"
        
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
            
        # Context Injections
        is_post = "true" if mode == "postproc" else "false"
        draw_opts = "rectangle: false, polygon: false" if mode == "postproc" else "rectangle: true, polygon: true"
        
        html = html.replace("__IS_POSTPROC__", is_post)
        html = html.replace("__DRAW_OPTS__", draw_opts)
        
        return html
    except Exception as e:
        return f"<html><body>Error loading map: {str(e)}</body></html>"

def validate_external_binaries(bin_path: str) -> bool:
    """
    [ENTERPRISE CHECK]: Memvalidasi kesehatan binary Deltares sebelum eksekusi.
    """
    if not bin_path or not os.path.exists(bin_path):
        return False
    
    # Cek apakah itu file .bat atau .exe
    if not bin_path.lower().endswith(('.bat', '.exe')):
        return False
        
    return True
