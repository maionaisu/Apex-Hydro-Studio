# ==============================================================================
# APEX NEXUS TIER-0: MODUL 4 - MESH BUILDER & DIMR COUPLER (UI VIEW)
# ==============================================================================
import os
import json
import logging
import traceback
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QLineEdit, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QMessageBox, QFrame, 
                             QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, 
                             QSlider, QComboBox, QCheckBox, QHeaderView, QSplitter, QGridLayout)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QCursor

try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

from ui.components.web_bridge import WebBridge
from utils.config import get_leaflet_html
from workers.mesh_worker import DepthOfClosure2DWorker, ApexDIMROrchestratorWorker
from core.state_manager import app_state

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS ---
STYLE_GROUPBOX = """
    QGroupBox { background-color: #2D3139; border: 1px solid #3A3F4A; border-radius: 12px; margin-top: 15px; padding-top: 35px; font-weight: 800; color: #FFFFFF; font-size: 14px; }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 6px 16px; background-color: transparent; color: #8FC9DC; top: 8px; left: 10px; }
"""
STYLE_INPUTS = """
    QLineEdit, QComboBox { background-color: #1F2227; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 14px; color: #FFFFFF; font-size: 13px; font-family: 'Consolas', monospace; }
    QLineEdit:focus, QComboBox:focus { border: 1px solid #595FF7; background-color: #2D3139; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { background-color: #2D3139; color: #FFFFFF; selection-background-color: #595FF7; border: 1px solid #3A3F4A; border-radius: 8px; }
    QCheckBox { color: #9CA3AF; font-size: 13px; font-weight: 800; }
    QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #3A3F4A; background: #1F2227; }
    QCheckBox::indicator:checked { background: #595FF7; border: 1px solid #7176F8; }
"""
STYLE_TABLE = """
    QTableWidget { background-color: #1F2227; color: #FFFFFF; gridline-color: #3A3F4A; border: 1px solid #3A3F4A; border-radius: 8px; font-family: 'Consolas', monospace; }
    QHeaderView::section { background-color: #2D3139; color: #8FC9DC; padding: 8px; font-weight: 800; border: none; border-bottom: 1px solid #3A3F4A; border-right: 1px solid #3A3F4A; }
"""
STYLE_SEGMENTED_TAB = """
    QTabWidget#SegmentedTab::pane { border: 1px solid #3A3F4A; border-radius: 12px; background: transparent; top: -1px; }
    QTabBar#SegmentedBar { alignment: center; }
    QTabBar#SegmentedBar::tab { background: #1F2227; color: #9CA3AF; border: 1px solid #3A3F4A; padding: 12px 30px; font-weight: 900; font-size: 14px; margin: 0px; }
    QTabBar#SegmentedBar::tab:first { border-top-left-radius: 12px; border-bottom-left-radius: 12px; border-right: none; }
    QTabBar#SegmentedBar::tab:last { border-top-right-radius: 12px; border-bottom-right-radius: 12px; border-left: none; }
    QTabBar#SegmentedBar::tab:selected { background: #595FF7; color: #FFFFFF; border-color: #595FF7; }
"""
STYLE_BTNS = """
    QPushButton#PrimaryBtn { background-color: #595FF7; color: #FFFFFF; border: none; border-radius: 10px; padding: 14px 16px; font-weight: 900; font-size: 14px; }
    QPushButton#PrimaryBtn:hover { background-color: #7176F8; }
    QPushButton#PrimaryBtn:disabled { background-color: #3A3F4A; color: #6B7280; }
    QPushButton#OutlineBtn { background-color: transparent; color: #8FC9DC; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 16px; font-weight: 800; font-size: 13px; }
    QPushButton#OutlineBtn:hover { background-color: rgba(143, 201, 220, 0.1); border-color: #8FC9DC; }
"""
STYLE_SLIDER = """
    QSlider::groove:horizontal { border-radius: 4px; height: 8px; background-color: #1F2227; border: 1px solid #3A3F4A; }
    QSlider::handle:horizontal { background-color: #FFFFFF; border: 3px solid #595FF7; width: 18px; height: 18px; margin: -6px 0; border-radius: 12px; }
    QSlider::sub-page:horizontal { background-color: #595FF7; border-radius: 4px; }
"""

LABEL_STYLE = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 13px; }"


