# ==============================================================================
# APEX NEXUS TIER-0: MODUL 1 - ERA5 SYNTHESIZER (UI VIEW)
# ==============================================================================
import os
import json
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QLineEdit, QLabel, QPushButton, 
                             QDateTimeEdit, QTextEdit, QFileDialog, QMessageBox, QFrame, 
                             QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget, QListWidget, QAbstractItemView, QListWidgetItem, QHeaderView)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt, QDateTime, QSettings

from ui.components.web_bridge import WebBridge
from utils.config import get_leaflet_html
from workers.era5_worker import ERA5DownloaderWorker
from engines.era5_extractor import ERA5Extractor, HAS_XARRAY
from core.state_manager import app_state

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS (REVOLUT / GRADIENTA INFLUENCE) ---
# Menggunakan palet Slate gelap, aksen Amber, dan layout membulat (rounded)
STYLE_GROUPBOX = """
    QGroupBox {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        margin-top: 24px;
        padding-top: 15px;
        font-weight: bold;
        color: #F1F5F9;
        font-size: 14px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 10px;
        background-color: #0F172A;
        border-radius: 6px;
        color: #F59E0B;
        top: -12px;
        left: 15px;
    }
"""

STYLE_LINEEDIT = """
    QLineEdit, QDateTimeEdit {
        background-color: #0F172A;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 8px 12px;
        color: #F8FAFC;
        font-size: 13px;
        selection-background-color: #F59E0B;
    }
    QLineEdit:focus, QDateTimeEdit:focus {
        border: 1px solid #F59E0B;
    }
"""

STYLE_BTN_PRIMARY = """
    QPushButton {
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F59E0B, stop:1 #D97706);
        color: #022C22;
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton:hover {
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FCD34D, stop:1 #F59E0B);
    }
    QPushButton:pressed {
        background-color: #B45309;
    }
    QPushButton:disabled {
        background-color: #334155;
        color: #94A3B8;
    }
"""

STYLE_BTN_OUTLINE = """
    QPushButton {
        background-color: transparent;
        color: #F8FAFC;
        border: 1px solid #64748B;
        border-radius: 8px;
        padding: 10px 16px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #334155;
        border-color: #F59E0B;
        color: #F59E0B;
    }
"""


