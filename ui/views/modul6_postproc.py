# ==============================================================================
# APEX NEXUS TIER-0: MODUL 6 - POST-PROCESSING & VISUALIZATION (UI VIEW)
# ==============================================================================
import os
import json
import logging
import traceback
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QScrollArea, QSlider, QFrame,
                             QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget, QHeaderView, QSplitter)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt

try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

from utils.config import get_leaflet_html
from workers.postproc_worker import PostProcAnimationWorker
from core.state_manager import app_state
from ui.components.web_bridge import WebBridge

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS (THE "GOLDEN" CSS FIX) ---
STYLE_GROUPBOX = """
    QGroupBox {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        margin-top: 10px;
        padding-top: 40px; /* Space lapang agar title duduk manis di dalam */
        font-weight: bold;
        color: #F1F5F9;
        font-size: 14px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 6px 15px;
        background-color: #0F172A;
        border-radius: 8px;
        color: #F59E0B;
        top: 10px; /* Positif! Judul masuk ke dalam kotak */
        left: 12px;
    }
"""

STYLE_INPUTS = """
    QComboBox {
        background-color: #0F172A;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 10px 14px;
        color: #F8FAFC;
        font-size: 13px;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    QComboBox:focus { border: 1px solid #F59E0B; }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox QAbstractItemView {
        background-color: #1E293B;
        color: #F8FAFC;
        selection-background-color: #334155;
        border: 1px solid #475569;
        border-radius: 6px;
    }
"""

STYLE_TABLE_LIST = """
    QTableWidget { 
        background-color: #0F172A; 
        color: #F8FAFC; 
        gridline-color: #334155; 
        border: 1px solid #334155; 
        border-radius: 8px; 
        font-family: 'Consolas', 'Courier New', monospace;
    }
    QHeaderView::section { 
        background-color: #1E293B; 
        color: #94A3B8; 
        padding: 8px; 
        font-weight: bold; 
        border: 1px solid #334155; 
    }
"""

STYLE_BTN_PRIMARY = """
    QPushButton#ExecuteBtn {
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F59E0B, stop:1 #D97706);
        color: #022C22;
        border: none;
        border-radius: 8px;
        padding: 12px 16px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton#ExecuteBtn:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FCD34D, stop:1 #F59E0B); transform: scale(1.02); }
    QPushButton#ExecuteBtn:pressed { background-color: #B45309; }
    QPushButton#ExecuteBtn:disabled { background-color: #334155; color: #94A3B8; }
"""

STYLE_BTN_OUTLINE = """
    QPushButton#OutlineBtn {
        background-color: transparent;
        color: #F8FAFC;
        border: 1px solid #64748B;
        border-radius: 8px;
        padding: 12px 16px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton#OutlineBtn:hover { background-color: #334155; border-color: #F59E0B; color: #F59E0B; }
"""

STYLE_SLIDER = """
    QSlider::groove:horizontal { border-radius: 6px; height: 12px; margin: 0px; background-color: #334155; }
    QSlider::handle:horizontal { background-color: #F59E0B; border: 3px solid #FFFFFF; width: 20px; height: 20px; margin: -5px 0; border-radius: 10px; }
    QSlider::handle:horizontal:hover { background-color: #FCD34D; transform: scale(1.2); }
    QSlider::sub-page:horizontal { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #F59E0B); border-radius: 6px; }
    QSlider:disabled { opacity: 0.4; }
"""

LABEL_STYLE = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 13px; }"


