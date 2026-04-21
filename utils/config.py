import os
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller _MEIPASS """
    try:
        base_path = sys._MEIPASS
    except Exception:
        # Fallback to the root directory of the application
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(base_path, relative_path)

def get_leaflet_html(mode="era5"):
    """ Reads the base HTML template and replaces draw options based on the mode. """
    template_path = resource_path(os.path.join("assets", "templates", "leaflet_base.html"))
    
    if not os.path.exists(template_path):
        return f"<html><body><h1>Error: Template not found at {template_path}</h1></body></html>"
        
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    if mode == "postproc":
        html = html_content.replace("__IS_POSTPROC__", "true")
    else:
        draw_opts = "rectangle: true, polygon: false, polyline: false" if mode == "era5" else "rectangle: true, polygon: true, polyline: true"
        html = html_content.replace("__IS_POSTPROC__", "false")
        html = html.replace("__DRAW_OPTS__", draw_opts)
        
    return html
