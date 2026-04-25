# ==============================================================================
# APEX NEXUS TIER-0: MODUL 1 - ERA5 SYNTHESIZER (UI VIEW)
# ==============================================================================
import os
import logging
import traceback
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QLineEdit, QLabel, QPushButton, 
                             QDateTimeEdit, QTextEdit, QFileDialog, QMessageBox, QFrame, 
                             QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget, 
                             QListWidget, QAbstractItemView, QListWidgetItem, QHeaderView, QSplitter)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt, QDateTime, QSettings
from PyQt6.QtGui import QColor, QCursor

from ui.components.web_bridge import WebBridge
from utils.config import get_leaflet_html
from workers.era5_worker import ERA5DownloaderWorker
from engines.era5_extractor import ERA5Extractor, HAS_XARRAY
from core.state_manager import app_state

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS (FINTECH SLATE ADAPTATION) ---
STYLE_GROUPBOX = """
    QGroupBox { background-color: #2D3139; border: 1px solid #3A3F4A; border-radius: 12px; margin-top: 15px; padding-top: 35px; font-weight: 800; color: #FFFFFF; font-size: 14px; }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 6px 16px; background-color: transparent; color: #8FC9DC; top: 8px; left: 10px; }
"""
STYLE_INPUTS = """
    QLineEdit, QDateTimeEdit { background-color: #1F2227; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 14px; color: #FFFFFF; font-size: 13px; font-family: 'Consolas', monospace; }
    QLineEdit:focus, QDateTimeEdit:focus { border: 1px solid #595FF7; background-color: #2D3139; }
    QDateTimeEdit::drop-down { border: none; width: 24px; }
"""
STYLE_TABLE_LIST = """
    QListWidget, QTableWidget { background-color: #1F2227; color: #FFFFFF; gridline-color: #3A3F4A; border: 1px solid #3A3F4A; border-radius: 8px; font-family: 'Consolas', monospace; }
    QListWidget::item { padding: 8px 12px; border-radius: 6px; margin-bottom: 2px; }
    QListWidget::item:hover:!selected { background-color: #2D3139; }
    QListWidget::item:selected { background-color: #595FF7; color: #FFFFFF; }
    QHeaderView::section { background-color: #2D3139; color: #8FC9DC; padding: 8px; font-weight: 800; border: none; border-bottom: 1px solid #3A3F4A; border-right: 1px solid #3A3F4A; }
    QTableWidget::item:selected { background-color: #595FF7; color: #FFFFFF; }
"""
STYLE_BTNS = """
    QPushButton#PrimaryBtn { background-color: #595FF7; color: #FFFFFF; border: none; border-radius: 10px; padding: 14px 16px; font-weight: 900; font-size: 14px; }
    QPushButton#PrimaryBtn:hover { background-color: #7176F8; }
    QPushButton#PrimaryBtn:disabled { background-color: #3A3F4A; color: #6B7280; }
    QPushButton#OutlineBtn { background-color: transparent; color: #8FC9DC; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 16px; font-weight: 800; font-size: 13px; }
    QPushButton#OutlineBtn:hover { background-color: rgba(143, 201, 220, 0.1); border-color: #8FC9DC; }
    QPushButton#DangerBtn { background-color: transparent; color: #FC3F4D; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 16px; font-weight: 800; font-size: 13px; }
    QPushButton#DangerBtn:hover { background-color: rgba(252, 63, 77, 0.1); border-color: #FC3F4D; }
"""
STYLE_TABS = """
    QTabWidget::pane { border: 1px solid #3A3F4A; border-radius: 12px; background: #1E2128; }
    QTabBar::tab { background: #1F2227; color: #9CA3AF; padding: 12px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; font-weight: 800; }
    QTabBar::tab:selected { background: #2D3139; color: #8FC9DC; border-bottom: 3px solid #8FC9DC; }
"""

LABEL_STYLE = "QLabel { color: #9CA3AF; font-weight: bold; font-size: 13px; }"


