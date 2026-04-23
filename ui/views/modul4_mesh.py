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
                             QSlider, QComboBox, QCheckBox, QHeaderView)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

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

# --- ENTERPRISE QSS STYLESHEETS (REVOLUT / GRADIENTA INFLUENCE) ---
STYLE_GROUPBOX = """
    QGroupBox { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; margin-top: 24px; padding-top: 15px; font-weight: bold; color: #F1F5F9; font-size: 14px; }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 10px; background-color: #0F172A; border-radius: 6px; color: #F59E0B; top: -12px; left: 15px; }
"""
STYLE_INPUTS = """
    QLineEdit, QComboBox { background-color: #0F172A; border: 1px solid #475569; border-radius: 6px; padding: 8px 12px; color: #F8FAFC; font-size: 13px; }
    QLineEdit:focus, QComboBox:focus { border: 1px solid #F59E0B; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { background-color: #1E293B; color: #F8FAFC; selection-background-color: #334155; border: 1px solid #475569; border-radius: 6px; }
    QCheckBox { color: #CBD5E1; font-size: 13px; }
    QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #475569; background: #0F172A; }
    QCheckBox::indicator:checked { background: #F59E0B; border: 1px solid #D97706; }
"""
STYLE_BTN_PRIMARY = """
    QPushButton#ExecuteBtn { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F59E0B, stop:1 #D97706); color: #022C22; border: none; border-radius: 8px; padding: 10px 16px; font-weight: bold; font-size: 14px; }
    QPushButton#ExecuteBtn:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FCD34D, stop:1 #F59E0B); }
    QPushButton#ExecuteBtn:pressed { background-color: #B45309; }
    QPushButton#ExecuteBtn:disabled { background-color: #334155; color: #94A3B8; }
"""
STYLE_BTN_OUTLINE = """
    QPushButton#OutlineBtn { background-color: transparent; color: #F8FAFC; border: 1px solid #64748B; border-radius: 8px; padding: 10px 16px; font-weight: bold; }
    QPushButton#OutlineBtn:hover { background-color: #334155; border-color: #F59E0B; color: #F59E0B; }
"""
STYLE_SLIDER = """
    QSlider::groove:horizontal { border-radius: 4px; height: 8px; margin: 0px; background-color: #334155; }
    QSlider::handle:horizontal { background-color: #F59E0B; border: 2px solid #FFFFFF; width: 16px; height: 16px; margin: -4px 0; border-radius: 8px; }
    QSlider::handle:horizontal:hover { background-color: #FCD34D; }
    QSlider::sub-page:horizontal { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #F59E0B); border-radius: 4px; }
"""