class Modul6PostProc(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.nc_file = ""
        self.current_max_time = 0
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_TABLE_LIST} {STYLE_BTN_PRIMARY} {STYLE_BTN_OUTLINE} {STYLE_SLIDER}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER ---
        head = QVBoxLayout()
        t = QLabel("Post-Processing & Spatio-Temporal Animation")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Visualisasi Output NetCDF (*_map.nc) dari Deltares secara spasial menggunakan Leaflet Heatmaps Dinamis.")
        d.setStyleSheet("color: #94A3B8; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        # Splitter Layout Transparan (Peta vs Kontrol)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 10px; }")

        # ==============================================================================
        # 1. TOP SECTION (MAP & AOI)
        # ==============================================================================
        top_widget = QWidget()
        top_section = QHBoxLayout(top_widget)
        top_section.setContentsMargins(0, 0, 0, 0)
        top_section.setSpacing(20)
        
        # LEFT: MAP
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: 1px solid #1E293B; border-radius: 12px; background: #000; overflow: hidden;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(1, 1, 1, 1)
        
        self.web_map = QWebEngineView()
        self.web_map.setMinimumHeight(450)
        self.web_map.setHtml(get_leaflet_html("postproc"))
        tl.addWidget(self.web_map)
        
        top_section.addWidget(top_wrap, stretch=7)
        
        # RIGHT: AOI Tabs
        self.tabs_aoi = QTabWidget()
        self.tabs_aoi.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; border-radius: 12px; background: #1E293B; }
            QTabBar::tab { background: #0F172A; color: #94A3B8; padding: 12px 18px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; font-weight: bold;}
            QTabBar::tab:selected { background: #1E293B; color: #F59E0B; border-bottom: 3px solid #F59E0B;}
        """)

        # Tab 1: Shapefile / KML Subset
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(20, 24, 20, 20)
        lbl_msg = QLabel("📂 Unggah batas Area Geospasial (AOI) untuk mengekstrak dan menyorot data Heatmap ke lokasi pesisir spesifik.")
        lbl_msg.setStyleSheet("color: #CBD5E1; font-size: 13px; line-height: 1.5;")
        lbl_msg.setWordWrap(True)
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_shp = QPushButton("Muat Vector Pesisir (.shp/.kml)")
        btn_shp.setObjectName("OutlineBtn")
        btn_shp.clicked.connect(self.import_aoi_shapefile)
        
        l1.addWidget(lbl_msg)
        l1.addSpacing(15)
        l1.addWidget(btn_shp)
        l1.addStretch()
        self.tabs_aoi.addTab(t1, "SHP/KML Subset")

        # Tab 2: Manual BBox Bounds
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(20, 24, 20, 20)
        lbl_aoi = QLabel("Manual Bounding Box (Lat/Lon):")
        lbl_aoi.setStyleSheet(LABEL_STYLE)
        l2.addWidget(lbl_aoi)
        
        self.tbl_bbox = QTableWidget(4, 1)
        self.tbl_bbox.setVerticalHeaderLabels(["North", "South", "East", "West"])
        self.tbl_bbox.horizontalHeader().setVisible(False)
        self.tbl_bbox.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_bbox.setMaximumHeight(160)
        
        for j in range(4): 
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_bbox.setItem(j, 0, item)
            
        self.tbl_bbox.itemChanged.connect(self.manual_update_bbox_vertical)
        l2.addWidget(self.tbl_bbox)
        l2.addStretch()
        self.tabs_aoi.addTab(t2, "Manual Params")
        
        top_section.addWidget(self.tabs_aoi, stretch=3)
        splitter.addWidget(top_widget)

        # ==============================================================================
        # 2. BOTTOM SECTION (CONTROLS & TIMELINE)
        # ==============================================================================
        bot_widget = QWidget()
        bot_layout = QVBoxLayout(bot_widget)
        bot_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; }
            QScrollBar:vertical { background: #0F172A; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #475569; border-radius: 5px; }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 5, 0, 0)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(25)
        
        # Col 1: File & Variable
        c1 = QVBoxLayout()
        grp1 = QGroupBox("1. Dataset & Variabel Fisik (.map.nc)")
        
        g1 = QFormLayout(grp1)
        g1.setHorizontalSpacing(20)
        g1.setVerticalSpacing(18)
        
        self.btn_nc = QPushButton("📂 Muat Hasil Simulasi (.map.nc)")
        self.btn_nc.setObjectName("OutlineBtn")
        self.btn_nc.clicked.connect(self.load_nc_file)
        g1.addRow(self.btn_nc)
        
        self.cmb_var = QComboBox()
        # Katalog default DFlow FM & SWAN Map Output
        self.cmb_var.addItems([
            'mesh2d_s1',      # Water level
            'mesh2d_ucx',     # Velocity X
            'mesh2d_ucy',     # Velocity Y
            'mesh2d_taus',    # Bed shear stress
            'Hsig',           # Significant wave height (SWAN)
            'Tp',             # Peak wave period (SWAN)
            'Wdir'            # Wave direction (SWAN)
        ])
        lbl_var = QLabel("Pilih Variabel:"); lbl_var.setStyleSheet(LABEL_STYLE)
        g1.addRow(lbl_var, self.cmb_var)
        
        self.btn_ren = QPushButton("▶ Render Heatmap Sekarang")
        self.btn_ren.setObjectName("ExecuteBtn")
        self.btn_ren.clicked.connect(lambda: self.trigger_render(self.sld_time.value()))
        g1.addRow(self.btn_ren)
        
        c1.addWidget(grp1)
        c1.addStretch()
        ctrl.addLayout(c1, stretch=4)

        # Col 2: Time Control (Scrubber)
        c2 = QVBoxLayout()
        grp2 = QGroupBox("2. Time Series Scrubber (Animasi Dinamis)")
        g2 = QVBoxLayout(grp2)
        g2.setSpacing(18)
        
        h_info = QHBoxLayout()
        self.lbl_t_idx = QLabel("Time Index: [ 0 ]")
        self.lbl_t_str = QLabel("Timestamp: -")
        self.lbl_val_range = QLabel("Range (Min-Max): -")
        
        self.lbl_t_idx.setStyleSheet("color:#38BDF8; font-weight:900; font-size:14px; font-family: 'Consolas', monospace;")
        self.lbl_t_str.setStyleSheet("color:#10B981; font-weight:900; font-size:14px; font-family: 'Consolas', monospace; background-color:#064E3B; padding:6px 12px; border-radius:6px; border: 1px solid #047857;")
        self.lbl_val_range.setStyleSheet("color:#F59E0B; font-weight:900; font-size:13px; font-family: 'Consolas', monospace; background-color:#451A03; padding:6px 12px; border-radius:6px; border: 1px solid #78350F;")
        
        h_info.addWidget(self.lbl_t_idx)
        h_info.addStretch()
        h_info.addWidget(self.lbl_t_str)
        h_info.addStretch()
        h_info.addWidget(self.lbl_val_range)
        g2.addLayout(h_info)
        
        self.sld_time = QSlider(Qt.Orientation.Horizontal)
        self.sld_time.setRange(0, 0)
        self.sld_time.setValue(0)
        self.sld_time.setEnabled(False) # Disabled until first render
        self.sld_time.valueChanged.connect(self.on_slider_moved)
        self.sld_time.sliderReleased.connect(self.on_slider_released)
        g2.addWidget(self.sld_time)
        
        g2.addStretch()
        c2.addWidget(grp2)
        c2.addStretch()
        ctrl.addLayout(c2, stretch=6)
        
        scroll_layout.addLayout(ctrl)

        # --- 3. BOTTOM: LOG ---
        bl = QVBoxLayout()
        bl.setContentsMargins(0, 15, 0, 0)
        bl.addWidget(QLabel("Terminal Rendering Status:", styleSheet="font-weight:900; color:#38BDF8; font-size: 14px;"))
        self.log_viz = QTextEdit()
        self.log_viz.setReadOnly(True)
        self.log_viz.setStyleSheet("background-color: #020617; color: #10B981; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #1E293B; border-radius: 8px; padding: 12px;")
        self.log_viz.setMinimumHeight(100)
        bl.addWidget(self.log_viz)
        
        scroll_layout.addLayout(bl)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        
        bot_layout.addWidget(scroll)
        splitter.addWidget(bot_widget)
        
        # Proporsi Splitter: Peta mengambil mayoritas layar
        splitter.setSizes([600, 250])
        main_layout.addWidget(splitter)

    # --------------------------------------------------------------------------
    # DATA & INTERACTION LOGIC
    # --------------------------------------------------------------------------

    def import_aoi_shapefile(self) -> None:
        if not HAS_GEOPANDAS: 
            QMessageBox.critical(self, "Pustaka Hilang", "Pustaka Geopandas tidak ditemukan. Install via pip.")
            return
            
        p, _ = QFileDialog.getOpenFileName(self, "Pilih Batas Area Subset", "", "Vector Data (*.shp *.kml *.geojson)")
        if not p: return
        
        try:
            gdf = gpd.read_file(p)
            
            # FIX: Null-Guard CRS
            if gdf.crs is None or gdf.crs.to_epsg() != 4326: 
                gdf = gdf.to_crs(epsg=4326)
                
            js = f"addGeoJSON({gdf.to_json()}, '#EF4444');"
            self.web_map.page().runJavaScript(js)
            self.log_viz.append(f"✅ Vektor Geospasial berhasil dimuat dan digambar di Peta.")
            
            # Ekstrak Total Bounds [min_lon, min_lat, max_lon, max_lat] -> [W, S, E, N]
            bounds = gdf.total_bounds 
            self.tbl_bbox.blockSignals(True)
            self.tbl_bbox.setItem(0, 0, QTableWidgetItem(f"{bounds[3]:.4f}")) # N
            self.tbl_bbox.setItem(1, 0, QTableWidgetItem(f"{bounds[1]:.4f}")) # S
            self.tbl_bbox.setItem(2, 0, QTableWidgetItem(f"{bounds[2]:.4f}")) # E
            self.tbl_bbox.setItem(3, 0, QTableWidgetItem(f"{bounds[0]:.4f}")) # W
            self.tbl_bbox.blockSignals(False)
            
        except Exception as e:
            logger.error(f"[SHP IMPORT] Gagal membaca subset file: {str(e)}\n{traceback.format_exc()}")
            self.log_viz.append(f"❌ Gagal memproses Shapefile: {str(e)}")

    def manual_update_bbox_vertical(self) -> None:
        try:
            n = float(self.tbl_bbox.item(0,0).text())
            s = float(self.tbl_bbox.item(1,0).text())
            e = float(self.tbl_bbox.item(2,0).text())
            w = float(self.tbl_bbox.item(3,0).text())
            
            if n <= s or e <= w:
                raise ValueError("Koordinat N harus > S, dan E harus > W.")
                
            js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{w},{s}],[{e},{s}],[{e},{n}],[{w},{n}],[{w},{s}]]]}}, '#38BDF8');"
            self.web_map.page().runJavaScript(js_box)
            self.log_viz.append("[SYSTEM] Bounding Box (Subset) telah diperbarui secara manual.")
        except Exception as e:
            self.log_viz.append(f"[WARNING] Input manual tidak valid: {str(e)}")

    def load_nc_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Pilih File .map.nc (Output DIMR)", os.getcwd(), "NetCDF Output (*.nc)")
        if p: 
            self.nc_file = os.path.abspath(p)
            self.log_viz.append(f"▶ File Map Output aktif: {os.path.basename(p)}")

    def on_slider_moved(self, val: int) -> None:
        # Pembaruan Label *secara cepat* tanpa mengeksekusi NetCDF (Mencegah Lag)
        self.lbl_t_idx.setText(f"Time Index: [ {val} / {self.current_max_time} ]")

    def on_slider_released(self) -> None:
        # Eksekusi NetCDF hanya saat user melepas klik Mouse pada slider
        self.trigger_render(self.sld_time.value())

    def trigger_render(self, time_idx: int) -> None:
        # 1. Concurrency Guard (Seksi 5.B Requirement)
        if hasattr(self, 'worker') and self.worker.isRunning():
            return # Ignore if already rendering (User clicked too fast)
            
        if not self.nc_file or not os.path.exists(self.nc_file):
            QMessageBox.warning(self, "File Hilang", "Muat file NetCDF (.nc) terlebih dahulu dari hasil kompilasi DIMR.")
            return
            
        epsg = app_state.get('EPSG', '32749')
        out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))
        os.makedirs(out_dir, exist_ok=True)
        
        target_var = self.cmb_var.currentText()
        
        # 2. UI Lock & Delegation
        self.btn_ren.setEnabled(False)
        self.sld_time.setEnabled(False)
        self.btn_ren.setText("⏳ Sedang Mengekstrak Frame NetCDF...")
        
        self.worker = PostProcAnimationWorker(self.nc_file, target_var, time_idx, epsg, out_dir)
        self.worker.log_signal.connect(self.log_viz.append)
        self.worker.frame_signal.connect(self.apply_overlay)
        
        def on_finished(success: bool):
            self.sld_time.setEnabled(True)
            self.btn_ren.setEnabled(True)
            self.btn_ren.setText("▶ Render Heatmap Sekarang")
            self.worker.deleteLater() # Strict Garbage Collection
            
        self.worker.finished_signal.connect(on_finished)
        self.worker.start()

    def apply_overlay(self, data: dict) -> None:
        """Menerima Base64 Image dan Bounds dari Worker, menginjeksinya ke Javascript Leaflet."""
        self.current_max_time = data.get('max_time', 0)
        
        # Update Slider Range (Diam-diam matikan signal agar tidak memicu re-render otomatis)
        self.sld_time.blockSignals(True)
        self.sld_time.setRange(0, self.current_max_time)
        self.sld_time.blockSignals(False)
        
        self.lbl_t_str.setText(f"Timestamp: {data.get('time_str', 'Static')}")
        v_min, v_max = data.get('v_min', 0.0), data.get('v_max', 0.0)
        self.lbl_val_range.setText(f"Range: {v_min:.3f} s/d {v_max:.3f}")
        
        b = data['bounds']
        base64_img = data['base64_img']
        
        # Serialisasi format Bounds Leaflet: [[South, West], [North, East]]
        bounds_json = json.dumps([[b['S'], b['W']], [b['N'], b['E']]])
        
        # Injeksi Javascipt (Double braces {{ }} untuk escaping format string Python)
        js_code = f"""
        if (window.currentOverlay) {{ map.removeLayer(window.currentOverlay); }}
        var bounds = {bounds_json};
        window.currentOverlay = L.imageOverlay('{base64_img}', bounds, {{opacity: 0.85}});
        window.currentOverlay.addTo(map);
        map.fitBounds(bounds);
        """
        self.web_map.page().runJavaScript(js_code)
        self.log_viz.append("✅ Frame berhasil diinjeksi ke Canvas Peta.")