class Modul1ERA5(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('ApexStudio', 'HydroSettings')
        self._syncing = False
        self.era5_path = ""  # Diinisialisasi kosong untuk menghindari AttributeError
        
        # Mengaitkan sinyal global StateManager untuk responsivitas lintas modul
        app_state.state_updated.connect(self.on_global_state_changed)
        
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_LINEEDIT}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)
        
        # --- HEADER (REVOLUT STYLE) ---
        head = QVBoxLayout()
        t = QLabel("Metocean Synthesizer (ERA5)")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Unduh, ekstrak, dan sintesis parameter angin serta gelombang historis melalui CDS API Copernicus.")
        d.setStyleSheet("color: #94A3B8; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)
        
        # --- 1. TOP SECTION (MAP & AOI) ---
        top_section = QHBoxLayout()
        top_section.setSpacing(16)
        
        # KIRI: Peta Leaflet WebEngine
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: 1px solid #1E293B; border-radius: 12px; background: #000; overflow: hidden;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(1, 1, 1, 1) # Margin sangat tipis agar map terlihat menyatu
        
        self.web_map_era5 = QWebEngineView()
        self.web_map_era5.setMinimumHeight(400)
        
        # Inisiasi Komunikasi Jembatan Python-JS yang Aman (Dari File 15)
        self.bridge_era5 = WebBridge()
        self.bridge_era5.bbox_drawn.connect(self.update_era5_bbox)
        
        self.web_map_era5.page().setWebChannel(QWebChannel(self.web_map_era5.page()))
        self.web_map_era5.page().webChannel().registerObject("bridge", self.bridge_era5)
        self.web_map_era5.setHtml(get_leaflet_html("era5"))
        tl.addWidget(self.web_map_era5)
        
        top_section.addWidget(top_wrap, stretch=7)
        
        # KANAN: Panel Tab Input AOI
        self.tabs_aoi = QTabWidget()
        self.tabs_aoi.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; border-radius: 8px; background: #1E293B; }
            QTabBar::tab { background: #0F172A; color: #94A3B8; padding: 10px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;}
            QTabBar::tab:selected { background: #1E293B; color: #F59E0B; font-weight: bold; border-bottom: 2px solid #F59E0B;}
        """)
        
        # Tab 1: Peta Interaktif
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(16, 20, 16, 16)
        lbl_msg = QLabel("💡 Gunakan fitur Draw Rectangle (Kotak) pada toolbar peta di sebelah kiri untuk menggambar area batas ekstraksi ERA5 secara otomatis.")
        lbl_msg.setStyleSheet("color: #CBD5E1; font-size: 13px; line-height: 1.6;")
        lbl_msg.setWordWrap(True)
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l1.addWidget(lbl_msg)
        l1.addStretch()
        self.tabs_aoi.addTab(t1, "Mode Interaktif")
        
        # Tab 2: Input Manual (Grid WGS84)
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(16, 16, 16, 16)
        lbl_aoi = QLabel("Input Koordinat WGS84 (Lat/Lon):")
        lbl_aoi.setStyleSheet("font-weight: bold; color: #F8FAFC; font-size: 13px;")
        l2.addWidget(lbl_aoi)
        
        self.tbl_bbox = QTableWidget(4, 1)
        self.tbl_bbox.setStyleSheet("""
            QTableWidget { background-color: #0F172A; color: #F8FAFC; gridline-color: #334155; border: 1px solid #334155; border-radius: 6px; }
            QHeaderView::section { background-color: #1E293B; color: #94A3B8; padding: 4px; font-weight: bold; border: 1px solid #334155; }
        """)
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
        self.tabs_aoi.addTab(t2, "Manual Input")
        
        top_section.addWidget(self.tabs_aoi, stretch=3)
        main_layout.addLayout(top_section, stretch=1)
        
        # --- 2. BOTTOM SECTION (SCROLLABLE CONTROLS) ---
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
        scroll_layout.setContentsMargins(0, 10, 0, 0)
        
        ctrl = QHBoxLayout()
        ctrl.setSpacing(20)
        
        # KIRI BAWAH: CDS API & List Variabel
        c1 = QVBoxLayout()
        
        grp0 = QGroupBox("1. Kredensial CDS API")
        g0 = QVBoxLayout(grp0)
        g0.setSpacing(12)
        
        self.inp_api = QLineEdit()
        self.inp_api.setPlaceholderText("UID:API_KEY (e.g., 123456:a1b2c3d4-e5f6-g7h8-i9j0)")
        self.inp_api.setToolTip("Dapatkan kunci API ini dari dashboard profil Copernicus Climate Data Store Anda.")
        self.inp_api.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit) # Masking keamanan
        
        cached_api = self.settings.value('cds_api', '')
        if cached_api:
            self.inp_api.setText(cached_api)
            
        g0.addWidget(self.inp_api)
        
        self.lbl_era_bbox = QLabel("Batas Spasial (BBox): Belum Ditetapkan")
        self.lbl_era_bbox.setStyleSheet("color:#EF4444; font-weight:bold; font-size:13px;")
        g0.addWidget(self.lbl_era_bbox)
        c1.addWidget(grp0)
        
        grp1 = QGroupBox("2. Parameter & Resolusi Waktu")
        g1 = QFormLayout(grp1)
        g1.setSpacing(16)
        
        self.var_list = QListWidget()
        self.var_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.var_list.setMinimumHeight(180)
        self.var_list.setStyleSheet("""
            QListWidget { background-color: #0F172A; border: 1px solid #475569; border-radius: 6px; padding: 5px; color: #F8FAFC; }
            QListWidget::item:selected { background-color: #334155; color: #F59E0B; border-left: 3px solid #F59E0B; }
        """)

        # Katalog ERA5 sesuai spesifikasi Oceanografi
        ERA5_CATALOG = [
            ("═══ KONDISI GELOMBANG (WAVES) ═══", None),
            ("Significant Height of Combined Wind Waves (Hs)", "significant_height_of_combined_wind_waves"),
            ("Mean Wave Period (Tm01)", "mean_wave_period"),
            ("Mean Wave Direction (Dir)", "mean_wave_direction"),
            ("Peak Wave Period (Tp)", "peak_wave_period"),
            ("Ocean Surface Stokes Drift U", "u_component_stokes_drift"),
            ("Ocean Surface Stokes Drift V", "v_component_stokes_drift"),
            ("═══ KONDISI ANGIN (WIND) ═══", None),
            ("10m U-component of Wind", "10m_u_component_of_wind"),
            ("10m V-component of Wind", "10m_v_component_of_wind"),
            ("Instantaneous 10m Wind Gust", "instantaneous_10m_wind_gust"),
            ("═══ KONDISI PERMUKAAN LAUT ═══", None),
            ("Sea Surface Temperature (SST)", "sea_surface_temperature"),
            ("Mean Sea Level Pressure (MSLP)", "mean_sea_level_pressure"),
        ]

        default_selected = {
            "significant_height_of_combined_wind_waves",
            "mean_wave_period",
            "mean_wave_direction",
        }

        for v_disp, v_id in ERA5_CATALOG:
            item = QListWidgetItem(v_disp)
            if v_id is None:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setForeground(QColor("#64748B"))
                item.setBackground(QColor("#1E293B"))
            else:
                item.setData(Qt.ItemDataRole.UserRole, v_id)
                if v_id in default_selected:
                    item.setSelected(True)
            self.var_list.addItem(item)

        g1.addRow(QLabel("Katalog Variabel:", styleSheet="color:#94A3B8;")),
        g1.addRow(self.var_list)
        
        # Penanggalan dengan pembatas logis
        safe_end_dt = QDateTime.currentDateTime().addDays(-5) # Delay rilisan ERA5
        self.dt_start = QDateTimeEdit(safe_end_dt.addYears(-1))
        self.dt_start.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_start.setCalendarPopup(True)
        
        self.dt_end = QDateTimeEdit(safe_end_dt)
        self.dt_end.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_end.setCalendarPopup(True)
        
        g1.addRow("Tgl Mulai:", self.dt_start)
        g1.addRow("Tgl Akhir:", self.dt_end)
        
        self.btn_dl_era5 = QPushButton("↓ Mulai Unduh dari Server Copernicus (.nc)")
        self.btn_dl_era5.setStyleSheet(STYLE_BTN_PRIMARY)
        self.btn_dl_era5.clicked.connect(self.run_era5_downloader)
        g1.addRow(self.btn_dl_era5)
        
        c1.addWidget(grp1)
        ctrl.addLayout(c1, stretch=5)
        
        # KANAN BAWAH: Manual Override & Terminal
        c2 = QVBoxLayout()
        
        grp2 = QGroupBox("3. Ekstraksi Sentral & Manual Override")
        g2 = QFormLayout(grp2)
        g2.setSpacing(16)
        
        btn_load = QPushButton("📂 Pilih File .nc Lokal")
        btn_load.setStyleSheet(STYLE_BTN_OUTLINE)
        btn_load.clicked.connect(self.load_era5_file)
        g2.addRow(btn_load)
        
        btn_nc = QPushButton("⚡ Ekstrak Nilai Rata-rata dari NetCDF")
        btn_nc.setStyleSheet(STYLE_BTN_OUTLINE)
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
        g2.addRow(QLabel("Atau Injeksi Angka Manual:", styleSheet="color:#94A3B8; font-size:12px; margin-top:10px;"))
        g2.addRow(h_man)
        
        btn_inj = QPushButton("Gunakan Input Manual")
        btn_inj.setStyleSheet(STYLE_BTN_OUTLINE)
        btn_inj.clicked.connect(self.manual_override_wave)
        g2.addRow(btn_inj)
        
        c2.addWidget(grp2)
        
        # Terminal Sistem
        term_lbl = QLabel("Terminal Proses (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#38BDF8; font-size: 14px; margin-top: 10px;")
        c2.addWidget(term_lbl)
        
        self.log_era5 = QTextEdit()
        self.log_era5.setReadOnly(True)
        self.log_era5.setStyleSheet("background-color: #020617; color: #10B981; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #1E293B; border-radius: 6px; padding: 8px;")
        c2.addWidget(self.log_era5)
        
        ctrl.addLayout(c2, stretch=5)
        
        scroll_layout.addLayout(ctrl)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

    # --------------------------------------------------------------------------
    # STATE SYNCHRONIZATION & INTERACTION LOGIC
    # --------------------------------------------------------------------------
    
    def on_global_state_changed(self, key: str) -> None:
        """Dipanggil otomatis oleh Singleton StateManager jika memori berubah."""
        # Jika Worker selesai mengkalkulasi DoC, update UI otomatis (Contoh interaktivitas lintas modul)
        if key in ['Hs', 'Tp', 'Dir', 'DoC']:
            hs = app_state.get('Hs', 0)
            tp = app_state.get('Tp', 0)
            dir_ = app_state.get('Dir', 0)
            self.inp_man_hs.setText(f"{hs:.2f}")
            self.inp_man_tp.setText(f"{tp:.2f}")
            self.inp_man_dir.setText(f"{dir_:.2f}")

    def update_era5_bbox(self, data: dict) -> None:
        """Menerima poligon BBox dari Leaflet Map secara real-time via Jembatan Web."""
        self._syncing = True
        app_state.update('mesh_bbox', data)
        self.lbl_era_bbox.setText(f"✓ Batas AOI: N{data['N']:.3f}, S{data['S']:.3f}, E{data['E']:.3f}, W{data['W']:.3f}")
        self.lbl_era_bbox.setStyleSheet("color: #10B981; font-weight: bold; font-size:13px;")
        
        # Mencegah signal loop back (pembaruan tabel tidak akan memicu penggambaran peta lagi)
        self.tbl_bbox.blockSignals(True)
        self.tbl_bbox.setItem(0, 0, QTableWidgetItem(f"{data['N']:.4f}"))
        self.tbl_bbox.setItem(1, 0, QTableWidgetItem(f"{data['S']:.4f}"))
        self.tbl_bbox.setItem(2, 0, QTableWidgetItem(f"{data['E']:.4f}"))
        self.tbl_bbox.setItem(3, 0, QTableWidgetItem(f"{data['W']:.4f}"))
        for i in range(4): self.tbl_bbox.item(i, 0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tbl_bbox.blockSignals(False)
        
        self.log_era5.append("[SYSTEM] Bounding Box berhasil disinkronisasi dari Peta.")
        self._syncing = False

    def manual_update_bbox_vertical(self) -> None:
        if self._syncing: return
        try:
            n = float(self.tbl_bbox.item(0,0).text())
            s = float(self.tbl_bbox.item(1,0).text())
            e = float(self.tbl_bbox.item(2,0).text())
            w = float(self.tbl_bbox.item(3,0).text())
            
            # Guard: Logika arah mata angin tidak boleh terbalik
            if n <= s or e <= w:
                raise ValueError("Koordinat terbalik. (N > S) dan (E > W) adalah syarat mutlak.")
                
            data = {'N': n, 'S': s, 'E': e, 'W': w}
            app_state.update('mesh_bbox', data)
            
            self.lbl_era_bbox.setText(f"✓ Manual BBox disinkronisasi: N{n:.2f}, S{s:.2f}, E{e:.2f}, W{w:.2f}")
            self.lbl_era_bbox.setStyleSheet("color: #10B981; font-weight: bold; font-size:13px;")
            
            # Menggambar ulang kotak oranye di peta Leaflet secara dinamis
            js_box = f"addGeoJSON({{\"type\":\"Polygon\",\"coordinates\":[[[{w},{s}],[{e},{s}],[{e},{n}],[{w},{n}],[{w},{s}]]]}}, '#F59E0B');"
            self.web_map_era5.page().runJavaScript("clearMap(); " + js_box)
            self.log_era5.append("[SYSTEM] Tabel Manual AOI berhasil dikirim dan digambar ke Peta.")
        except Exception as e:
            self.log_era5.append(f"[WARNING] Input manual gagal divalidasi: {str(e)}")

    def load_era5_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pilih File ERA5 Lokal", "", "NetCDF (*.nc)")
        if path:
            self.era5_path = path
            self.log_era5.append(f"▶ File sumber aktif disetel ke: {os.path.basename(path)}")

    def run_era5_downloader(self) -> None:
        # 1. Thread concurrency guard (Seksi 5.B Requirement)
        if hasattr(self, 'era_w') and self.era_w.isRunning():
            QMessageBox.warning(self, "Konflik", "Proses pengunduhan sedang berjalan. Harap tunggu.")
            return

        api_key = self.inp_api.text().strip()
        bbox = app_state.get('mesh_bbox')
        
        # 2. Input validation guard
        if not api_key or not bbox: 
            QMessageBox.critical(self, "Validasi Gagal", "Kredensial API CDS dan Bounding Box di peta tidak boleh kosong.")
            return
            
        dt_s = self.dt_start.dateTime()
        dt_e = self.dt_end.dateTime()
        
        if dt_s >= dt_e:
            QMessageBox.critical(self, "Validasi Gagal", "Tanggal mulai (Start) harus lebih lampau daripada Tanggal Akhir (End).")
            return
            
        self.settings.setValue('cds_api', api_key)
        
        selected_items = self.var_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Validasi Gagal", "Pilih minimal 1 Variabel dari katalog ERA5!")
            return
            
        params = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        out_file = os.path.abspath(os.path.join(os.getcwd(), "Apex_Data_Exports", "ERA5_WAVE.nc"))
        
        # Mengubah status antarmuka
        self.btn_dl_era5.setEnabled(False)
        self.btn_dl_era5.setText("⏳ Sedang mengunduh via API satelit...")
        
        # Melepas instruksi ke background worker (O(1) Main Thread memory usage)
        self.era_w = ERA5DownloaderWorker(api_key, bbox, params, dt_s, dt_e, out_file)
        self.era_w.log_signal.connect(self.log_era5.append)
        
        def on_finished(success: bool, path: str):
            self.btn_dl_era5.setEnabled(True)
            self.btn_dl_era5.setText("↓ Mulai Unduh dari Server Copernicus (.nc)")
            
            if success and os.path.exists(path):
                self.era5_path = path # BUG FIX: Otomatis menetapkan path aktif setelah unduh selesai
                self.log_era5.append(f"[SYSTEM] Unduhan selesai. File aktif disetel otomatis ke: {os.path.basename(path)}")
                # Menawarkan ekstraksi otomatis
                if QMessageBox.question(self, "Sukses", "Unduhan selesai. Apakah Anda ingin mengekstrak rata-rata gelombang (Hs, Tp, Dir) sekarang?") == QMessageBox.StandardButton.Yes:
                    self.execute_era5_local()
                    
            self.era_w.deleteLater() # Strict Garbage Collection
            
        self.era_w.finished_signal.connect(on_finished)
        self.era_w.start()

    def execute_era5_local(self) -> None:
        """Mendelegasikan file NC ke Dask Engine untuk diekstraksi ke Memori Global."""
        if not self.era5_path or not os.path.exists(self.era5_path): 
            QMessageBox.critical(self, "Gagal Ekstraksi", "File ERA5 belum diunduh atau belum dipilih secara manual.")
            return
            
        if not HAS_XARRAY: 
            self.log_era5.append("❌ Pustaka sistem inti (xarray/dask/netCDF4) tidak ditemukan di mesin.")
            return
            
        try:
            self.log_era5.append("▶ Memanggil Engine Ekstraksi (Out-of-Core Xarray)...")
            hs, tp, dir_, doc = ERA5Extractor.extract_wave_params(self.era5_path)
            
            # Atomic update ke Memori Global
            app_state.update_multiple({'He': hs, 'Hs': hs, 'Tp': tp, 'Dir': dir_, 'DoC': doc})
            self.log_era5.append(f"✅ Ekstrak sukses dikirim ke memori inti: Hs={hs:.2f}m, Tp={tp:.1f}s, Dir={dir_:.1f}°, DoC={doc:.2f}m")
            
        except Exception as e:
            logger.error(f"Kegagalan ekstraksi UI: {str(e)}")
            self.log_era5.append(f"❌ Error ekstraksi lokal: {str(e)}")

    def manual_override_wave(self) -> None:
        try:
            hs = float(self.inp_man_hs.text() or 1.5)
            tp = float(self.inp_man_tp.text() or 8.0)
            dir_ = float(self.inp_man_dir.text() or 180.0)
            doc = 1.57 * hs
            
            # Atomic update ke Memori Global
            app_state.update_multiple({'He': hs, 'Hs': hs, 'Tp': tp, 'Dir': dir_, 'DoC': doc})
            self.log_era5.append(f"✅ Parameter Skripsi di-inject manual ke StateManager: Hs={hs}m, Tp={tp}s, Dir={dir_}°, DoC={doc:.3f}m")
            
        except ValueError:
            QMessageBox.warning(self, "Input Ditolak", "Input Manual harus berupa angka (Float).")
