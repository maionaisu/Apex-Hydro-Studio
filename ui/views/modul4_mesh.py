import os
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QLineEdit, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QMessageBox, QFrame, 
                             QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QSlider)
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

class Modul4Mesh(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_bathy = ""
        self.file_ldb = ""
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        head = QVBoxLayout()
        t = QLabel("DIMR Coupler Builder & DoC")
        t.setStyleSheet("font-size: 20pt; font-weight: 900; color: white;")
        d = QLabel("Merakit topologi mesh mangrove dan menulis XML Coupler untuk Flow (MDU) & Wave (MDW).")
        d.setStyleSheet("color: #94A3B8; font-size: 10pt;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        # 1. Top Section (Map / Tabs)
        self.gis_tabs_m = QTabWidget()
        self.gis_tabs_m.setMinimumHeight(350)
        
        tab_map = QWidget()
        lay_map = QVBoxLayout(tab_map)
        lay_map.setContentsMargins(0, 0, 0, 0)
        
        self.web_mesh = QWebEngineView()
        self.bridge_mesh = WebBridge()
        self.bridge_mesh.bbox_drawn.connect(self.update_mesh_bbox)
        self.bridge_mesh.transect_drawn.connect(self.update_mesh_transect)
        
        self.web_mesh.page().setWebChannel(QWebChannel(self.web_mesh.page()))
        self.web_mesh.page().webChannel().registerObject("bridge", self.bridge_mesh)
        self.web_mesh.setHtml(get_leaflet_html("mesh"))
        
        lay_map.addWidget(self.web_mesh)
        self.gis_tabs_m.addTab(tab_map, "Interactive Map")

        tab_mesh_viz = QWidget()
        lay_mz = QVBoxLayout(tab_mesh_viz)
        self.lbl_mesh_preview = QLabel("Topology UGRID Mesh Preview")
        self.lbl_mesh_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay_mz.addWidget(self.lbl_mesh_preview)
        self.gis_tabs_m.addTab(tab_mesh_viz, "Mesh Topology")

        tab_doc = QWidget()
        lay_doc = QVBoxLayout(tab_doc)
        self.lbl_doc_plot = QLabel("Plot DoC 2D Cross Section akan muncul di sini.")
        self.lbl_doc_plot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay_doc.addWidget(self.lbl_doc_plot)
        self.gis_tabs_m.addTab(tab_doc, "DoC 2D Cross Section")
        
        top_section = QHBoxLayout()
        top_section.addWidget(self.gis_tabs_m, stretch=7)
        
        self.tabs_aoi = QTabWidget()
        self.tabs_aoi.setObjectName("SegmentedTab")
        self.tabs_aoi.tabBar().setObjectName("SegmentedBar")
        
        # Tab 1: Manual BBox
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(10, 15, 10, 10)
        l1.addWidget(QLabel("Manual BBox (Lat/Lon):"))
        self.tbl_bbox = QTableWidget(4, 1)
        self.tbl_bbox.setVerticalHeaderLabels(["North", "South", "East", "West"])
        self.tbl_bbox.horizontalHeader().setVisible(False)
        self.tbl_bbox.setMaximumHeight(150)
        for j in range(4): self.tbl_bbox.setItem(j, 0, QTableWidgetItem(""))
        self.tbl_bbox.itemChanged.connect(self.manual_update_bbox_vertical)
        l1.addWidget(self.tbl_bbox)
        btn_m1 = QPushButton("Update BBox Area")
        btn_m1.clicked.connect(self.manual_map_update)
        l1.addWidget(btn_m1)
        l1.addStretch()
        self.tabs_aoi.addTab(t1, "Set BBox")
        
        # Tab 2: Manual Transect
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(10, 15, 10, 10)
        l2.addWidget(QLabel("Manual Transect Nodes:"))
        self.tbl_man = QTableWidget(2, 2)
        self.tbl_man.setHorizontalHeaderLabels(["Lat (Y)", "Lon (X)"])
        self.tbl_man.setMaximumHeight(80)
        self.tbl_man.setItem(0, 0, QTableWidgetItem("-8.460"))
        self.tbl_man.setItem(0, 1, QTableWidgetItem("112.616"))
        self.tbl_man.setItem(1, 0, QTableWidgetItem("-8.415"))
        self.tbl_man.setItem(1, 1, QTableWidgetItem("112.717"))
        l2.addWidget(self.tbl_man)
        btn_m2 = QPushButton("Update Line Profiles")
        btn_m2.clicked.connect(self.manual_map_update)
        l2.addWidget(btn_m2)
        l2.addStretch()
        self.tabs_aoi.addTab(t2, "Set Transect Series")
        
        top_section.addWidget(self.tabs_aoi, stretch=3)
        main_layout.addLayout(top_section, stretch=1)

        # 2. Bottom Section (Controls in ScrollArea)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 5, 0, 0)

        ctrl = QHBoxLayout()
        # Col 1: Geometry & coordinate
        c1 = QVBoxLayout()
        grp1 = QGroupBox("1. Geometry & Coordinate Editor")
        g1 = QVBoxLayout(grp1)
        
        self.lbl_mbbox = QLabel("BBOX: Belum Digambar")
        self.lbl_mtrans = QLabel("Transek: Belum Digambar")
        g1.addWidget(self.lbl_mbbox)
        g1.addWidget(self.lbl_mtrans)
        
        h1 = QHBoxLayout()
        btn_b = QPushButton("Bathy (.xyz)")
        btn_b.clicked.connect(lambda: self.load_mesh_file('bathy'))
        btn_shp = QPushButton("Coast (.shp/.kml)")
        btn_shp.clicked.connect(self.import_aoi_shapefile)
        h1.addWidget(btn_b)
        h1.addWidget(btn_shp)
        g1.addLayout(h1)
        
        c1.addWidget(grp1)
        c1.addStretch()
        ctrl.addLayout(c1)

        # Col 2: Resolution & Builder
        c2 = QVBoxLayout()
        grp2 = QGroupBox("2. Resolution & Compiler")
        g2 = QFormLayout(grp2)
        
        self.sld_max = QSlider(Qt.Orientation.Horizontal)
        self.sld_max.setRange(50, 500)
        self.sld_max.setValue(100)
        self.inp_max = QLineEdit("100")
        self.inp_max.setFixedWidth(50)
        
        self.sld_max.valueChanged.connect(lambda v: self.inp_max.setText(str(v)))
        self.inp_max.textChanged.connect(lambda t: self.sld_max.setValue(int(t) if t.isdigit() else 100))
        
        hx = QHBoxLayout()
        hx.addWidget(self.sld_max)
        hx.addWidget(self.inp_max)
        g2.addRow("Max (Offshore):", hx)
        
        self.sld_min = QSlider(Qt.Orientation.Horizontal)
        self.sld_min.setRange(5, 50)
        self.sld_min.setValue(12)
        self.inp_min = QLineEdit("12")
        self.inp_min.setFixedWidth(50)
        
        self.sld_min.valueChanged.connect(lambda v: self.inp_min.setText(str(v)))
        self.inp_min.textChanged.connect(lambda t: self.sld_min.setValue(int(t) if t.isdigit() else 12))
        
        hm = QHBoxLayout()
        hm.addWidget(self.sld_min)
        hm.addWidget(self.inp_min)
        g2.addRow("Min (Coast):", hm)
        
        self.lbl_cost = QLabel("Estimasi Beban: Menghitung...")
        self.lbl_cost.setStyleSheet("background-color: #020617; padding: 5px; border-radius: 4px; font-size: 11px;")
        g2.addRow("", self.lbl_cost)

        btn_doc = QPushButton("Plot 2D DoC Profiler")
        btn_doc.setObjectName("OutlineBtn")
        btn_doc.clicked.connect(self.run_doc_calc)
        g2.addRow(btn_doc)
        
        self.btn_mesh = QPushButton("COMPILE MDU + SWAN + DIMR")
        self.btn_mesh.setObjectName("ExecuteBtn")
        self.btn_mesh.clicked.connect(self.run_dimr_pipeline)
        g2.addRow(self.btn_mesh)
        
        c2.addWidget(grp2)
        ctrl.addLayout(c2)
        scroll_layout.addLayout(ctrl)

        # 3. Terminal Log
        bl = QVBoxLayout()
        bl.addWidget(QLabel("Terminal Process Log:", styleSheet="font-weight:bold; color:#F59E0B;"))
        self.log_mesh = QTextEdit()
        self.log_mesh.setReadOnly(True)
        self.log_mesh.setMinimumHeight(120)
        bl.addWidget(self.log_mesh)
        scroll_layout.addLayout(bl)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        self.sld_max.valueChanged.connect(self.update_sliders)
        self.sld_min.valueChanged.connect(self.update_sliders)


    def load_mesh_file(self, ftype):
        p, _ = QFileDialog.getOpenFileName(self, "Pilih File", "", "XYZ (*.xyz)" if ftype == 'bathy' else "LDB (*.ldb)")
        if p:
            if ftype == 'bathy': 
                self.file_bathy = p
                self.log_mesh.append(f"▶ Bathymetry {os.path.basename(p)} aktif.")
            else: 
                self.file_ldb = p
                self.log_mesh.append(f"▶ Coastline {os.path.basename(p)} aktif.")

    def update_mesh_bbox(self, d): 
        app_state.update('mesh_bbox', d)
        self.lbl_mbbox.setText("✓ Bbox Sinkron dari Peta")
        self.tbl_bbox.blockSignals(True)
        self.tbl_bbox.setItem(0, 0, QTableWidgetItem(f"{d['N']:.4f}"))
        self.tbl_bbox.setItem(1, 0, QTableWidgetItem(f"{d['S']:.4f}"))
        self.tbl_bbox.setItem(2, 0, QTableWidgetItem(f"{d['E']:.4f}"))
        self.tbl_bbox.setItem(3, 0, QTableWidgetItem(f"{d['W']:.4f}"))
        self.tbl_bbox.blockSignals(False)
        self.update_sliders()
        
    def manual_update_bbox_vertical(self):
        self.manual_map_update()

    def update_mesh_transect(self, d): 
        app_state.update('transect', d)
        self.lbl_mtrans.setText(f"✓ {len(d)} Node Transek Sinkron")
        self.tbl_man.setRowCount(len(d))
        for i, coord in enumerate(d):
            self.tbl_man.setItem(i, 0, QTableWidgetItem(f"{coord[0]:.4f}"))
            self.tbl_man.setItem(i, 1, QTableWidgetItem(f"{coord[1]:.4f}"))

    def import_aoi_shapefile(self):
        if not HAS_GEOPANDAS: 
            self.log_mesh.append("❌ Library geopandas tidak ditemukan.")
            return
            
        p, _ = QFileDialog.getOpenFileName(self, "Pilih Coastline .shp", "", "Vector (*.shp *.kml)")
        if p:
            try:
                gdf = gpd.read_file(p)
                if gdf.crs.to_epsg() != 4326: 
                    gdf = gdf.to_crs(epsg=4326)
                    
                ldb_path = os.path.join(os.getcwd(), 'Apex_Data_Exports', 'coastline_auto.ldb')
                os.makedirs(os.path.dirname(ldb_path), exist_ok=True)
                
                with open(ldb_path, 'w') as f:
                    for i, row in gdf.iterrows():
                        g = row.geometry
                        if g.geom_type in ['LineString', 'Polygon']:
                            c = list(g.exterior.coords) if g.geom_type == 'Polygon' else list(g.coords)
                            f.write(f"L{i}\n{len(c)} 2\n")
                            for coord in c: f.write(f"{coord[0]} {coord[1]}\n")
                            
                self.file_ldb = ldb_path
                js = f"addGeoJSON({gdf.to_json()}, '#EF4444');"
                self.web_mesh.page().runJavaScript(js)
                self.log_mesh.append("✅ Dikonversi menjadi Coastline LDB untuk Deltares.")
            except Exception as e:
                self.log_mesh.append(f"❌ Gagal memproses: {e}")

    def manual_map_update(self):
        try:
            try:
                n = float(self.tbl_bbox.item(0,0).text())
                s = float(self.tbl_bbox.item(1,0).text())
                e = float(self.tbl_bbox.item(2,0).text())
                w = float(self.tbl_bbox.item(3,0).text())
                
                app_state.update('mesh_bbox', {'N': n, 'S': s, 'E': e, 'W': w})
                js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{w},{s}],[{e},{s}],[{e},{n}],[{w},{n}],[{w},{s}]]]}}, '#38BDF8');"
                self.web_mesh.page().runJavaScript(js_box)
            except: 
                pass
            
            coords = []
            for i in range(self.tbl_man.rowCount()):
                lat = float(self.tbl_man.item(i,0).text())
                lon = float(self.tbl_man.item(i,1).text())
                coords.append([lat, lon]) 
                
            if len(coords) >= 2:
                app_state.update('transect', coords)
                js_line = f"addGeoJSON({{\"type\":\"LineString\",\"coordinates\":{json.dumps([[c[1], c[0]] for c in coords])}}}, '#10B981');"
                self.web_mesh.page().runJavaScript(js_line)
                self.log_mesh.append("✅ Peta diupdate dari Input Manual.")
        except Exception as e: 
            self.log_mesh.append(f"❌ Gagal update dari tabel: {e}")

    def update_sliders(self):
        max_r = self.sld_max.value()
        min_r = self.sld_min.value()
        
        if min_r >= max_r: 
            self.lbl_cost.setText("⚠ Error: Resolusi Min lebih besar dari Max.")
            return
            
        area_m2 = 25000000 
        aoi = app_state.get('mesh_bbox')
        
        if aoi: 
            area_m2 = abs(aoi['E'] - aoi['W']) * 111320 * abs(aoi['N'] - aoi['S']) * 110540 
            
        est_nodes = area_m2 / (((max_r + min_r) / 2.0)**2)
        
        if est_nodes < 20000:
            status, color = "Ringan", "#10B981"
        elif est_nodes < 50000:
            status, color = "Medium", "#F59E0B"
        else:
            status, color = "BERAT (Butuh HPC)", "#EF4444"
            
        self.lbl_cost.setText(f"Area: {area_m2/1e6:.1f} km² | Nodes: ~{int(est_nodes):,} | {status}")
        self.lbl_cost.setStyleSheet(f"color: {color}; font-weight:bold; font-size:11px;")

    def run_doc_calc(self):
        if not self.file_bathy or not app_state.get('transect') or app_state.get('Hs', 0) == 0: 
            QMessageBox.warning(self, "Data", "Bathy, Transek, dan Wave Hs wajib ada.")
            return
            
        self.doc_w = DepthOfClosure2DWorker(
            self.file_bathy, 
            app_state.get('transect'), 
            app_state.get('He', 1.5), 
            app_state.get('EPSG', '32749')
        )
        
        self.doc_w.log_signal.connect(self.log_mesh.append)
        self.doc_w.doc_val_signal.connect(lambda v: app_state.update('DoC', v))
        self.doc_w.plot_signal.connect(self.on_doc_plot)
        self.doc_w.start()

    def on_doc_plot(self, plot_path):
        if os.path.exists(plot_path): 
            self.lbl_doc_plot.setPixmap(QPixmap(plot_path).scaled(self.lbl_doc_plot.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.gis_tabs_m.setCurrentIndex(2)

    def run_dimr_pipeline(self):
        p = {
            'he': app_state.get('He', 1.5), 
            'doc': app_state.get('DoC', 0), 
            'epsg': app_state.get('EPSG', '32749'), 
            'aoi_bounds': app_state.get('mesh_bbox'),
            'transect': app_state.get('transect'), 
            'bathy_file': self.file_bathy, 
            'ldb_file': self.file_ldb,
            'sediment_file': app_state.get('sediment_xyz', ""), 
            'tide_bc': app_state.get('tide_bc', ""),
            'max_res': self.sld_max.value(), 
            'min_res': self.sld_min.value(), 
            'out_dir': os.path.join(os.getcwd(), 'Apex_FM_Model_Final')
        }
        
        if not p['bathy_file'] or not p['aoi_bounds'] or not p['transect']:
            QMessageBox.warning(self, "Error Data", "Pastikan Bounding Box, Transek, dan File Batimetri sudah terisi semua.")
            return

        self.btn_mesh.setEnabled(False)
        self.btn_mesh.setText("BUILDING DIMR COUPLER (MDU & SWAN)...")
        self.log_mesh.clear()
        
        self.dimr_worker = ApexDIMROrchestratorWorker(p, app_state.state)
        self.dimr_worker.log_signal.connect(self.log_mesh.append)
        self.dimr_worker.progress_signal.connect(lambda p: None) 
        self.dimr_worker.preview_signal.connect(self.show_mesh_preview)
        self.dimr_worker.finished_signal.connect(self.on_mesh_finished)
        self.dimr_worker.start()

    def show_mesh_preview(self, img_path):
        if os.path.exists(img_path):
            self.lbl_mesh_preview.setPixmap(QPixmap(img_path).scaled(self.lbl_mesh_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.gis_tabs_m.setCurrentIndex(1)

    def on_mesh_finished(self, status, success):
        self.btn_mesh.setEnabled(True)
        self.btn_mesh.setText("COMPILE MDU + SWAN + DIMR XML")
        if success: 
            QMessageBox.information(self, "Kompilasi Sukses", "Semua konfigurasi telah dibangun di folder 'Apex_FM_Model_Final'. Lanjut ke Modul Execution.")
