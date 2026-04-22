# ==============================================================================
# APEX NEXUS TIER-0: GLOBAL CONFIGURATION & RESOURCE MANAGER
# ==============================================================================
import os
import sys
import logging

logger = logging.getLogger(__name__)

def resource_path(relative_path: str) -> str:
    """ 
    Get absolute path to resource, works for dev and for PyInstaller --onedir / --onefile.
    Safely resolves sys._MEIPASS without broad Exception swallowing.
    """
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    base_path = getattr(
        sys, 
        '_MEIPASS', 
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    )
    return os.path.join(base_path, relative_path)

def get_leaflet_html(mode: str = "era5") -> str:
    """ 
    Reads the base HTML template and replaces draw options based on the active UI mode. 
    Implements BUG-13 FIX for safe post-processing template generation.
    """
    template_path = resource_path(os.path.join("assets", "templates", "leaflet_base.html"))
    
    if not os.path.exists(template_path):
        error_msg = f"<html><body><h1>[FATAL ERROR] Template not found at {template_path}</h1></body></html>"
        logger.error(f"Leaflet template missing: {template_path}")
        return error_msg
        
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    # Inject variables based on UI Module context
    if mode == "postproc":
        html = html_content.replace("__IS_POSTPROC__", "true")
        # BUG-13 FIX: Must explicitly disable draw tools in postproc to prevent JS SyntaxError
        html = html.replace("__DRAW_OPTS__", "rectangle: false, polygon: false, polyline: false")
    else:
        # Dynamic draw options based on the active engine
        draw_opts = "rectangle: true, polygon: false, polyline: false" if mode == "era5" else "rectangle: true, polygon: true, polyline: true"
        html = html_content.replace("__IS_POSTPROC__", "false")
        html = html.replace("__DRAW_OPTS__", draw_opts)
        
    # SANITY CHECK: Detect unreplaced template tags (pre-mitigation for future UI updates)
    if "__" in html:
        # We only warn, as double underscores might legitimately exist in JS, 
        # but usually it indicates a missed template variable like __API_KEY__
        logger.debug("[UI] Notice: '__' sequence found in final HTML. Verify all template tags are replaced.")
        
    return html