class Modul1ERA5(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('ApexStudio', 'HydroSettings')
        self._syncing = False
        self.era5_path = "" 
        
        # Sinkronisasi Global State
        app_state.state_updated.connect(self.on_global_state_changed)
        app_state.bulk_state_updated.connect(self.on_bulk_state_changed)
        
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_TABLE_LIST} {STYLE_BTNS} {STYLE_TABS}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)
        
        # --- HEADER (FINTECH STYLE) ---
        head = QVBoxLayout()
        t = QLabel("Metocean Synthesizer (ERA5)")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Unduh Data Copernicus CDS, Ekstrak Kondisi Awal (Initial Condition), dan Generasi Macro-AOI Otomatis.")
        d.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")
        
        # ==============================================================================
        # 1. TOP SECTION (MAP & AOI TABS)
        # ==============================================================================
        top_widget = QWidget()
        top_section = QHBoxLayout(top_widget)
        top_section.setContentsMargins(0, 0, 0, 0)
        top_section.setSpacing(20)
        
        # KIRI: Peta Leaflet WebEngine
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: 1px solid #3A3F4A; border-radius: 12px; background: #000; overflow: hidden;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(1, 1, 1, 1)
        
        self.web_map_era5 = QWebEngineView()
        self.web_map_era5.setMinimumHeight(400)
        
        self.bridge_era5 = WebBridge()
        self.bridge_era5.bbox_drawn.connect(self.update_era5_bbox)
        
        self.web_map_era5.page().setWebChannel(QWebChannel(self.web_map_era5.page()))
        self.web_map_era5.page().webChannel().registerObject("bridge", self.bridge_era5)
        self.web_map_era5.setHtml(get_leaflet_html("era5"))
        tl.addWidget(self.web_map_era5)
        
        top_section.addWidget(top_wrap, stretch=7)
        
        # KANAN: Panel Tab Input AOI (Batas Download)
        self.tabs_aoi = QTabWidget()
        
        # Tab 1: Interactive Map
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(20, 24, 20, 20)
        lbl_msg = QLabel("💡 Gunakan fitur Draw Rectangle pada toolbar peta untuk menentukan area unduhan ERA5 (Bukan Area Detail).")
        lbl_msg.setStyleSheet("color: #9CA3AF; font-size: 13px; line-height: 1.6;")
        lbl_msg.setWordWrap(True)
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l1.addWidget(lbl_msg)
        
        self.lbl_req_bbox = QLabel("Batas Request (BBox): Belum Digambar")
        self.lbl_req_bbox.setStyleSheet("color:#FC3F4D; font-weight:bold; font-size:12px; background-color: #1F2227; padding: 10px; border-radius: 6px; border: 1px solid #3A3F4A; margin-top: 15px;")
        self.lbl_req_bbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l1.addWidget(self.lbl_req_bbox)
        l1.addStretch()
        self.tabs_aoi.addTab(t1, "🗺️ Mode Peta Interaktif")
        
        # Tab 2: Manual Extent
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(20, 20, 20, 20)
        lbl_aoi = QLabel("Request Bounds (Lat/Lon):"); lbl_aoi.setStyleSheet(LABEL_STYLE)
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
        self.tabs_aoi.addTab(t2, "⌨️ Input Manual")
        
        top_section.addWidget(self.tabs_aoi, stretch=3)
        splitter.addWidget(top_widget)
        
        # ==============================================================================
        # 2. BOTTOM SECTION (SCROLLABLE CONTROLS)
        # ==============================================================================
        bot_widget = QWidget()
        bot_layout = QVBoxLayout(bot_widget)
        bot_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; }
            QScrollBar:vertical { background: transparent; width: 8px; margin: 0px; }
            QScrollBar::handle:vertical { background: #3A3F4A; min-height: 30px; border-radius: 4px; }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 5, 0, 0)
        
        ctrl = QHBoxLayout()
        ctrl.setSpacing(25)
        
        # ---------------------------------------------------------
        # KIRI BAWAH: CDS API & Request Builder
        # ---------------------------------------------------------
        c1 = QVBoxLayout()
        
        grp0 = QGroupBox("1. Kredensial CDS API & Target Variabel")
        g0 = QFormLayout(grp0)
        g0.setHorizontalSpacing(16)
        g0.setVerticalSpacing(16)
        
        self.inp_api = QLineEdit()
        self.inp_api.setPlaceholderText("UID:API_KEY (e.g., 123456:a1b2c3d4-e5f6)")
        self.inp_api.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        cached_api = self.settings.value('cds_api', '')
        if cached_api: self.inp_api.setText(cached_api)
        
        g0.addRow(QLabel("API Key:", styleSheet=LABEL_STYLE), self.inp_api)
        
        self.var_list = QListWidget()
        self.var_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.var_list.setMinimumHeight(150)

        ERA5_CATALOG = [
            ("═══ KONDISI GELOMBANG (WAVES) ═══", None),
            ("Significant Height of Combined Wind Waves (Hs)", "significant_height_of_combined_wind_waves_and_swell"),
            ("Mean Wave Period (Tm01)", "mean_wave_period"),
            ("Mean Wave Direction (Dir)", "mean_wave_direction"),
            ("Peak Wave Period (Tp)", "peak_wave_period"),
            ("═══ KONDISI ANGIN & PERMUKAAN ═══", None),
            ("10m U-component of Wind", "10m_u_component_of_wind"),
            ("10m V-component of Wind", "10m_v_component_of_wind"),
            ("Mean Sea Level Pressure (MSLP)", "mean_sea_level_pressure"),
        ]
        default_selected = {"significant_height_of_combined_wind_waves_and_swell", "mean_wave_period", "mean_wave_direction"}

        for v_disp, v_id in ERA5_CATALOG:
            item = QListWidgetItem(v_disp)
            if v_id is None:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setForeground(QColor("#6B7280"))
                item.setBackground(QColor("#1F2227"))
            else:
                item.setData(Qt.ItemDataRole.UserRole, v_id)
                if v_id in default_selected: item.setSelected(True)
            self.var_list.addItem(item)

        g0.addRow(QLabel("Katalog:", styleSheet=LABEL_STYLE), self.var_list)
        
        safe_end_dt = QDateTime.currentDateTime().addDays(-5) 
        self.dt_start = QDateTimeEdit(safe_end_dt.addYears(-1))
        self.dt_start.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_start.setCalendarPopup(True)
        
        self.dt_end = QDateTimeEdit(safe_end_dt)
        self.dt_end.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_end.setCalendarPopup(True)
        
        # [HARDENING]: Memicu Time Sync saat tanggal diubah
        self.dt_start.dateTimeChanged.connect(self._sync_time_to_state)
        self.dt_end.dateTimeChanged.connect(self._sync_time_to_state)
        
        h_date = QHBoxLayout()
        h_date.addWidget(self.dt_start)
        h_date.addWidget(QLabel(" s/d ", styleSheet="color:#9CA3AF; font-weight:bold;"))
        h_date.addWidget(self.dt_end)
        g0.addRow(QLabel("Rentang:", styleSheet=LABEL_STYLE), h_date)
        
        self.btn_dl_era5 = QPushButton("↓ Mulai Unduh dari Server Copernicus (.nc)")
        self.btn_dl_era5.setObjectName("PrimaryBtn")
        self.btn_dl_era5.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_dl_era5.clicked.connect(self.run_era5_downloader)
        g0.addRow(self.btn_dl_era5)
        
        c1.addWidget(grp0)
        c1.addStretch()
        ctrl.addLayout(c1, stretch=5)
        
        # ---------------------------------------------------------
        # KANAN BAWAH: Metadata Reader & Manual Override
        # ---------------------------------------------------------
        c2 = QVBoxLayout()
        
        grp2 = QGroupBox("2. Macro-Boundary (Auto-AOI) & Ekstraksi IC")
        g2 = QFormLayout(grp2)
        g2.setHorizontalSpacing(16)
        g2.setVerticalSpacing(16)
        
        btn_load = QPushButton("📂 Validasi File .nc Lokal / Unduhan")
        btn_load.setObjectName("OutlineBtn")
        btn_load.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_load.clicked.connect(self.load_era5_file)
        g2.addRow(btn_load)
        
        # GRID EXTENT DASHBOARD
        self.grid_stats_frame = QFrame()
        self.grid_stats_frame.setStyleSheet("background-color: #1E2128; border: 1px solid #3A3F4A; border-radius: 8px; padding: 5px;")
        g_stat_lay = QHBoxLayout(self.grid_stats_frame)
        g_stat_lay.setContentsMargins(10, 10, 10, 10)
        
        self.bound_labels = {}
        for key, title in [("N", "Lat Max (N)"), ("S", "Lat Min (S)"), ("E", "Lon Max (E)"), ("W", "Lon Min (W)")]:
            f = QVBoxLayout()
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color: #9CA3AF; font-size: 11px;")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val = QLabel("—")
            lbl_val.setStyleSheet("color: #8FC9DC; font-weight: 900; font-size: 13px; font-family: 'Consolas';")
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            f.addWidget(lbl_title)
            f.addWidget(lbl_val)
            self.bound_labels[key] = lbl_val
            g_stat_lay.addLayout(f)
            
        g2.addRow(self.grid_stats_frame)
        
        btn_nc = QPushButton("⚡ Ekstrak IC (Hs, Tp, Dir) & Broadcast Auto-AOI")
        btn_nc.setObjectName("PrimaryBtn")
        btn_nc.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_nc.clicked.connect(self.execute_era5_local)
        g2.addRow(btn_nc)
        
        # Manual Overrides
        self.inp_man_hs = QLineEdit(); self.inp_man_hs.setPlaceholderText("Hs (m)")
        self.inp_man_tp = QLineEdit(); self.inp_man_tp.setPlaceholderText("Tp (s)")
        self.inp_man_dir = QLineEdit(); self.inp_man_dir.setPlaceholderText("Dir (°)")
        
        h_man = QHBoxLayout(); h_man.setSpacing(10)
        h_man.addWidget(self.inp_man_hs); h_man.addWidget(self.inp_man_tp); h_man.addWidget(self.inp_man_dir)
        
        g2.addRow(QLabel("Atau Injeksi Angka Manual:", styleSheet=LABEL_STYLE), h_man)
        
        btn_inj = QPushButton("Injeksi Manual (Tanpa .nc)")
        btn_inj.setObjectName("DangerBtn")
        btn_inj.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_inj.clicked.connect(self.manual_override_wave)
        g2.addRow("", btn_inj)
        
        c2.addWidget(grp2)
        
        # Terminal Sistem
        term_lbl = QLabel("Terminal Integrasi (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#8FC9DC; font-size: 14px; margin-top: 10px;")
        c2.addWidget(term_lbl)
        
        self.log_era5 = QTextEdit()
        self.log_era5.setReadOnly(True)
        self.log_era5.setStyleSheet("background-color: #1E2128; color: #42E695; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #3A3F4A; border-radius: 8px; padding: 12px;")
        self.log_era5.setMinimumHeight(100)
        c2.addWidget(self.log_era5)
        
        ctrl.addLayout(c2, stretch=5)
        
        scroll_layout.addLayout(ctrl)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        bot_layout.addWidget(scroll)
        splitter.addWidget(bot_widget)
        
        splitter.setSizes([450, 450])
        main_layout.addWidget(splitter)
        
        # Sync Initial Time Boundary
        self._sync_time_to_state()

    # --------------------------------------------------------------------------
    # STATE SYNCHRONIZATION & INTERACTION LOGIC
    # --------------------------------------------------------------------------
    
    def _sync_time_to_state(self):
        """[HARDENING] Sync Time Boundary for DIMR/Tidal execution"""
        app_state.update_multiple({
            'sim_start_time': self.dt_start.dateTime().toString(Qt.DateFormat.ISODate),
            'sim_end_time': self.dt_end.dateTime().toString(Qt.DateFormat.ISODate)
        })

    def on_bulk_state_changed(self) -> None:
        """Triggered when update_multiple is called from StateManager."""
        self.on_global_state_changed('Hs') # Trigger visual update

    def on_global_state_changed(self, key: str) -> None:
        """Dipanggil otomatis oleh Singleton StateManager."""
        if key in ['Hs', 'Tp', 'Dir']:
            self.inp_man_hs.setText(f"{app_state.get('Hs', 0):.2f}")
            self.inp_man_tp.setText(f"{app_state.get('Tp', 0):.2f}")
            self.inp_man_dir.setText(f"{app_state.get('Dir', 0):.2f}")
        elif key in ['sim_start_time', 'sim_end_time']:
            # Prevent circular signals
            self.dt_start.blockSignals(True)
            self.dt_end.blockSignals(True)
            
            st_iso = app_state.get('sim_start_time', "")
            en_iso = app_state.get('sim_end_time', "")
            
            if st_iso: self.dt_start.setDateTime(QDateTime.fromString(st_iso, Qt.DateFormat.ISODate))
            if en_iso: self.dt_end.setDateTime(QDateTime.fromString(en_iso, Qt.DateFormat.ISODate))
            
            self.dt_start.blockSignals(False)
            self.dt_end.blockSignals(False)

    def update_era5_bbox(self, data: dict) -> None:
        """Menangkap input BBox Request dari user via Peta Leaflet."""
        self._syncing = True
        self.req_bounds = data 
        self.lbl_req_bbox.setText(f"Request: N{data['N']:.2f}, S{data['S']:.2f}, E{data['E']:.2f}, W{data['W']:.2f}")
        self.lbl_req_bbox.setStyleSheet("color: #42E695; font-weight: bold; font-size:12px; background-color: rgba(66,230,149,0.1); padding: 10px; border-radius: 6px; border: 1px solid #42E695; margin-top: 15px;")
        
        self.tbl_bbox.blockSignals(True)
        self.tbl_bbox.setItem(0, 0, QTableWidgetItem(f"{data['N']:.4f}"))
        self.tbl_bbox.setItem(1, 0, QTableWidgetItem(f"{data['S']:.4f}"))
        self.tbl_bbox.setItem(2, 0, QTableWidgetItem(f"{data['E']:.4f}"))
        self.tbl_bbox.setItem(3, 0, QTableWidgetItem(f"{data['W']:.4f}"))
        self.tbl_bbox.blockSignals(False)
        
        self.log_era5.append("[SYSTEM] Bounding Box Request diperbarui dari Peta.")
        self._syncing = False

    def manual_update_bbox_vertical(self) -> None:
        if self._syncing: return
        try:
            n = float(self.tbl_bbox.item(0,0).text())
            s = float(self.tbl_bbox.item(1,0).text())
            e = float(self.tbl_bbox.item(2,0).text())
            w = float(self.tbl_bbox.item(3,0).text())
            
            if n <= s or e <= w:
                raise ValueError("Koordinat terbalik. (N > S) dan (E > W) mutlak.")
                
            self.req_bounds = {'N': n, 'S': s, 'E': e, 'W': w}
            self.lbl_req_bbox.setText(f"Request Manual: N{n:.2f}, S{s:.2f}, E{e:.2f}, W{w:.2f}")
            self.lbl_req_bbox.setStyleSheet("color: #42E695; font-weight: bold; font-size:12px; background-color: rgba(66,230,149,0.1); padding: 10px; border-radius: 6px; border: 1px solid #42E695; margin-top: 15px;")
            
            js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{w},{s}],[{e},{s}],[{e},{n}],[{w},{n}],[{w},{s}]]]}}, '#595FF7');"
            self.web_map_era5.page().runJavaScript("clearMap(); " + js_box)
            self.log_era5.append("[SYSTEM] Request AOI Manual diterapkan.")
        except Exception as e:
            self.log_era5.append(f"[WARNING] Input manual gagal divalidasi: {str(e)}")

    def run_era5_downloader(self) -> None:
        if hasattr(self, 'era_w') and self.era_w.isRunning():
            QMessageBox.warning(self, "Konflik", "Proses pengunduhan sedang berjalan.")
            return

        api_key = self.inp_api.text().strip()
        bbox = getattr(self, 'req_bounds', None)
        
        if not api_key or not bbox: 
            QMessageBox.critical(self, "Validasi", "Kredensial API CDS dan Request Bounding Box wajib diisi.")
            return
            
        dt_s = self.dt_start.dateTime()
        dt_e = self.dt_end.dateTime()
        if dt_s >= dt_e:
            QMessageBox.critical(self, "Validasi", "Tgl Mulai harus < Tgl Akhir.")
            return
            
        self.settings.setValue('cds_api', api_key)
        
        selected_items = self.var_list.selectedItems()
        if not selected_items: return
            
        params = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        out_file = os.path.abspath(os.path.join(os.getcwd(), "Apex_Data_Exports", "ERA5_WAVE.nc"))
        
        self.btn_dl_era5.setEnabled(False)
        self.btn_dl_era5.setText("⏳ Sedang mengunduh via API satelit...")
        
        self.era_w = ERA5DownloaderWorker(api_key, bbox, params, dt_s, dt_e, out_file)
        self.era_w.log_signal.connect(self.log_era5.append)
        
        def on_finished(success: bool, path: str):
            self.btn_dl_era5.setEnabled(True)
            self.btn_dl_era5.setText("↓ Mulai Unduh dari Server Copernicus (.nc)")
            if success and os.path.exists(path):
                self.load_era5_file(path)
                self.log_era5.append(f"✅ Auto-Loaded: {os.path.basename(path)}")
            self.era_w.deleteLater()
            
        self.era_w.finished_signal.connect(on_finished)
        self.era_w.start()

    def load_era5_file(self, pre_path: str = "") -> None:
        path = pre_path
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Pilih File ERA5 Lokal", "", "NetCDF (*.nc)")
            
        if not path or not os.path.exists(path): return
        
        self.era5_path = path
        self.log_era5.append(f"▶ File aktif: {os.path.basename(path)}")
        
        if not HAS_XARRAY:
            self.log_era5.append("⚠ Pustaka 'xarray' tidak ditemukan. Gagal mengekstrak Metadata Auto-AOI.")
            return
            
        try:
            import xarray as xr
            self.log_era5.append("■ Membedah dimensi grid spasial (Auto-AOI) dari .nc...")
            with xr.open_dataset(path, engine='netcdf4') as ds:
                lon_var = 'longitude' if 'longitude' in ds else 'lon'
                lat_var = 'latitude' if 'latitude' in ds else 'lat'
                
                n = float(ds[lat_var].max())
                s = float(ds[lat_var].min())
                e = float(ds[lon_var].max())
                w = float(ds[lon_var].min())
                
                self.bound_labels["N"].setText(f"{n:.3f}°")
                self.bound_labels["S"].setText(f"{s:.3f}°")
                self.bound_labels["E"].setText(f"{e:.3f}°")
                self.bound_labels["W"].setText(f"{w:.3f}°")
                
                self.actual_nc_bounds = {'N': n, 'S': s, 'E': e, 'W': w}
                self.log_era5.append(f"✅ Metadata Spatial Bounding: N{n:.2f}, S{s:.2f}, E{e:.2f}, W{w:.2f}")
                
        except Exception as e:
            self.log_era5.append(f"❌ Error membaca metadata: {str(e)}")

    def execute_era5_local(self) -> None:
        if not self.era5_path or not os.path.exists(self.era5_path): 
            QMessageBox.critical(self, "Gagal", "File ERA5 belum diunduh/dipilih.")
            return
            
        try:
            if hasattr(self, 'actual_nc_bounds'):
                b = self.actual_nc_bounds
                app_state.update('mesh_bbox', b)
                self.log_era5.append("✅ [AUTO-AOI] Batas Makro D-Waves berhasil disinkronisasi ke Global State.")
                
                js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{b['W']},{b['S']}],[{b['E']},{b['S']}],[{b['E']},{b['N']}],[{b['W']},{b['N']}],[{b['W']},{b['S']}]]]}}, '#FC3F4D');"
                self.web_map_era5.page().runJavaScript("clearMap(); " + js_box)
            
            if HAS_XARRAY:
                self.log_era5.append("▶ Memanggil Out-of-Core Dask Extractor...")
                hs, tp, dir_, doc = ERA5Extractor.extract_wave_params(self.era5_path)
                
                # [HARDENING] Sync Time boundaries too!
                self._sync_time_to_state()
                app_state.update_multiple({'He': hs, 'Hs': hs, 'Tp': tp, 'Dir': dir_, 'DoC': doc})
                
                # Paksa pembaruan TextBox lokal jika sinyal lambat
                self.inp_man_hs.setText(f"{hs:.2f}")
                self.inp_man_tp.setText(f"{tp:.2f}")
                self.inp_man_dir.setText(f"{dir_:.2f}")
                
                self.log_era5.append(f"✅ Initial Condition Terkunci: Hs={hs:.2f}m, Tp={tp:.1f}s, Dir={dir_:.1f}°")
            else:
                self.log_era5.append("❌ Pustaka Xarray tidak terpasang di sistem.")
                
        except Exception as e:
            self.log_era5.append(f"❌ Error ekstraksi lokal: {str(e)}")

    def manual_override_wave(self) -> None:
        try:
            hs = float(self.inp_man_hs.text() or 1.5)
            tp = float(self.inp_man_tp.text() or 8.0)
            dir_ = float(self.inp_man_dir.text() or 180.0)
            doc = 1.57 * hs
            
            # [HARDENING] Ensure time is synced
            self._sync_time_to_state()
            app_state.update_multiple({'He': hs, 'Hs': hs, 'Tp': tp, 'Dir': dir_, 'DoC': doc})
            self.log_era5.append(f"✅ Parameter di-inject manual: Hs={hs}m, Tp={tp}s, Dir={dir_}°")
            
        except ValueError:
            QMessageBox.warning(self, "Input Ditolak", "Input Manual harus berupa angka desimal.")
