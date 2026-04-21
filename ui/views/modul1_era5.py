import os
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QLineEdit, QLabel, QPushButton, 
                             QDateTimeEdit, QTextEdit, QFileDialog, QMessageBox, QFrame, 
                             QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget, QListWidget, QAbstractItemView, QListWidgetItem)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt, QDateTime, QSettings

from ui.components.web_bridge import WebBridge
from utils.config import get_leaflet_html
from workers.era5_worker import ERA5DownloaderWorker
from engines.era5_extractor import ERA5Extractor, HAS_XARRAY
from core.state_manager import app_state

class Modul1ERA5(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('ApexStudio', 'HydroSettings')
        self._syncing = False
        self.setup_ui()  # bridge is set up inline inside setup_ui

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header
        head = QVBoxLayout()
        t = QLabel("Metocean Synthesizer (ERA5)")
        t.setStyleSheet("font-size: 20pt; font-weight: 900; color: white;")
        d = QLabel("Tarik parameter angin dan gelombang menggunakan kotak Interaktif dari peta di atas.")
        d.setStyleSheet("color: #94A3B8; font-size: 10pt;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)
        
        # 1. Top Section (Map and AOI manual input)
        top_section = QHBoxLayout()
        
        # LEFT: MAP
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: 1px solid #1E293B; border-radius: 8px; background: #000;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(0, 0, 0, 0)
        
        self.web_map_era5 = QWebEngineView()
        self.web_map_era5.setMinimumHeight(400)
        self.bridge_era5 = WebBridge()
        self.bridge_era5.bbox_drawn.connect(self.update_era5_bbox)
        self.web_map_era5.page().setWebChannel(QWebChannel(self.web_map_era5.page()))
        self.web_map_era5.page().webChannel().registerObject("bridge", self.bridge_era5)
        self.web_map_era5.setHtml(get_leaflet_html("era5"))
        tl.addWidget(self.web_map_era5)
        
        top_section.addWidget(top_wrap, stretch=7)
        
        # RIGHT: AOI Tabs
        self.tabs_aoi = QTabWidget()
        self.tabs_aoi.setObjectName("SegmentedTab")
        self.tabs_aoi.tabBar().setObjectName("SegmentedBar")
        
        # Tab 1: Interactive
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(10, 15, 10, 10)
        lbl_msg = QLabel("✏️ Gunakan toolbar\ndi Peta untuk menggambar area\nbatas ekstraksi ERA5.")
        lbl_msg.setStyleSheet("color: #94A3B8; font-style: italic; font-size: 10pt; line-height: 1.5;")
        l1.addWidget(lbl_msg)
        l1.addStretch()
        self.tabs_aoi.addTab(t1, "Interactive Mode")
        
        # Tab 2: Manual Coordinates
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(10, 15, 10, 10)
        lbl_aoi = QLabel("Input (Lat/Lon):")
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
        
        # Col 1
        c1 = QVBoxLayout()
        grp0 = QGroupBox("1. CDS API & Area")
        g0 = QVBoxLayout(grp0)
        self.inp_api = QLineEdit()
        self.inp_api.setPlaceholderText("UID:API_KEY")
        self.inp_api.setToolTip("Contoh: 123456:a1b2c3d4-e5f6-g7h8-i9j0")
        
        # Auto-load cached API Key 
        cached_api = self.settings.value('cds_api', '')
        if cached_api:
            self.inp_api.setText(cached_api)
            
        g0.addWidget(self.inp_api)
        
        self.lbl_era_bbox = QLabel("AOI Belum disinkronisasi (Draw Box di Peta)")
        self.lbl_era_bbox.setStyleSheet("color:#F59E0B; font-weight:bold; font-size:9pt;")
        g0.addWidget(self.lbl_era_bbox)
        
        lbl_info = QLabel("Untuk menggambar Bounding Box, gunakan tombol persegi (Draw Rectangle) di toolbar Leaflet Map kiri. Koordinat akan dikirim secara seketika via QtWebChannel.")
        lbl_info.setStyleSheet("color: #64748B; font-size: 8pt;")
        lbl_info.setWordWrap(True)
        g0.addWidget(lbl_info)
        
        c1.addWidget(grp0)
        
        grp1 = QGroupBox("2. Parameter & Temporal Scope")
        g1 = QFormLayout(grp1)
        
        # ERA5 Variable Selection — Comprehensive Catalog (Ctrl+Click for multi-select)
        self.var_list = QListWidget()
        self.var_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.var_list.setMinimumHeight(220)
        self.var_list.setToolTip("Ctrl+Click untuk pilih lebih dari satu variabel")

        # Catalog grouped by oceanographic/metocean domain
        ERA5_CATALOG = [
            # ── OCEAN WAVES ─────────────────────────────────────────────────────────────
            ("═══ OCEAN WAVES ═══", None),
            ("Significant Height of Combined Wind Waves (Hs)",  "significant_height_of_combined_wind_waves"),
            ("Mean Wave Period (Tm01)",                         "mean_wave_period"),
            ("Mean Wave Direction (Dir)",                       "mean_wave_direction"),
            ("Peak Wave Period (Tp)",                           "peak_wave_period"),
            ("Mean Period of Total Swell (Swell Tp)",           "mean_period_of_total_swell"),
            ("Significant Height of Wind Waves",                "significant_height_of_wind_waves"),
            ("Significant Height of Total Swell",               "significant_height_of_total_swell"),
            ("Mean Direction of Wind Waves",                    "mean_direction_of_wind_waves"),
            ("Mean Direction of Total Swell",                   "mean_direction_of_total_swell"),
            ("Coefficient of Drag with Waves",                  "coefficient_of_drag_with_waves"),
            ("Ocean Surface Stokes Drift U",                    "u_component_stokes_drift"),
            ("Ocean Surface Stokes Drift V",                    "v_component_stokes_drift"),
            # ── WIND ────────────────────────────────────────────────────────────────────
            ("═══ WIND ═══", None),
            ("10m U-component of Wind",                         "10m_u_component_of_wind"),
            ("10m V-component of Wind",                         "10m_v_component_of_wind"),
            ("10m Wind Speed",                                  "wind_speed"),
            ("100m U-component of Wind",                       "100m_u_component_of_wind"),
            ("100m V-component of Wind",                       "100m_v_component_of_wind"),
            ("Instantaneous 10m Wind Gust",                     "instantaneous_10m_wind_gust"),
            ("Wind Stress U (Surface)",                         "surface_eastward_turbulent_surface_stress"),
            ("Wind Stress V (Surface)",                         "surface_northward_turbulent_surface_stress"),
            # ── OCEAN & SEA SURFACE ──────────────────────────────────────────────────────
            ("═══ SEA SURFACE ═══", None),
            ("Sea Surface Temperature (SST)",                   "sea_surface_temperature"),
            ("Mean Sea Level Pressure (MSLP)",                  "mean_sea_level_pressure"),
            ("Sea Surface Salinity",                            "sea_surface_salinity"),
            # ── PRECIPITATION & RADIATION ────────────────────────────────────────────────
            ("═══ ATMOSPHERE ═══", None),
            ("Total Precipitation",                             "total_precipitation"),
            ("Convective Precipitation",                        "convective_precipitation"),
            ("2m Temperature",                                  "2m_temperature"),
            ("2m Dewpoint Temperature",                         "2m_dewpoint_temperature"),
            ("Surface Net Solar Radiation",                     "surface_net_solar_radiation"),
            ("Surface Net Thermal Radiation",                   "surface_net_thermal_radiation"),
            ("Boundary Layer Height",                           "boundary_layer_height"),
            ("Geopotential at 500hPa",                          "geopotential"),
        ]

        default_selected = {
            "significant_height_of_combined_wind_waves",
            "mean_wave_period",
            "mean_wave_direction",
        }

        for v_disp, v_id in ERA5_CATALOG:
            item = QListWidgetItem(v_disp)
            if v_id is None:
                # Section header — non-selectable, styled grey
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setForeground(Qt.GlobalColor.darkGray)
            else:
                item.setData(Qt.ItemDataRole.UserRole, v_id)
                if v_id in default_selected:
                    item.setSelected(True)
            self.var_list.addItem(item)

        g1.addRow("Opsi Variabel (Ctrl+Klik):", self.var_list)
        
        # Copernicus CDS has 5 days release lag 
        safe_end_dt = QDateTime.currentDateTime().addDays(-5)
        
        self.dt_start = QDateTimeEdit(safe_end_dt.addYears(-1))
        self.dt_start.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_start.setCalendarPopup(True)
        
        self.dt_end = QDateTimeEdit(safe_end_dt)
        self.dt_end.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_end.setCalendarPopup(True)
        
        g1.addRow("Start:", self.dt_start)
        g1.addRow("End:", self.dt_end)
        self.btn_dl_era5 = QPushButton("↓ Download ERA5 (.nc)")
        self.btn_dl_era5.clicked.connect(self.run_era5_downloader)
        g1.addRow(self.btn_dl_era5)
        c1.addWidget(grp1)
        ctrl.addLayout(c1)
        
        # Col 2
        c2 = QVBoxLayout()
        grp2 = QGroupBox("3. Extract & Manual Inject")
        g2 = QFormLayout(grp2)
        
        btn_load = QPushButton("Pilih File .nc Lokal")
        btn_load.setObjectName("OutlineBtn")
        btn_load.clicked.connect(self.load_era5_file)
        g2.addRow(btn_load)
        
        btn_nc = QPushButton("Extract File .nc")
        btn_nc.setObjectName("OutlineBtn")
        btn_nc.clicked.connect(self.execute_era5_local)
        g2.addRow(btn_nc)
        
        self.inp_man_hs = QLineEdit()
        self.inp_man_tp = QLineEdit()
        self.inp_man_dir = QLineEdit()
        self.inp_man_hs.setPlaceholderText("Hs (m)")
        self.inp_man_tp.setPlaceholderText("Tp (s)")
        self.inp_man_dir.setPlaceholderText("Dir (°)")
        
        h_man = QHBoxLayout()
        h_man.addWidget(self.inp_man_hs)
        h_man.addWidget(self.inp_man_tp)
        h_man.addWidget(self.inp_man_dir)
        g2.addRow("Manual:", h_man)
        
        btn_inj = QPushButton("Inject Wave Parameters")
        btn_inj.clicked.connect(self.manual_override_wave)
        g2.addRow(btn_inj)
        
        c2.addWidget(grp2)
        c2.addStretch()
        ctrl.addLayout(c2)
        
        scroll_layout.addLayout(ctrl)
        
        bl = QVBoxLayout()
        bl.addWidget(QLabel("Terminal Process Log:", styleSheet="font-weight:bold; color:#F59E0B;"))
        self.log_era5 = QTextEdit()
        self.log_era5.setReadOnly(True)
        self.log_era5.setMinimumHeight(120)
        self.log_era5.setMaximumHeight(200)
        bl.addWidget(self.log_era5)
        scroll_layout.addLayout(bl)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)
        
    def update_era5_bbox(self, data):
        self._syncing = True
        app_state.update('mesh_bbox', data)
        self.lbl_era_bbox.setText(f"✓ N{data['N']:.2f}, S{data['S']:.2f}, E{data['E']:.2f}, W{data['W']:.2f}")
        self.lbl_era_bbox.setStyleSheet("color: #10B981; font-weight: bold;")
        
        self.tbl_bbox.setItem(0, 0, QTableWidgetItem(f"{data['N']:.4f}"))
        self.tbl_bbox.setItem(1, 0, QTableWidgetItem(f"{data['S']:.4f}"))
        self.tbl_bbox.setItem(2, 0, QTableWidgetItem(f"{data['E']:.4f}"))
        self.tbl_bbox.setItem(3, 0, QTableWidgetItem(f"{data['W']:.4f}"))
        
        self.log_era5.append("▶ Bounding Box otomatis disinkronisasi dari MapNative Bridge.")
        self._syncing = False

    def manual_update_bbox_vertical(self):
        if self._syncing: return
        try:
            n = float(self.tbl_bbox.item(0,0).text())
            s = float(self.tbl_bbox.item(1,0).text())
            e = float(self.tbl_bbox.item(2,0).text())
            w = float(self.tbl_bbox.item(3,0).text())
            
            data = {'N': n, 'S': s, 'E': e, 'W': w}
            app_state.update('mesh_bbox', data)
            self.lbl_era_bbox.setText(f"✓ Manual BBox disinkronisasi")
            self.lbl_era_bbox.setStyleSheet("color: #10B981; font-weight: bold;")
            
            js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{w},{s}],[{e},{s}],[{e},{n}],[{w},{n}],[{w},{s}]]]}}, '#F59E0B');"
            self.web_map_era5.page().runJavaScript("clearMap(); " + js_box)
            self.log_era5.append("▶ Tabel Manual AOI berhasil dikirim ke Leaflet Map.")
        except Exception:
            pass

    def load_era5_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih File ERA5", "", "NetCDF (*.nc)")
        if path:
            self.era5_path = path
            self.log_era5.append(f"▶ File aktif: {os.path.basename(path)}")

    def run_era5_downloader(self):
        api_key = self.inp_api.text()
        bbox = app_state.get('mesh_bbox')
        if not api_key or not bbox: 
            QMessageBox.warning(self, "Error", "Lengkapi API Key dan Bbox.")
            return
            
        self.settings.setValue('cds_api', api_key) # Save API Key
        
        selected_items = self.var_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Error", "Pilih minimal 1 Variabel ERA5!")
            return
            
        params = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        out_file = os.path.join(os.getcwd(), "Apex_Data_Exports", "ERA5_WAVE.nc")
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        
        self.btn_dl_era5.setEnabled(False)
        self.btn_dl_era5.setText("⏳ Downloading ERA5 via CDS API...")
        self.era_w = ERA5DownloaderWorker(api_key, bbox, params, self.dt_start.dateTime(), self.dt_end.dateTime(), out_file)
        self.era_w.log_signal.connect(self.log_era5.append)
        
        def on_finished(success, path):
            self.btn_dl_era5.setEnabled(True)
            self.btn_dl_era5.setText("↓ Download ERA5 (.nc)")
            self.era_w.deleteLater() # Garbage Collection 
            
        self.era_w.finished_signal.connect(on_finished)
        self.era_w.start()

    def execute_era5_local(self):
        if not hasattr(self, 'era5_path'): 
            QMessageBox.warning(self, "Error", "Pilih file .nc dulu.")
            return
            
        if not HAS_XARRAY: 
            self.log_era5.append("❌ Library xarray tidak ditemukan.")
            return
            
        try:
            hs, tp, dir_, doc = ERA5Extractor.extract_wave_params(self.era5_path)
            app_state.update_multiple({'He': hs, 'Hs': hs, 'Tp': tp, 'Dir': dir_, 'DoC': doc})
            self.log_era5.append(f"✅ Ekstrak sukses. Hs={hs:.2f}m, Tp={tp:.1f}s, Dir={dir_:.1f}°, DoC={doc:.2f}m")
        except Exception as e:
            self.log_era5.append(f"❌ Error ekstraksi: {e}")

    def manual_override_wave(self):
        try:
            hs = float(self.inp_man_hs.text() or 1.5)
            tp = float(self.inp_man_tp.text() or 8.0)
            dir_ = float(self.inp_man_dir.text() or 180.0)
            doc = 1.57 * hs
            
            app_state.update_multiple({'He': hs, 'Hs': hs, 'Tp': tp, 'Dir': dir_, 'DoC': doc})
            self.log_era5.append(f"✅ Parameter Wave di-inject secara manual. Hs={hs}m, Tp={tp}s, Dir={dir_}°, DoC={doc}m")
        except Exception as e:
            self.log_era5.append(f"❌ Input tidak valid: {e}")