class Modul4Mesh(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_bathy = ""
        self.file_ldb = ""
        self.setup_ui()
        # [NEW INJECTION]: Memasang telinga pendengar ke Memori Global
        app_state.state_updated.connect(self.on_global_state_changed)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_BTN_PRIMARY} {STYLE_BTN_OUTLINE} {STYLE_SLIDER}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER ---
        head = QVBoxLayout()
        t = QLabel("DIMR Coupler Builder & Topology")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Merakit topologi mesh adaptif (Unstructured), DoC Profiler, dan injeksi XML Coupler (Flow <-> Wave).")
        d.setStyleSheet("color: #94A3B8; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        # --- 1. TOP SECTION (MAP / TABS) ---
        self.gis_tabs_m = QTabWidget()
        self.gis_tabs_m.setMinimumHeight(400)
        self.gis_tabs_m.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; border-radius: 8px; background: #1E293B; }
            QTabBar::tab { background: #0F172A; color: #94A3B8; padding: 10px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;}
            QTabBar::tab:selected { background: #1E293B; color: #F59E0B; font-weight: bold; border-bottom: 2px solid #F59E0B;}
        """)
        
        tab_map = QWidget()
        lay_map = QVBoxLayout(tab_map)
        lay_map.setContentsMargins(1, 1, 1, 1)
        
        self.web_mesh = QWebEngineView()
        self.bridge_mesh = WebBridge()
        self.bridge_mesh.bbox_drawn.connect(self.update_mesh_bbox)
        self.bridge_mesh.transect_drawn.connect(self.update_mesh_transect)
        
        self.web_mesh.page().setWebChannel(QWebChannel(self.web_mesh.page()))
        self.web_mesh.page().webChannel().registerObject("bridge", self.bridge_mesh)
        self.web_mesh.setHtml(get_leaflet_html("mesh"))
        
        lay_map.addWidget(self.web_mesh)
        self.gis_tabs_m.addTab(tab_map, "Peta Interaktif (Leaflet)")

        tab_mesh_viz = QWidget()
        lay_mz = QVBoxLayout(tab_mesh_viz)
        self.lbl_mesh_preview = QLabel("Topology UGRID Mesh Preview akan muncul di sini setelah kompilasi.")
        self.lbl_mesh_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mesh_preview.setStyleSheet("color: #64748B; font-weight: bold;")
        lay_mz.addWidget(self.lbl_mesh_preview)
        self.gis_tabs_m.addTab(tab_mesh_viz, "Topologi Mesh")

        tab_doc = QWidget()
        lay_doc = QVBoxLayout(tab_doc)
        self.lbl_doc_plot = QLabel("Plot DoC 2D Panorama Cross Section akan dirender di sini.")
        self.lbl_doc_plot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_doc_plot.setStyleSheet("color: #64748B; font-weight: bold;")
        lay_doc.addWidget(self.lbl_doc_plot)
        self.gis_tabs_m.addTab(tab_doc, "Panorama DoC")
        
        top_section = QHBoxLayout()
        top_section.setSpacing(16)
        top_section.addWidget(self.gis_tabs_m, stretch=7)
        
        # RIGHT PANEL: AOI & Transect Manual Input
        self.tabs_aoi = QTabWidget()
        self.tabs_aoi.setStyleSheet(self.gis_tabs_m.styleSheet())
        
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(16, 16, 16, 16)
        l1.addWidget(QLabel("Koordinat BBox (Lat/Lon):", styleSheet="color: #F8FAFC; font-weight:bold;"))
        self.tbl_bbox = QTableWidget(4, 1)
        self.tbl_bbox.setStyleSheet("QTableWidget { background-color: #0F172A; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; }")
        self.tbl_bbox.setVerticalHeaderLabels(["North", "South", "East", "West"])
        self.tbl_bbox.horizontalHeader().setVisible(False)
        self.tbl_bbox.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_bbox.setMaximumHeight(140)
        for j in range(4): self.tbl_bbox.setItem(j, 0, QTableWidgetItem(""))
        self.tbl_bbox.itemChanged.connect(self.manual_update_bbox_vertical)
        l1.addWidget(self.tbl_bbox)
        btn_m1 = QPushButton("Update BBox Area")
        btn_m1.setObjectName("OutlineBtn")
        btn_m1.clicked.connect(self.manual_map_update)
        l1.addWidget(btn_m1)
        l1.addStretch()
        self.tabs_aoi.addTab(t1, "Set BBox")
        
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(16, 16, 16, 16)
        l2.addWidget(QLabel("Manual Transect Nodes:", styleSheet="color: #F8FAFC; font-weight:bold;"))
        self.tbl_man = QTableWidget(2, 2)
        self.tbl_man.setStyleSheet("QTableWidget { background-color: #0F172A; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; }")
        self.tbl_man.setHorizontalHeaderLabels(["Lat (Y)", "Lon (X)"])
        self.tbl_man.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_man.setMaximumHeight(100)
        self.tbl_man.setItem(0, 0, QTableWidgetItem("-8.460"))
        self.tbl_man.setItem(0, 1, QTableWidgetItem("112.616"))
        self.tbl_man.setItem(1, 0, QTableWidgetItem("-8.415"))
        self.tbl_man.setItem(1, 1, QTableWidgetItem("112.717"))
        l2.addWidget(self.tbl_man)
        btn_m2 = QPushButton("Update Line Profiles")
        btn_m2.setObjectName("OutlineBtn")
        btn_m2.clicked.connect(self.manual_map_update)
        l2.addWidget(btn_m2)
        l2.addStretch()
        self.tabs_aoi.addTab(t2, "Transect")
        
        top_section.addWidget(self.tabs_aoi, stretch=3)
        main_layout.addLayout(top_section, stretch=1)

        # --- 2. BOTTOM SECTION (CONTROLS IN SCROLLAREA) ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(20)

        # Col 1: Boundary & Input Editor
        c1 = QVBoxLayout()
        grp1 = QGroupBox("1. Input Data & Oseanografi Fisik")
        g1 = QVBoxLayout(grp1)
        g1.setSpacing(14)
        
        # [NEW FEATURE]: Dynamic Ocean Boundary Direction
        h_dir = QHBoxLayout()
        h_dir.addWidget(QLabel("Arah Laut Lepas:", styleSheet="color: #CBD5E1;"))
        self.cmb_bnd_dir = QComboBox()
        self.cmb_bnd_dir.addItem("Selatan (Samudra Hindia)", "South")
        self.cmb_bnd_dir.addItem("Utara (Laut Jawa)", "North")
        self.cmb_bnd_dir.addItem("Timur", "East")
        self.cmb_bnd_dir.addItem("Barat", "West")
        h_dir.addWidget(self.cmb_bnd_dir)
        g1.addLayout(h_dir)
        
        # [NEW FEATURE]: Riemann Absorbing Boundary
        self.chk_riemann = QCheckBox("Gunakan Riemann Absorbing Boundary (Mencegah Refleksi Buatan)")
        self.chk_riemann.setChecked(True) # Diaktifkan by default untuk stabilitas Skripsi
        self.chk_riemann.setToolTip("Mengubah tipe batas menjadi Weakly Reflective untuk mencegah resonansi ombak pantulan dari pesisir mangrove.")
        g1.addWidget(self.chk_riemann)
        
        self.lbl_mbbox = QLabel("BBOX: Belum Digambar")
        self.lbl_mtrans = QLabel("Transek: Belum Digambar")
        self.lbl_mbbox.setStyleSheet("color:#F59E0B; font-weight:bold;")
        self.lbl_mtrans.setStyleSheet("color:#F59E0B; font-weight:bold;")
        g1.addWidget(self.lbl_mbbox)
        g1.addWidget(self.lbl_mtrans)
        
        h1 = QHBoxLayout()
        btn_b = QPushButton("📂 Unggah Bathy (.xyz)")
        btn_b.setObjectName("OutlineBtn")
        btn_b.clicked.connect(lambda: self.load_mesh_file('bathy'))
        btn_shp = QPushButton("🗺️ Pesisir / Coastline (.shp)")
        btn_shp.setObjectName("OutlineBtn")
        btn_shp.clicked.connect(self.import_aoi_shapefile)
        h1.addWidget(btn_b)
        h1.addWidget(btn_shp)
        g1.addLayout(h1)
        
        c1.addWidget(grp1)
        c1.addStretch()
        ctrl.addLayout(c1, stretch=5)

        # Col 2: Resolution & Builder
        c2 = QVBoxLayout()
        grp2 = QGroupBox("2. Algoritma Fraktal MeshKernel & DIMR Compiler")
        g2 = QFormLayout(grp2)
        g2.setSpacing(14)
        
        self.sld_max = QSlider(Qt.Orientation.Horizontal)
        self.sld_max.setRange(50, 500)
        self.sld_max.setValue(100)
        self.inp_max = QLineEdit("100")
        self.inp_max.setFixedWidth(60)
        
        self.sld_max.valueChanged.connect(lambda v: self.inp_max.setText(str(v)))
        self.inp_max.textChanged.connect(lambda t: self.sld_max.setValue(int(t) if t.isdigit() else 100))
        
        hx = QHBoxLayout()
        hx.addWidget(self.sld_max)
        hx.addWidget(self.inp_max)
        g2.addRow("Res. Maksimum (Laut Lepas):", hx)
        
        self.sld_min = QSlider(Qt.Orientation.Horizontal)
        self.sld_min.setRange(5, 50)
        self.sld_min.setValue(12)
        self.inp_min = QLineEdit("12")
        self.inp_min.setFixedWidth(60)
        
        self.sld_min.valueChanged.connect(lambda v: self.inp_min.setText(str(v)))
        self.inp_min.textChanged.connect(lambda t: self.sld_min.setValue(int(t) if t.isdigit() else 12))
        
        hm = QHBoxLayout()
        hm.addWidget(self.sld_min)
        hm.addWidget(self.inp_min)
        g2.addRow("Res. Minimum (Mangrove):", hm)
        
        self.lbl_cost = QLabel("Estimasi Beban Node: Menghitung...")
        self.lbl_cost.setStyleSheet("background-color: #0F172A; padding: 8px; border: 1px solid #334155; border-radius: 6px; font-size: 12px; margin-bottom: 10px;")
        g2.addRow("", self.lbl_cost)

        btn_doc = QPushButton("🔭 Proses Kalkulasi DoC & 2D Profiler")
        btn_doc.setObjectName("OutlineBtn")
        btn_doc.clicked.connect(self.run_doc_calc)
        g2.addRow(btn_doc)
        
        self.btn_mesh = QPushButton("⚡ KOMPILASI MDU + SWAN + XML DIMR")
        self.btn_mesh.setObjectName("ExecuteBtn")
        self.btn_mesh.clicked.connect(self.run_dimr_pipeline)
        g2.addRow(self.btn_mesh)
        
        c2.addWidget(grp2)
        ctrl.addLayout(c2, stretch=5)
        scroll_layout.addLayout(ctrl)

        # --- 3. TERMINAL LOG ---
        bl = QVBoxLayout()
        bl.setContentsMargins(0, 10, 0, 0)
        bl.addWidget(QLabel("Terminal Log Eksekusi Arsitektur:", styleSheet="font-weight:900; color:#38BDF8; font-size: 14px;"))
        self.log_mesh = QTextEdit()
        self.log_mesh.setReadOnly(True)
        self.log_mesh.setStyleSheet("background-color: #020617; color: #10B981; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #1E293B; border-radius: 6px; padding: 8px;")
        self.log_mesh.setMinimumHeight(120)
        bl.addWidget(self.log_mesh)
        scroll_layout.addLayout(bl)
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        self.sld_max.valueChanged.connect(self.update_sliders)
        self.sld_min.valueChanged.connect(self.update_sliders)

    # --------------------------------------------------------------------------
    # DATA INGESTION & UI SYNCHRONIZATION
    # --------------------------------------------------------------------------

    def on_global_state_changed(self, key: str) -> None:
        """
        Logika cerdas: Otomatis memutar Arah Boundary berdasarkan Wave Rose (Dir) ERA5.
        """
        if key == 'Dir':
            dir_val = app_state.get('Dir', 180.0)
            
            # Mapping Konvensi MWD (Mean Wave Direction) ke Batas Geografis
            if 45 <= dir_val < 135:
                bnd = "East"
            elif 135 <= dir_val < 225:
                bnd = "South"
            elif 225 <= dir_val < 315:
                bnd = "West"
            else: # 315-360 dan 0-45
                bnd = "North"
                
            idx = self.cmb_bnd_dir.findData(bnd)
            if idx >= 0:
                self.cmb_bnd_dir.setCurrentIndex(idx)
                self.log_mesh.append(f"[AUTO-SYNC] Arah gelombang ERA5 ({dir_val:.1f}°) terdeteksi. Batas laut disetel ke: {bnd}.")

    def load_mesh_file(self, ftype: str) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Pilih File", "", "XYZ Data (*.xyz)" if ftype == 'bathy' else "Land Boundary (*.ldb)")
        if p:
            if ftype == 'bathy': 
                self.file_bathy = os.path.abspath(p)
                self.log_mesh.append(f"[SYSTEM] Batimetri aktif disetel ke: {os.path.basename(p)}")
            else: 
                self.file_ldb = os.path.abspath(p)
                self.log_mesh.append(f"[SYSTEM] Coastline LDB aktif disetel ke: {os.path.basename(p)}")

    def update_mesh_bbox(self, d: dict) -> None: 
        app_state.update('mesh_bbox', d)
        self.lbl_mbbox.setText("✓ BBox disinkronisasi dari Peta")
        self.lbl_mbbox.setStyleSheet("color:#10B981; font-weight:bold;")
        
        self.tbl_bbox.blockSignals(True)
        self.tbl_bbox.setItem(0, 0, QTableWidgetItem(f"{d['N']:.4f}"))
        self.tbl_bbox.setItem(1, 0, QTableWidgetItem(f"{d['S']:.4f}"))
        self.tbl_bbox.setItem(2, 0, QTableWidgetItem(f"{d['E']:.4f}"))
        self.tbl_bbox.setItem(3, 0, QTableWidgetItem(f"{d['W']:.4f}"))
        self.tbl_bbox.blockSignals(False)
        self.update_sliders()
        
    def manual_update_bbox_vertical(self) -> None:
        self.manual_map_update()

    def update_mesh_transect(self, d: list) -> None: 
        app_state.update('transect', d)
        self.lbl_mtrans.setText(f"✓ {len(d)} Titik Node Transek Sinkron")
        self.lbl_mtrans.setStyleSheet("color:#10B981; font-weight:bold;")
        
        self.tbl_man.setRowCount(len(d))
        for i, coord in enumerate(d):
            self.tbl_man.setItem(i, 0, QTableWidgetItem(f"{coord[0]:.4f}"))
            self.tbl_man.setItem(i, 1, QTableWidgetItem(f"{coord[1]:.4f}"))

    def import_aoi_shapefile(self) -> None:
        if not HAS_GEOPANDAS: 
            QMessageBox.critical(self, "Missing Library", "Pustaka 'geopandas' tidak terinstal. Jalankan: pip install geopandas shapely fiona")
            return
            
        p, _ = QFileDialog.getOpenFileName(self, "Pilih Coastline Polygon", "", "Vector Data (*.shp *.kml *.geojson)")
        if not p: return
        
        try:
            self.log_mesh.append("▶ Membaca geometri Vector Pesisir (Coastline)...")
            gdf = gpd.read_file(p)
            
            # Aman dari AttributeError jika gdf.crs None
            if gdf.crs is None or gdf.crs.to_epsg() != 4326: 
                gdf = gdf.to_crs(epsg=4326)
                
            ldb_path = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports', 'coastline_auto.ldb'))
            os.makedirs(os.path.dirname(ldb_path), exist_ok=True)
            
            with open(ldb_path, 'w', encoding='utf-8') as f:
                for i, row in gdf.iterrows():
                    g = row.geometry
                    if g.geom_type in ['LineString', 'Polygon', 'MultiPolygon']:
                        coords = list(g.exterior.coords) if g.geom_type == 'Polygon' else list(g.coords)
                        f.write(f"L{i}\n{len(coords)} 2\n")
                        for coord in coords: 
                            f.write(f"{coord[0]} {coord[1]}\n")
                            
            self.file_ldb = ldb_path
            js = f"addGeoJSON({gdf.to_json()}, '#EF4444');"
            self.web_mesh.page().runJavaScript(js)
            
            self.log_mesh.append(f"✅ Vektor dikonversi sukses menjadi {os.path.basename(ldb_path)} (Format Delft3D).")
            QMessageBox.information(self, "Konversi Sukses", "Shapefile berhasil dikonversi dan disuntikkan ke dalam Leaflet.")
            
        except Exception as e:
            logger.error(f"[SHP IMPORT] {str(e)}\n{traceback.format_exc()}")
            self.log_mesh.append(f"❌ Gagal memproses vektor geospasial: {str(e)}")

    def manual_map_update(self) -> None:
        try:
            # 1. BBox Check
            try:
                n = float(self.tbl_bbox.item(0,0).text())
                s = float(self.tbl_bbox.item(1,0).text())
                e = float(self.tbl_bbox.item(2,0).text())
                w = float(self.tbl_bbox.item(3,0).text())
                
                if n > s and e > w:
                    app_state.update('mesh_bbox', {'N': n, 'S': s, 'E': e, 'W': w})
                    js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{w},{s}],[{e},{s}],[{e},{n}],[{w},{n}],[{w},{s}]]]}}, '#38BDF8');"
                    self.web_mesh.page().runJavaScript(js_box)
            except Exception: pass
            
            # 2. Transect Check
            coords = []
            for i in range(self.tbl_man.rowCount()):
                try:
                    lat = float(self.tbl_man.item(i,0).text())
                    lon = float(self.tbl_man.item(i,1).text())
                    coords.append([lat, lon]) 
                except Exception: pass
                
            if len(coords) >= 2:
                app_state.update('transect', coords)
                js_line = f"addGeoJSON({{\"type\":\"LineString\",\"coordinates\":{json.dumps([[c[1], c[0]] for c in coords])}}}, '#10B981');"
                self.web_mesh.page().runJavaScript(js_line)
                
            self.log_mesh.append("[SYSTEM] Kanvas Web Map berhasil diperbarui dari Input Manual.")
        except Exception as e: 
            self.log_mesh.append(f"[WARNING] Gagal update map dari tabel manual: {str(e)}")

    def update_sliders(self) -> None:
        max_r = self.sld_max.value()
        min_r = self.sld_min.value()
        
        if min_r >= max_r: 
            self.lbl_cost.setText("⚠ ERROR: Resolusi Pesisir (Min) tidak boleh >= Resolusi Lepas Pantai (Max).")
            self.lbl_cost.setStyleSheet("color: #EF4444; font-weight:bold; font-size:12px; background-color:#450A0A;")
            return
            
        area_m2 = 25000000 
        aoi = app_state.get('mesh_bbox')
        
        if aoi: 
            # Aproksimasi area m2 dari derjat (1 deg ~ 111km)
            area_m2 = abs(aoi['E'] - aoi['W']) * 111320 * abs(aoi['N'] - aoi['S']) * 110540 
            
        est_nodes = area_m2 / (((max_r + min_r) / 2.0)**2)
        
        if est_nodes < 25000:
            status, color = "🟢 Ringan (PC/Laptop)", "#10B981"
            bg = "#064E3B"
        elif est_nodes < 60000:
            status, color = "🟡 Menengah (Workstation)", "#F59E0B"
            bg = "#451A03"
        else:
            status, color = "🔴 BERAT (Wajib HPC/Superkomputer)", "#EF4444"
            bg = "#450A0A"
            
        self.lbl_cost.setText(f"Luas Area: {area_m2/1e6:.1f} km² | Estimasi Komputasi: ~{int(est_nodes):,} Nodes | {status}")
        self.lbl_cost.setStyleSheet(f"color: {color}; font-weight:bold; font-size:12px; background-color:{bg}; padding: 8px; border-radius: 6px;")

    # --------------------------------------------------------------------------
    # THREAD EXECUTION & ORCHESTRATION
    # --------------------------------------------------------------------------

    def run_doc_calc(self) -> None:
        # Concurrency Guard
        if hasattr(self, 'doc_w') and self.doc_w.isRunning():
            QMessageBox.warning(self, "Terkunci", "Kalkulasi DoC sedang berjalan.")
            return

        if not self.file_bathy or not app_state.get('transect') or app_state.get('Hs', 0) == 0: 
            QMessageBox.critical(self, "Syarat Kurang", "Kalkulasi Depth of Closure (DoC) mensyaratkan: File Batimetri (.xyz), Garis Transek di Peta, dan Nilai Gelombang Hs (dari Modul ERA5) terisi.")
            return
            
        self.doc_w = DepthOfClosure2DWorker(
            self.file_bathy, 
            app_state.get('transect'), 
            app_state.get('He', 1.5), 
            app_state.get('EPSG', '32749')
        )
        
        self.doc_w.log_signal.connect(self.log_mesh.append)
        
        # Callback update DoC ke memori dan plot
        def on_doc_done(success: bool):
            if success:
                self.log_mesh.append("✅ Depth of Closure (DoC) terkunci di Global State.")
            self.doc_w.deleteLater()
            
        self.doc_w.doc_val_signal.connect(lambda v: app_state.update('DoC', v))
        self.doc_w.plot_signal.connect(self.on_doc_plot)
        self.doc_w.finished_signal.connect(on_doc_done)
        
        self.log_mesh.append("▶ Memulai Kalkulasi Matematika Fraktal DoC...")
        self.doc_w.start()

    def on_doc_plot(self, plot_path: str) -> None:
        if plot_path and os.path.exists(plot_path): 
            self.lbl_doc_plot.setPixmap(QPixmap(plot_path).scaled(self.lbl_doc_plot.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.gis_tabs_m.setCurrentIndex(2) # Pindah tab ke Panorama DoC otomatis

    def run_dimr_pipeline(self) -> None:
        # Concurrency Guard
        if hasattr(self, 'dimr_worker') and self.dimr_worker.isRunning():
            QMessageBox.warning(self, "Terkunci", "Kompilator sedang merakit topologi MDU. Harap tunggu.")
            return

        # Ambil state aman O(1) menggunakan fungsi get_all untuk snapshot
        state = app_state.get_all()
        
        p = {
            'he': state.get('He', 1.5), 
            'doc': state.get('DoC', 0), 
            'epsg': state.get('EPSG', '32749'), 
            'aoi_bounds': state.get('mesh_bbox'),
            'transect': state.get('transect'), 
            'bathy_file': self.file_bathy, 
            'ldb_file': self.file_ldb,
            'sediment_file': state.get('sediment_xyz', ""), 
            'tide_bc': state.get('tide_bc', ""),
            'max_res': self.sld_max.value(), 
            'min_res': self.sld_min.value(), 
            
            # [NEW INJECTION]: Physics boundary configurations for mesh_builder.py
            'ocean_boundary_dir': self.cmb_bnd_dir.currentData(), 
            'use_riemann': self.chk_riemann.isChecked(),
            
            'out_dir': os.path.abspath(os.path.join(os.getcwd(), 'Apex_FM_Model_Final'))
        }
        
        if not p['bathy_file'] or not p['aoi_bounds'] or not p['transect']:
            QMessageBox.critical(self, "Spesifikasi Inkomplit", "Untuk merakit arsitektur, Anda harus mendefinisikan Batimetri, Bounding Box (AOI), dan Garis Transek secara absolut.")
            return

        self.btn_mesh.setEnabled(False)
        self.btn_mesh.setText("⏳ MERAKIT DIMR COUPLER (MDU & SWAN)...")
        self.log_mesh.clear()
        
        self.dimr_worker = ApexDIMROrchestratorWorker(p, state)
        self.dimr_worker.log_signal.connect(self.log_mesh.append)
        self.dimr_worker.preview_signal.connect(self.show_mesh_preview)
        
        def on_mesh_done(status: str, success: bool):
            self.btn_mesh.setEnabled(True)
            self.btn_mesh.setText("⚡ KOMPILASI MDU + SWAN + XML DIMR")
            if success: 
                QMessageBox.information(self, "Kompilasi Sukses", "Pabrikasi MeshKernel dan XML Coupler telah selesai. Direktori 'Apex_FM_Model_Final' siap dieksekusi di Modul Simulation.")
            self.dimr_worker.deleteLater()
            
        self.dimr_worker.finished_signal.connect(on_mesh_done)
        self.dimr_worker.start()

    def show_mesh_preview(self, img_path: str) -> None:
        if img_path and os.path.exists(img_path):
            self.lbl_mesh_preview.setPixmap(QPixmap(img_path).scaled(self.lbl_mesh_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.gis_tabs_m.setCurrentIndex(1) # Pindah tab ke Topology Mesh otomatis
