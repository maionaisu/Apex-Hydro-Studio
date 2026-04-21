import os
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QScrollArea, QSlider, QFrame,
                             QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget)
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

class Modul6PostProc(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.nc_file = ""
        self.current_max_time = 0
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        head = QVBoxLayout()
        t = QLabel("Post-Processing & Data Visualization")
        t.setStyleSheet("font-size: 20pt; font-weight: 900; color: white;")
        d = QLabel("Visualisasi Output NetCDF (*_map.nc) dari Deltares secara spasial menggunakan Leaflet Heatmaps")
        d.setStyleSheet("color: #94A3B8; font-size: 10pt;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        # 1. Top Section (Map and Custom AOI Input)
        top_section = QHBoxLayout()
        
        # LEFT: MAP
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: 1px solid #1E293B; border-radius: 8px; background: #000;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(0, 0, 0, 0)
        self.web_map = QWebEngineView()
        self.web_map.setMinimumHeight(400)
        self.web_map.setHtml(get_leaflet_html("postproc"))
        tl.addWidget(self.web_map)
        
        top_section.addWidget(top_wrap, stretch=7)
        
        # RIGHT: AOI Tabs
        self.tabs_aoi = QTabWidget()
        self.tabs_aoi.setObjectName("SegmentedTab")
        self.tabs_aoi.tabBar().setObjectName("SegmentedBar")

        # Tab 1: Shapefile
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(10, 15, 10, 10)
        lbl_msg = QLabel("📂 Upload batas Area\nGeospasial untuk mengekstrak\ndan menyorot data Heatmap.")
        lbl_msg.setStyleSheet("color: #94A3B8; font-style: italic; font-size: 10pt; line-height: 1.5;")
        btn_shp = QPushButton("Muat Vector (.shp/.kml)")
        btn_shp.setObjectName("OutlineBtn")
        btn_shp.clicked.connect(self.import_aoi_shapefile)
        l1.addWidget(lbl_msg)
        l1.addSpacing(10)
        l1.addWidget(btn_shp)
        l1.addStretch()
        self.tabs_aoi.addTab(t1, "SHP/KML Subset")

        # Tab 2: Manual
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(10, 15, 10, 10)
        lbl_aoi = QLabel("Manual BBox (Lat/Lon):")
        lbl_aoi.setStyleSheet("font-weight: bold; color: #F8FAFC;")
        l2.addWidget(lbl_aoi)
        
        self.tbl_bbox = QTableWidget(4, 1)
        self.tbl_bbox.setVerticalHeaderLabels(["North", "South", "East", "West"])
        self.tbl_bbox.horizontalHeader().setVisible(False)
        self.tbl_bbox.setMaximumHeight(150)
        for j in range(4): self.tbl_bbox.setItem(j, 0, QTableWidgetItem(""))
        self.tbl_bbox.itemChanged.connect(self.manual_update_bbox_vertical)
        l2.addWidget(self.tbl_bbox)
        l2.addStretch()
        self.tabs_aoi.addTab(t2, "Manual Params")
        
        top_section.addWidget(self.tabs_aoi, stretch=3)
        main_layout.addLayout(top_section, stretch=1)

        # 2. Bottom Section (Controls in ScrollArea)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 10, 0, 0)

        ctrl = QHBoxLayout()
        
        # Col 1: File & Variable
        c1 = QVBoxLayout()
        grp1 = QGroupBox("1. Dataset & Variabel Fisik")
        g1 = QFormLayout(grp1)
        
        self.btn_nc = QPushButton("Muat Data Map NC (.nc)")
        self.btn_nc.setObjectName("OutlineBtn")
        self.btn_nc.clicked.connect(self.load_nc_file)
        g1.addRow(self.btn_nc)
        
        self.cmb_var = QComboBox()
        self.cmb_var.addItems(['mesh2d_s1', 'mesh2d_ucx', 'mesh2d_ucy', 'mesh2d_taus', 'Hsig', 'Tp'])
        g1.addRow("Pilih Variabel:", self.cmb_var)
        
        self.btn_ren = QPushButton("Render Frame Awal")
        self.btn_ren.setObjectName("ExecuteBtn")
        self.btn_ren.clicked.connect(lambda: self.trigger_render(0))
        g1.addRow(self.btn_ren)
        
        c1.addWidget(grp1)
        ctrl.addLayout(c1)

        # Col 2: Time Control
        c2 = QVBoxLayout()
        grp2 = QGroupBox("2. Time Series Scrubber")
        g2 = QVBoxLayout(grp2)
        
        h_info = QHBoxLayout()
        self.lbl_t_idx = QLabel("Time Index: 0")
        self.lbl_t_str = QLabel("Timestamp: -")
        self.lbl_val_range = QLabel("Range V: -")
        self.lbl_t_idx.setStyleSheet("color:#38BDF8; font-weight:bold;")
        self.lbl_t_str.setStyleSheet("color:#10B981; font-weight:bold;")
        self.lbl_val_range.setStyleSheet("color:#F59E0B; font-weight:bold;")
        h_info.addWidget(self.lbl_t_idx)
        h_info.addWidget(self.lbl_t_str)
        h_info.addWidget(self.lbl_val_range)
        g2.addLayout(h_info)
        
        self.sld_time = QSlider(Qt.Orientation.Horizontal)
        self.sld_time.setRange(0, 0)
        self.sld_time.setValue(0)
        self.sld_time.valueChanged.connect(self.on_slider_moved)
        self.sld_time.sliderReleased.connect(self.on_slider_released)
        g2.addWidget(self.sld_time)
        
        c2.addWidget(grp2)
        ctrl.addLayout(c2)
        scroll_layout.addLayout(ctrl)

        # 3. Bottom: Log
        bl = QVBoxLayout()
        bl.addWidget(QLabel("Render Output Status:", styleSheet="font-weight:bold; color:#F59E0B;"))
        self.log_viz = QTextEdit()
        self.log_viz.setReadOnly(True)
        self.log_viz.setMaximumHeight(80)
        bl.addWidget(self.log_viz)
        
        scroll_layout.addLayout(bl)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

    def import_aoi_shapefile(self):
        if not HAS_GEOPANDAS: 
            self.log_viz.append("❌ Library geopandas tidak ditemukan.")
            return
            
        p, _ = QFileDialog.getOpenFileName(self, "Pilih Coastline .shp/.kml", "", "Vector (*.shp *.kml)")
        if p:
            try:
                gdf = gpd.read_file(p)
                if gdf.crs.to_epsg() != 4326: gdf = gdf.to_crs(epsg=4326)
                js = f"addGeoJSON({gdf.to_json()}, '#EF4444');"
                self.web_map.page().runJavaScript(js)
                self.log_viz.append(f"✅ Vector SHP/KML dimuat dan digambar di atas Peta.")
                # Auto set bounds table based on total bounds
                bounds = gdf.total_bounds # [minx, miny, maxx, maxy]
                self.tbl_bbox.setItem(0, 0, QTableWidgetItem(f"{bounds[3]:.4f}")) # N
                self.tbl_bbox.setItem(1, 0, QTableWidgetItem(f"{bounds[1]:.4f}")) # S
                self.tbl_bbox.setItem(2, 0, QTableWidgetItem(f"{bounds[2]:.4f}")) # E
                self.tbl_bbox.setItem(3, 0, QTableWidgetItem(f"{bounds[0]:.4f}")) # W
            except Exception as e:
                self.log_viz.append(f"❌ Gagal memproses Shapefile: {e}")

    def manual_update_bbox_vertical(self):
        try:
            n = float(self.tbl_bbox.item(0,0).text())
            s = float(self.tbl_bbox.item(1,0).text())
            e = float(self.tbl_bbox.item(2,0).text())
            w = float(self.tbl_bbox.item(3,0).text())
            
            js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{w},{s}],[{e},{s}],[{e},{n}],[{w},{n}],[{w},{s}]]]}}, '#38BDF8');"
            self.web_map.page().runJavaScript(js_box)
            self.log_viz.append("✅ Manual Bounding Box digambar ulang.")
        except Exception:
            pass

    def load_nc_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Pilih File .map.nc Output", "", "NetCDF (*.nc)")
        if p: 
            self.nc_file = p
            self.log_viz.append(f"▶ File output siap dirender: {os.path.basename(p)}")

    def on_slider_moved(self, val):
        self.lbl_t_idx.setText(f"Time Index: {val} / {self.current_max_time}")

    def on_slider_released(self):
        self.trigger_render(self.sld_time.value())

    def trigger_render(self, time_idx):
        if not self.nc_file:
            QMessageBox.warning(self, "Error", "Muat file .nc terlebih dahulu.")
            return
            
        epsg = app_state.get('EPSG', '32749')
        out_dir = os.path.join(os.getcwd(), 'Apex_Data_Exports')
        os.makedirs(out_dir, exist_ok=True)
        
        target_var = self.cmb_var.currentText()
        
        self.worker = PostProcAnimationWorker(self.nc_file, target_var, time_idx, epsg, out_dir)
        self.worker.log_signal.connect(self.log_viz.append)
        self.worker.frame_signal.connect(self.apply_overlay)
        
        def on_finished():
            self.sld_time.setEnabled(True)
            self.btn_ren.setEnabled(True)
            self.btn_ren.setText("Render Frame Awal")
            self.worker.deleteLater()
            
        self.worker.finished_signal.connect(on_finished)
        
        self.btn_ren.setEnabled(False)
        self.sld_time.setEnabled(False)
        self.btn_ren.setText("⏳ Rendering...")
        self.worker.start()

    def apply_overlay(self, data):
        self.current_max_time = data['max_time']
        self.sld_time.setRange(0, self.current_max_time)
        self.lbl_t_str.setText(f"Timestamp: {data['time_str']}")
        
        v_min, v_max = data['v_min'], data['v_max']
        self.lbl_val_range.setText(f"Range: {v_min:.3f} s/d {v_max:.3f}")
        
        b = data['bounds']
        base64_img = data['base64_img']
        bounds_json = json.dumps([[b['S'], b['W']], [b['N'], b['E']]])
        
        js_code = f"""
        if (window.currentOverlay) {{ map.removeLayer(window.currentOverlay); }}
        var bounds = {bounds_json};
        window.currentOverlay = L.imageOverlay('{base64_img}', bounds, {{opacity: 0.85}});
        window.currentOverlay.addTo(map);
        map.fitBounds(bounds);
        """
        self.web_map.page().runJavaScript(js_code)