class Modul4Mesh(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_bathy = ""
        self.file_ldb = ""
        self._syncing = False
        
        self.setup_ui()
        app_state.state_updated.connect(self.on_global_state_changed)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_TABLE} {STYLE_SEGMENTED_TAB} {STYLE_BTNS} {STYLE_SLIDER}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER ---
        head = QVBoxLayout()
        t = QLabel("DIMR Domain & Adaptive Mesh Orchestrator")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Rekayasa arsitektur grid Ganda: Flexible Mesh (D-FLOW) dan Rectilinear Grid (D-WAVES) berbasis Dual-AOI.")
        d.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")

        # ==============================================================================
        # 1. TOP SECTION: MAP & PREVIEW TABS
        # ==============================================================================
        top_widget = QWidget()
        top_section = QHBoxLayout(top_widget)
        top_section.setContentsMargins(0, 0, 0, 0)
        top_section.setSpacing(20)

        # KIRI: Interactive Map & Viz Tabs
        self.gis_tabs_m = QTabWidget()
        self.gis_tabs_m.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3A3F4A; border-radius: 12px; background: #1E2128; }
            QTabBar::tab { background: #1F2227; color: #9CA3AF; padding: 12px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; font-weight: 800;}
            QTabBar::tab:selected { background: #2D3139; color: #8FC9DC; border-bottom: 3px solid #8FC9DC;}
        """)
        
        # Leaflet Map Tab
        tab_map = QWidget()
        lay_map = QVBoxLayout(tab_map)
        lay_map.setContentsMargins(1, 1, 1, 1)
        
        self.web_mesh = QWebEngineView()
        self.bridge_mesh = WebBridge()
        self.bridge_mesh.bbox_drawn.connect(self.update_inner_bbox)
        self.bridge_mesh.transect_drawn.connect(self.update_mesh_transect)
        
        self.web_mesh.page().setWebChannel(QWebChannel(self.web_mesh.page()))
        self.web_mesh.page().webChannel().registerObject("bridge", self.bridge_mesh)
        self.web_mesh.setHtml(get_leaflet_html("mesh"))
        lay_map.addWidget(self.web_mesh)
        self.gis_tabs_m.addTab(tab_map, "🗺️ Peta Interaktif (Dual-AOI)")

        # Topology Preview Tab
        tab_mesh_viz = QWidget()
        lay_mz = QVBoxLayout(tab_mesh_viz)
        lay_mz.setContentsMargins(20, 20, 20, 20)
        self.lbl_mesh_preview = QLabel("Visualisasi Topology (D-Flow MDU / D-Waves MDW) akan di-render di sini.")
        self.lbl_mesh_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mesh_preview.setStyleSheet("color: #5C637A; font-weight: 800; font-size:14px; background-color:#1E2128; border-radius:8px; border:2px dashed #3A3F4A;")
        lay_mz.addWidget(self.lbl_mesh_preview)
        self.gis_tabs_m.addTab(tab_mesh_viz, "🕸️ Pratinjau Topologi Mesh")

        # DoC Panorama Tab
        tab_doc = QWidget()
        lay_doc = QVBoxLayout(tab_doc)
        lay_doc.setContentsMargins(20, 20, 20, 20)
        self.lbl_doc_plot = QLabel("Plot DoC 2D Panorama Cross Section (Morphodynamics) akan dirender di sini.")
        self.lbl_doc_plot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_doc_plot.setStyleSheet("color: #5C637A; font-weight: 800; font-size:14px; background-color:#1E2128; border-radius:8px; border:2px dashed #3A3F4A;")
        lay_doc.addWidget(self.lbl_doc_plot)
        self.gis_tabs_m.addTab(tab_doc, "🔭 Panorama DoC (Transect)")
        
        top_section.addWidget(self.gis_tabs_m, stretch=7)
        
        # KANAN: AOI & Transect Manual Input Tabs
        self.tabs_aoi = QTabWidget()
        self.tabs_aoi.setStyleSheet(self.gis_tabs_m.styleSheet())
        
        # Tab 1: Set Inner BBox (Micro)
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(20, 24, 20, 20)
        lbl_bbox = QLabel("Batas Area Mikro (Inner Lat/Lon):")
        lbl_bbox.setStyleSheet(LABEL_STYLE)
        l1.addWidget(lbl_bbox)
        
        self.tbl_bbox = QTableWidget(4, 1)
        self.tbl_bbox.setVerticalHeaderLabels(["North", "South", "East", "West"])
        self.tbl_bbox.horizontalHeader().setVisible(False)
        self.tbl_bbox.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_bbox.setMaximumHeight(160)
        for j in range(4): 
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_bbox.setItem(j, 0, item)
            
        # [BUG FIX]: Hapus event koneksi otomatis agar tidak menggambar hantu saat inisialisasi
        l1.addWidget(self.tbl_bbox)
        
        btn_m1 = QPushButton("Update Area Mikro")
        btn_m1.setObjectName("OutlineBtn")
        btn_m1.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_m1.clicked.connect(self.manual_bbox_update)
        l1.addWidget(btn_m1)
        l1.addStretch()
        self.tabs_aoi.addTab(t1, "Set BBox Mikro")
        
        # Tab 2: Transect
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(20, 24, 20, 20)
        lbl_trans = QLabel("Manual Transect Nodes:")
        lbl_trans.setStyleSheet(LABEL_STYLE)
        l2.addWidget(lbl_trans)
        
        self.tbl_man = QTableWidget(2, 2)
        self.tbl_man.setHorizontalHeaderLabels(["Lat (Y)", "Lon (X)"])
        self.tbl_man.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_man.setMaximumHeight(120)
        
        for i, val in enumerate(["-8.460", "112.616", "-8.415", "112.717"]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_man.setItem(i//2, i%2, item)
            
        # [BUG FIX]: Hapus koneksi otomatis pada tbl_man
        l2.addWidget(self.tbl_man)
        
        btn_m2 = QPushButton("Update Line Profiles")
        btn_m2.setObjectName("OutlineBtn")
        btn_m2.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_m2.clicked.connect(self.manual_transect_update)
        l2.addWidget(btn_m2)
        l2.addStretch()
        self.tabs_aoi.addTab(t2, "Transect")
        
        top_section.addWidget(self.tabs_aoi, stretch=3)
        splitter.addWidget(top_widget)

        # ==============================================================================
        # 2. BOTTOM SECTION: SEGMENTED CONTROLS & TERMINAL
        # ==============================================================================
        bot_widget = QWidget()
        bot_layout = QVBoxLayout(bot_widget)
        bot_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 5, 0, 0)
        scroll_layout.setSpacing(20)

        # --- SEGMENTED TABS (D-FLOW vs D-WAVES) ---
        self.mode_tabs = QTabWidget()
        self.mode_tabs.setObjectName("SegmentedTab")
        self.mode_tabs.tabBar().setObjectName("SegmentedBar")
        self.mode_tabs.tabBar().setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # ---------------------------------------------------------
        # TAB 1: D-FLOW (Flexible Mesh)
        # ---------------------------------------------------------
        tab_flow = QWidget()
        flow_lay = QHBoxLayout(tab_flow)
        flow_lay.setContentsMargins(20, 24, 20, 20)
        flow_lay.setSpacing(24)
        
        # D-FLOW LEFT: Domain & Boundary Geometry
        fc1 = QVBoxLayout()
        fgrp1 = QGroupBox("Geometri Pesisir & Area Of Interest (AOI)")
        fg1 = QVBoxLayout(fgrp1)
        fg1.setSpacing(16)
        
        aoi_info = QLabel("<b>Makro (Outer):</b> Otomatis setara Grid ERA5 (Read-Only)<br><b>Mikro (Inner):</b> Gambarlah kotak di Peta (Area Refinement)")
        aoi_info.setStyleSheet("color: #9CA3AF; font-size: 13px; line-height: 1.4;")
        fg1.addWidget(aoi_info)
        
        self.lbl_inner_bbox = QLabel("BBOX Mikro (Inner): Belum Digambar")
        self.lbl_inner_bbox.setStyleSheet("color:#FC3F4D; font-weight:bold; font-size:12px; background-color: #1F2227; padding: 10px; border-radius: 6px; border: 1px solid #3A3F4A;")
        self.lbl_inner_bbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fg1.addWidget(self.lbl_inner_bbox)
        
        h_shp = QHBoxLayout()
        btn_shp = QPushButton("🗺️ Coastline (.shp / .ldb)")
        btn_shp.setObjectName("OutlineBtn")
        btn_shp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_shp.clicked.connect(self.import_aoi_shapefile)
        self.lbl_coast_stat = QLabel("Tidak Ada")
        self.lbl_coast_stat.setStyleSheet("color: #6B7280; font-weight: bold; font-size: 12px;")
        h_shp.addWidget(btn_shp, stretch=1)
        h_shp.addWidget(self.lbl_coast_stat, stretch=1)
        fg1.addLayout(h_shp)
        
        self.chk_clip_land = QCheckBox("Hapus Node Daratan (Clip Landward Edge)")
        self.chk_clip_land.setChecked(True)
        self.chk_clip_land.setToolTip("Otomatis menghapus mesh yang tumpang tindih dengan poligon daratan.")
        fg1.addWidget(self.chk_clip_land)
        
        fg1.addWidget(QLabel("Titik Transek (Morphodynamics DoC):", styleSheet="color: #8FC9DC; font-weight: 800; font-size: 13px; margin-top: 10px;"))
        
        # Tabel D-Flow hanya sebagai representasi visual state, tidak perlu itemChanged otomatis
        self.tbl_trans = QTableWidget(2, 2)
        self.tbl_trans.setHorizontalHeaderLabels(["Lat (Y)", "Lon (X)"])
        self.tbl_trans.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_trans.setMaximumHeight(90)
        fg1.addWidget(self.tbl_trans)
        
        fc1.addWidget(fgrp1)
        fc1.addStretch()
        flow_lay.addLayout(fc1, stretch=1)
        
        # D-FLOW RIGHT: Physics & Mesh Rules
        fc2 = QVBoxLayout()
        fgrp2 = QGroupBox("Batimetri, Fisika Batas & Resolusi (MDU)")
        fg2 = QFormLayout(fgrp2)
        fg2.setHorizontalSpacing(16)
        fg2.setVerticalSpacing(16)
        
        btn_b = QPushButton("📂 File Batimetri (.xyz)")
        btn_b.setObjectName("OutlineBtn")
        btn_b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_b.clicked.connect(lambda: self.load_mesh_file('bathy'))
        self.lbl_bathy_stat = QLabel("Tidak Ada")
        self.lbl_bathy_stat.setStyleSheet("color: #6B7280; font-weight: bold; font-size: 12px;")
        hb = QHBoxLayout()
        hb.addWidget(btn_b); hb.addWidget(self.lbl_bathy_stat)
        fg2.addRow(hb)
        
        self.cmb_bnd_dir = QComboBox()
        self.cmb_bnd_dir.addItems(["South", "North", "East", "West"])
        self.cmb_bnd_dir.setItemText(0, "Selatan (Samudra Hindia)")
        fg2.addRow(QLabel("Arah Laut Lepas:", styleSheet="color: #9CA3AF; font-weight: bold;"), self.cmb_bnd_dir)
        
        self.chk_riemann = QCheckBox("Gunakan Riemann Absorbing Boundary")
        self.chk_riemann.setChecked(True)
        fg2.addRow("", self.chk_riemann)
        
        self.sld_fmax, self.inp_fmax = self.create_slider_row(50, 1000, 750) # Coarse default 750
        fg2.addRow(QLabel("Res. Kasar (Outer):", styleSheet="color: #8FC9DC; font-weight: bold;"), self.make_hbox(self.sld_fmax, self.inp_fmax))
        
        self.sld_fmin, self.inp_fmin = self.create_slider_row(5, 100, 12)
        fg2.addRow(QLabel("Res. Halus (Inner):", styleSheet="color: #8FC9DC; font-weight: bold;"), self.make_hbox(self.sld_fmin, self.inp_fmin))
        
        btn_doc = QPushButton("🔭 Kalkulasi DoC (Depth of Closure)")
        btn_doc.setObjectName("OutlineBtn")
        btn_doc.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_doc.clicked.connect(self.run_doc_calc)
        fg2.addRow(btn_doc)
        
        fc2.addWidget(fgrp2)
        fc2.addStretch()
        flow_lay.addLayout(fc2, stretch=1)
        
        self.mode_tabs.addTab(tab_flow, "🌊 D-FLOW (Flexible Mesh)")
        
        # ---------------------------------------------------------
        # TAB 2: D-WAVES (Rectilinear Grid)
        # ---------------------------------------------------------
        tab_wave = QWidget()
        wave_lay = QHBoxLayout(tab_wave)
        wave_lay.setContentsMargins(20, 24, 20, 20)
        wave_lay.setSpacing(24)
        
        wc1 = QVBoxLayout()
        wgrp1 = QGroupBox("Domain Gelombang & Geometri Grid")
        wg1 = QVBoxLayout(wgrp1)
        wg1.setSpacing(16)
        
        info_wave = QLabel("Modul SWAN (D-Waves) beroperasi pada domain bersarang (Nested) atau grid Rectilinear untuk stabilitas komputasi.")
        info_wave.setStyleSheet("color: #9CA3AF; font-size: 13px; line-height: 1.4;")
        info_wave.setWordWrap(True)
        wg1.addWidget(info_wave)
        
        self.lbl_outer_bbox = QLabel("BBOX Makro (ERA5): Belum Tersedia")
        self.lbl_outer_bbox.setStyleSheet("color:#FC3F4D; font-weight:bold; font-size:12px; background-color: #1F2227; padding: 10px; border-radius: 6px; border: 1px solid #3A3F4A;")
        self.lbl_outer_bbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wg1.addWidget(self.lbl_outer_bbox)
        
        w_form = QFormLayout()
        w_form.setVerticalSpacing(16)
        w_form.setHorizontalSpacing(16)
        self.sld_wmax, self.inp_wmax = self.create_slider_row(50, 1000, 250)
        w_form.addRow(QLabel("Res. DX/DY Kasar:", styleSheet="color: #8FC9DC; font-weight: bold;"), self.make_hbox(self.sld_wmax, self.inp_wmax))
        self.sld_wmin, self.inp_wmin = self.create_slider_row(10, 200, 25)
        w_form.addRow(QLabel("Res. DX/DY Halus:", styleSheet="color: #8FC9DC; font-weight: bold;"), self.make_hbox(self.sld_wmin, self.inp_wmin))
        wg1.addLayout(w_form)
        
        wc1.addWidget(wgrp1)
        wc1.addStretch()
        wave_lay.addLayout(wc1, stretch=1)
        
        wc2 = QVBoxLayout()
        wgrp2 = QGroupBox("Parameter Gelombang Fisik (MDW)")
        wg2 = QFormLayout(wgrp2)
        wg2.setHorizontalSpacing(16)
        wg2.setVerticalSpacing(16)
        
        self.cmb_w_fric = QComboBox()
        self.cmb_w_fric.addItems(["JONSWAP", "COLLINS", "MADSEN"])
        wg2.addRow(QLabel("Bottom Friction:", styleSheet="color: #9CA3AF; font-weight: bold;"), self.cmb_w_fric)
        
        self.inp_gamma = QLineEdit("0.73")
        self.inp_gamma.setFixedWidth(80)
        wg2.addRow(QLabel("Gamma Breaking:", styleSheet="color: #9CA3AF; font-weight: bold;"), self.inp_gamma)
        
        self.inp_w_level = QLineEdit("0.0")
        self.inp_w_level.setFixedWidth(80)
        self.inp_w_level.setToolTip("Hanya digunakan pada Tahap 2 (D-WAVES Standalone) sebagai elevasi referensi pengganti pasang surut D-FLOW.")
        wg2.addRow(QLabel("Elevasi Air Konstan (m):", styleSheet="color: #F7C159; font-weight: bold;"), self.inp_w_level)
        
        self.lbl_w_ic = QLabel("Hs: - m | Tp: - s | Dir: - °")
        self.lbl_w_ic.setStyleSheet("color: #595FF7; font-weight: bold; font-family: 'Consolas', monospace; font-size: 13px; padding: 10px; background: #1F2227; border-radius: 8px; border: 1px solid #3A3F4A;")
        wg2.addRow(QLabel("Initial Condition:", styleSheet="color: #9CA3AF; font-weight: bold;"), self.lbl_w_ic)
        
        wc2.addWidget(wgrp2)
        wc2.addStretch()
        wave_lay.addLayout(wc2, stretch=1)
        
        self.mode_tabs.addTab(tab_wave, "〰️ D-WAVES (Rectilinear Grid)")
        scroll_layout.addWidget(self.mode_tabs)

        self.lbl_cost = QLabel("Estimasi Beban Komputasi: Menghitung...")
        self.lbl_cost.setStyleSheet("background-color: #1F2227; padding: 12px; border: 1px solid #3A3F4A; border-radius: 8px; font-size: 13px; font-weight: bold; color: #9CA3AF;")
        self.lbl_cost.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(self.lbl_cost)

        # --- BUILD STRATEGY & EXECUTION BUTTON ---
        bgrp = QGroupBox("3. Strategi Kompilasi & Kalibrasi")
        blay = QVBoxLayout(bgrp)
        blay.setSpacing(16)
        
        info_b = QLabel("PENTING: Praktik oseanografi numerik mensyaratkan kalibrasi muka air pasut (D-FLOW) secara terpisah sebelum melakukan Full Coupling dengan gelombang (D-WAVES) untuk menghindari *error* berantai. Gunakan Tahap 1 dan Tahap 2 sebelum melakukan Full Coupling.")
        info_b.setStyleSheet("color: #F7C159; font-size: 12px; line-height: 1.4; font-style: italic;")
        info_b.setWordWrap(True)
        blay.addWidget(info_b)
        
        self.cmb_build_mode = QComboBox()
        self.cmb_build_mode.addItems([
            "Tahap 1: D-FLOW Standalone (Kalibrasi Muka Air & Pasut)",
            "Tahap 2: D-WAVES Standalone (Kalibrasi Setup Gelombang)",
            "Tahap 3: FULL COUPLING DIMR (Interaksi Flow-Wave Dinamis)"
        ])
        self.cmb_build_mode.currentTextChanged.connect(self._update_build_btn_text)
        blay.addWidget(self.cmb_build_mode)

        self.btn_mesh = QPushButton("⚡ RAKIT D-FLOW STANDALONE (.mdu)")
        self.btn_mesh.setObjectName("PrimaryBtn")
        self.btn_mesh.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_mesh.clicked.connect(self.run_dimr_pipeline)
        blay.addWidget(self.btn_mesh)
        
        scroll_layout.addWidget(bgrp)

        # --- TERMINAL LOG ---
        bl = QVBoxLayout()
        bl.setContentsMargins(0, 10, 0, 0)
        bl.addWidget(QLabel("System Trace (Dimr Orchestrator):", styleSheet="font-weight:900; color:#8FC9DC; font-size: 14px;"))
        self.log_mesh = QTextEdit()
        self.log_mesh.setReadOnly(True)
        self.log_mesh.setStyleSheet("background-color: #1E2128; color: #8FC9DC; font-family: Consolas, monospace; font-size: 13px; border: 1px solid #3A3F4A; border-radius: 8px; padding: 12px;")
        self.log_mesh.setMinimumHeight(150)
        bl.addWidget(self.log_mesh)
        scroll_layout.addLayout(bl)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        bot_layout.addWidget(scroll)
        splitter.addWidget(bot_widget)
        
        splitter.setSizes([500, 400])
        main_layout.addWidget(splitter)

        self.sld_fmax.valueChanged.connect(self.update_sliders)
        self.sld_fmin.valueChanged.connect(self.update_sliders)

    # --------------------------------------------------------------------------
    # UI HELPER FUNCTIONS
    # --------------------------------------------------------------------------
    def _update_build_btn_text(self, text: str) -> None:
        if "Tahap 1" in text:
            self.btn_mesh.setText("⚡ RAKIT D-FLOW STANDALONE (.mdu)")
        elif "Tahap 2" in text:
            self.btn_mesh.setText("⚡ RAKIT D-WAVES STANDALONE (.mdw)")
        else:
            self.btn_mesh.setText("⚡ RAKIT FULL COUPLING (DIMR XML)")

    def create_slider_row(self, min_val, max_val, default_val):
        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(min_val, max_val)
        sld.setValue(default_val)
        inp = QLineEdit(str(default_val))
        inp.setFixedWidth(60)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        sld.valueChanged.connect(lambda v: inp.setText(str(v)))
        inp.textChanged.connect(lambda t: sld.setValue(int(t) if t.isdigit() else default_val))
        return sld, inp

    def make_hbox(self, widget1, widget2):
        h = QHBoxLayout()
        h.setSpacing(12)
        h.addWidget(widget1, stretch=4)
        h.addWidget(widget2, stretch=1)
        return h

    # --------------------------------------------------------------------------
    # DATA INGESTION & UI SYNCHRONIZATION
    # --------------------------------------------------------------------------

    def on_global_state_changed(self, key: str) -> None:
        state = app_state.get_all()
        
        if key in ['Hs', 'Tp', 'Dir']:
            self.lbl_w_ic.setText(f"Hs: {state.get('Hs',0):.1f}m | Tp: {state.get('Tp',0):.1f}s | Dir: {state.get('Dir',0):.1f}°")
            
        if key == 'Dir':
            dir_val = state.get('Dir', 180.0)
            if 45 <= dir_val < 135: bnd = "East"
            elif 135 <= dir_val < 225: bnd = "South"
            elif 225 <= dir_val < 315: bnd = "West"
            else: bnd = "North"
                
            idx = self.cmb_bnd_dir.findData(bnd)
            if idx >= 0:
                self.cmb_bnd_dir.setCurrentIndex(idx)
                self.log_mesh.append(f"[AUTO-SYNC] Arah gelombang ERA5 ({dir_val:.1f}°) terdeteksi. Batas laut disetel ke: {bnd}.")
                
        if key == 'mesh_bbox':
            outer = state.get('mesh_bbox')
            if outer:
                self.lbl_outer_bbox.setText(f"✓ Makro BBox: N{outer['N']:.2f}, S{outer['S']:.2f}, E{outer['E']:.2f}, W{outer['W']:.2f}")
                self.lbl_outer_bbox.setStyleSheet("color:#42E695; font-weight:bold; font-size:12px; background-color: rgba(66, 230, 149, 0.1); padding: 10px; border-radius: 6px; border: 1px solid #42E695;")
                
                js_outer = f"var outB = [[{outer['S']}, {outer['W']}], [{outer['N']}, {outer['E']}]]; L.rectangle(outB, {{color: '#FC3F4D', weight: 2, fillOpacity: 0.05, dashArray: '5, 10'}}).addTo(map); map.fitBounds(outB);"
                self.web_mesh.page().runJavaScript(js_outer)
                
            # [ENTERPRISE BUG-FIX]: Trigger ulang kalkulasi biaya HPC saat batas makro berubah
            self.update_sliders()

    def load_mesh_file(self, ftype: str) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Pilih File", "", "XYZ Data (*.xyz)")
        if p:
            self.file_bathy = os.path.abspath(p)
            self.lbl_bathy_stat.setText(f"✓ {os.path.basename(p)}")
            self.lbl_bathy_stat.setStyleSheet("color: #42E695;")

    def import_aoi_shapefile(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Pilih Pesisir / Land Boundary", "", "Vector & Boundary (*.shp *.ldb *.kml *.geojson)")
        if not p: return
        
        try:
            if p.endswith('.ldb'):
                self.file_ldb = os.path.abspath(p)
                self.lbl_coast_stat.setText(f"✓ LDB Native")
                self.lbl_coast_stat.setStyleSheet("color: #595FF7;")
                return
                
            if not HAS_GEOPANDAS: 
                QMessageBox.critical(self, "Missing Library", "Pustaka 'geopandas' diperlukan untuk membaca .shp.")
                return
                
            self.log_mesh.append("▶ Konversi .shp ke .ldb...")
            gdf = gpd.read_file(p)
            if gdf.crs is None or gdf.crs.to_epsg() != 4326: 
                gdf = gdf.to_crs(epsg=4326)
                
            ldb_path = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports', 'coastline_auto.ldb'))
            
            with open(ldb_path, 'w', encoding='utf-8') as f:
                bnd_counter = 1
                for i, row in gdf.iterrows():
                    geom = row.geometry
                    if geom is None: continue
                    
                    geoms = [geom] if geom.geom_type in ['Polygon', 'LineString'] else geom.geoms
                    
                    for g in geoms:
                        if g.geom_type == 'Polygon':
                            coords = list(g.exterior.coords)
                        elif g.geom_type == 'LineString':
                            coords = list(g.coords)
                        else: continue
                            
                        f.write(f"Bnd_{bnd_counter}\n{len(coords)} 2\n")
                        for coord in coords: 
                            f.write(f"{coord[0]:.3f} {coord[1]:.3f}\n")
                        bnd_counter += 1
                            
            self.file_ldb = ldb_path
            self.lbl_coast_stat.setText(f"✓ SHP Converted")
            self.lbl_coast_stat.setStyleSheet("color: #42E695;")
            
            js = f"addGeoJSON({gdf.to_json()}, '#8FC9DC');"
            self.web_mesh.page().runJavaScript(js)
            
            self.log_mesh.append(f"✅ Vektor dikonversi sukses menjadi {os.path.basename(ldb_path)} (Format Delft3D).")
            QMessageBox.information(self, "Konversi Sukses", "Shapefile berhasil dikonversi dan disuntikkan ke dalam Leaflet.")
            
        except Exception as e:
            logger.error(f"[LDB IMPORT] {str(e)}\n{traceback.format_exc()}")
            self.log_mesh.append(f"❌ Gagal memproses Coastline: {str(e)}")

    def update_inner_bbox(self, d: dict) -> None: 
        """Ditangkap dari alat gambar kotak pada peta Leaflet."""
        self._syncing = True
        app_state.update('inner_bbox', d)
        self.lbl_inner_bbox.setText("✓ Area Mikro (Inner) Tersimpan")
        self.lbl_inner_bbox.setStyleSheet("color:#595FF7; font-weight:bold; font-size:12px; background-color: rgba(89, 95, 247, 0.1); padding: 10px; border-radius: 6px; border: 1px solid #595FF7;")
        
        self.tbl_bbox.blockSignals(True)
        self.tbl_bbox.setItem(0, 0, QTableWidgetItem(f"{d['N']:.4f}"))
        self.tbl_bbox.setItem(1, 0, QTableWidgetItem(f"{d['S']:.4f}"))
        self.tbl_bbox.setItem(2, 0, QTableWidgetItem(f"{d['E']:.4f}"))
        self.tbl_bbox.setItem(3, 0, QTableWidgetItem(f"{d['W']:.4f}"))
        self.tbl_bbox.blockSignals(False)
        self.update_sliders()
        self._syncing = False

    def update_mesh_transect(self, d: list) -> None: 
        """Ditangkap dari alat gambar garis poli (Polyline) pada peta Leaflet."""
        self._syncing = True
        app_state.update('transect', d)
        self.tbl_trans.setRowCount(len(d))
        self.tbl_trans.blockSignals(True)
        for i, coord in enumerate(d):
            for col, val in enumerate([coord[0], coord[1]]):
                item = QTableWidgetItem(f"{val:.4f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl_trans.setItem(i, col, item)
        self.tbl_trans.blockSignals(False)
        self._syncing = False

    def manual_bbox_update(self) -> None:
        """Dipicu HANYA jika tombol 'Update Area Mikro' diklik."""
        try:
            n = float(self.tbl_bbox.item(0,0).text())
            s = float(self.tbl_bbox.item(1,0).text())
            e = float(self.tbl_bbox.item(2,0).text())
            w = float(self.tbl_bbox.item(3,0).text())
            
            if n > s and e > w:
                app_state.update('inner_bbox', {'N': n, 'S': s, 'E': e, 'W': w})
                js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{w},{s}],[{e},{s}],[{e},{n}],[{w},{n}],[{w},{s}]]]}}, '#595FF7');"
                self.web_mesh.page().runJavaScript("clearMap(); " + js_box)
                self.log_mesh.append("[SYSTEM] BBox Peta berhasil diperbarui secara manual.")
                self.update_sliders()
            else:
                QMessageBox.warning(self, "Galat Logika", "Koordinat terbalik. N harus lebih besar dari S, E harus lebih besar dari W.")
        except Exception: 
            pass

    def manual_transect_update(self) -> None:
        """Dipicu HANYA jika tombol 'Update Line Profiles' diklik."""
        coords = []
        for i in range(self.tbl_man.rowCount()):
            try:
                lat = float(self.tbl_man.item(i,0).text())
                lon = float(self.tbl_man.item(i,1).text())
                coords.append([lat, lon]) 
            except Exception: pass
            
        if len(coords) >= 2:
            app_state.update('transect', coords)
            js_line = f"addGeoJSON({{\"type\":\"LineString\",\"coordinates\":{json.dumps([[c[1], c[0]] for c in coords])}}}, '#8FC9DC');"
            self.web_mesh.page().runJavaScript(js_line)
            self.log_mesh.append("[SYSTEM] Garis Transek berhasil diperbarui secara manual.")

    def update_sliders(self) -> None:
        """
        [ENTERPRISE BUG-FIX] Kalkulasi Cost Numerik yang Akurat.
        Memisahkan estimasi jumlah node antara area Macro (kasar) dan Micro (halus)
        agar sistem tidak asal menebak beban HPC 'BERAT' pada area yang dominan kasar.
        """
        max_r = self.sld_fmax.value()
        min_r = self.sld_fmin.value()
        
        if min_r >= max_r: 
            self.lbl_cost.setText("⚠ ERROR: Resolusi Halus (Inner) tidak boleh >= Resolusi Kasar (Outer).")
            self.lbl_cost.setStyleSheet("color: #FC3F4D; font-weight:bold; font-size:13px; background-color: rgba(252, 63, 77, 0.1); padding: 12px; border-radius: 8px; border: 1px solid #FC3F4D;")
            return
            
        macro = app_state.get('mesh_bbox')
        micro = app_state.get('inner_bbox')
        
        # Konversi sederhana derajat ke meter: 1 deg = ~111,320 meter ekuator
        macro_area_m2 = 0
        micro_area_m2 = 0
        
        if macro:
            macro_area_m2 = abs(macro['E'] - macro['W']) * 111320 * abs(macro['N'] - macro['S']) * 110540 
            
        if micro:
            micro_area_m2 = abs(micro['E'] - micro['W']) * 111320 * abs(micro['N'] - micro['S']) * 110540
            
        # Jika belum ada AOI sama sekali, gunakan angka default (Contoh: area 5x5 km)
        if macro_area_m2 == 0 and micro_area_m2 == 0:
            macro_area_m2 = 25000000 
            
        # Kurangi area luar agar tidak dihitung dua kali
        outer_area_m2 = max(0, macro_area_m2 - micro_area_m2)
        
        # Hitung jumlah titik (nodes)
        nodes_outer = outer_area_m2 / (max_r ** 2) if max_r > 0 else 0
        nodes_inner = micro_area_m2 / (min_r ** 2) if min_r > 0 else 0
        
        est_nodes = nodes_outer + nodes_inner
        
        if est_nodes < 30000:
            status, color = "🟢 Ringan (PC/Laptop Biasa)", "#42E695"
            bg, brd = "rgba(66, 230, 149, 0.1)", "#42E695"
        elif est_nodes < 100000:
            status, color = "🟡 Menengah (Workstation i7/Ryzen 7)", "#F7C159"
            bg, brd = "rgba(247, 193, 89, 0.1)", "#F7C159"
        else:
            status, color = "🔴 BERAT (Membutuhkan HPC/Superkomputer)", "#FC3F4D"
            bg, brd = "rgba(252, 63, 77, 0.1)", "#FC3F4D"
            
        # Mengubah luas dari meter persegi ke kilometer persegi untuk UI
        total_km2 = max(macro_area_m2, micro_area_m2) / 1e6
        self.lbl_cost.setText(f"Cakupan Geografis: {total_km2:.1f} km² | Beban: ~{int(est_nodes):,} Titik Komputasi (Nodes) | {status}")
        self.lbl_cost.setStyleSheet(f"color: {color}; font-weight:bold; font-size:13px; background-color:{bg}; padding: 12px; border-radius: 8px; border: 1px solid {brd};")

    # --------------------------------------------------------------------------
    # THREAD EXECUTION
    # --------------------------------------------------------------------------

    def run_doc_calc(self) -> None:
        if hasattr(self, 'doc_w') and self.doc_w.isRunning(): return
        
        if not self.file_bathy or not app_state.get('transect') or app_state.get('Hs', 0) == 0: 
            QMessageBox.critical(self, "Syarat Kurang", "Berkas Batimetri (.xyz), Garis Transek, dan Parameter Gelombang (Hs) dari Modul ERA5 wajib ada.")
            return
            
        self.doc_w = DepthOfClosure2DWorker(self.file_bathy, app_state.get('transect'), app_state.get('He', 1.5), app_state.get('EPSG', '32749'))
        self.doc_w.log_signal.connect(self.log_mesh.append)
        
        def on_doc_done(success: bool):
            if success: self.log_mesh.append("✅ Depth of Closure (DoC) telah dikunci ke Global State.")
            self.doc_w.deleteLater()
            
        self.doc_w.doc_val_signal.connect(lambda v: app_state.update('DoC', v))
        self.doc_w.plot_signal.connect(self.on_doc_plot)
        self.doc_w.finished_signal.connect(on_doc_done)
        self.doc_w.start()

    def on_doc_plot(self, plot_path: str) -> None:
        if plot_path and os.path.exists(plot_path): 
            self.lbl_doc_plot.setPixmap(QPixmap(plot_path).scaled(self.lbl_doc_plot.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.gis_tabs_m.setCurrentIndex(2)

    def run_dimr_pipeline(self) -> None:
        if hasattr(self, 'dimr_worker') and self.dimr_worker.isRunning(): return

        state = app_state.get_all()
        
        if not state.get('sim_start_time') or not state.get('sim_end_time'):
            QMessageBox.critical(self, "Waktu Tidak Selaras", "Rentang waktu simulasi belum dikunci dari Modul 1. Mesin DIMR membutuhkan ketetapan waktu mutlak.")
            return

        mode_text = self.cmb_build_mode.currentText()
        if "Tahap 1" in mode_text: b_mode = "dflow_only"
        elif "Tahap 2" in mode_text: b_mode = "dwaves_only"
        else: b_mode = "coupled"
        
        p = {
            'he': state.get('He', 1.5), 
            'doc': state.get('DoC', 0), 
            'epsg': state.get('EPSG', '32749'), 
            'aoi_bounds': state.get('mesh_bbox'), 
            'inner_bbox': state.get('inner_bbox'), 
            'transect': state.get('transect'), 
            'bathy_file': self.file_bathy, 
            'ldb_file': self.file_ldb,
            'clip_landward': self.chk_clip_land.isChecked(),
            'sediment_file': state.get('sediment_xyz', ""), 
            'tide_bc': state.get('tide_bc', ""),
            
            'build_mode': b_mode,
            
            'max_res': self.sld_fmax.value(), 
            'min_res': self.sld_fmin.value(), 
            'ocean_boundary_dir': self.cmb_bnd_dir.currentData(), 
            'use_riemann': self.chk_riemann.isChecked(),
            
            'w_max_res': self.sld_wmax.value(),
            'w_min_res': self.sld_wmin.value(),
            'w_fric_type': self.cmb_w_fric.currentText(),
            'w_gamma': float(self.inp_gamma.text() or 0.73),
            'w_level': float(self.inp_w_level.text() or 0.0),
            
            'out_dir': os.path.abspath(os.path.join(os.getcwd(), 'Apex_FM_Model_Final'))
        }
        
        if not p['bathy_file'] or not p['aoi_bounds'] or not p['inner_bbox']:
            QMessageBox.critical(self, "Berkas Belum Lengkap", "Batimetri, BBox Makro (ERA5), dan BBox Mikro wajib disetel untuk merakit jaring arsitektur komputasi (Mesh).")
            return

        self.btn_mesh.setEnabled(False)
        self.btn_mesh.setText("⏳ MEMPROSES ARSITEKTUR GRID...")
        self.log_mesh.clear()
        
        self.dimr_worker = ApexDIMROrchestratorWorker(p, state)
        self.dimr_worker.log_signal.connect(self.log_mesh.append)
        self.dimr_worker.preview_signal.connect(self.show_mesh_preview)
        
        def on_mesh_done(status: str, success: bool):
            self.btn_mesh.setEnabled(True)
            self._update_build_btn_text(self.cmb_build_mode.currentText()) 
            if success: 
                QMessageBox.information(self, "Kompilasi Sukses", f"Eksekusi perakitan mesh dan konfigurasi ({b_mode}) berhasil diselesaikan.")
            self.dimr_worker.deleteLater()
            
        self.dimr_worker.finished_signal.connect(on_mesh_done)
        self.dimr_worker.start()

    def show_mesh_preview(self, img_path: str) -> None:
        if img_path and os.path.exists(img_path):
            self.lbl_mesh_preview.setPixmap(QPixmap(img_path).scaled(self.lbl_mesh_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.gis_tabs_m.setCurrentIndex(1)
