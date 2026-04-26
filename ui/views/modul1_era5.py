# ==============================================================================
# APEX NEXUS TIER-0: MODUL 1 - ERA5 SYNTHESIZER (UI VIEW)
# ==============================================================================
import os
import logging
import traceback
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLineEdit, QLabel, QPushButton, QDateTimeEdit, 
                             QTextEdit, QFileDialog, QMessageBox, QFrame, 
                             QTableWidget, QTableWidgetItem, QTabWidget, 
                             QListWidget, QAbstractItemView, QListWidgetItem, 
                             QHeaderView, QSplitter)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt, QDateTime, QSettings
from PyQt6.QtGui import QColor, QCursor

# Mengimpor komponen Flexbox dari core_widgets
from ui.components.core_widgets import FlexScrollArea, CardWidget, ModernButton
from ui.components.web_bridge import WebBridge
from utils.config import get_leaflet_html
from workers.era5_worker import ERA5DownloaderWorker
from engines.era5_extractor import ERA5Extractor, HAS_XARRAY
from core.state_manager import app_state

logger = logging.getLogger(__name__)

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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # Margin diurus oleh FlexScrollArea
        
        # 1. BUNGKUS DENGAN FLEX SCROLL AREA UNTUK MENCEGAH "CEMET"
        self.scroll_base = FlexScrollArea(self)
        
        # --- HEADER ---
        head = QVBoxLayout()
        t = QLabel("Metocean Synthesizer (ERA5)")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        
        d = QLabel("<div style='text-align: justify; line-height: 1.5;'>Unduh Data Copernicus CDS (Sistem Baru), Ekstrak Kondisi Awal (Initial Condition), dan Generasi Macro-AOI Otomatis dengan penyesuaian buffer spasial untuk mencegah kegagalan Crop MARS.</div>")
        d.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        d.setWordWrap(True)
        head.addWidget(t)
        head.addWidget(d)
        head.setContentsMargins(0, 0, 0, 10)
        self.scroll_base.add_layout(head)
        
        # --- SPLITTER UTAMA ---
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
        
        lbl_msg = QLabel("<div style='text-align: justify; line-height: 1.5;'>💡 Gunakan fitur Draw Rectangle pada toolbar peta untuk menentukan area makro. Sistem akan otomatis menambahkan <b>buffer spasial 0.5°</b> (≈ 55km) saat mengunduh untuk mencegah <i>Empty Area Mask Error</i> pada server satelit.</div>")
        lbl_msg.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        lbl_msg.setWordWrap(True)
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
        lbl_aoi = QLabel("Request Bounds (Lat/Lon):")
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
        # 2. BOTTOM SECTION (CARD WIDGETS)
        # ==============================================================================
        bot_widget = QWidget()
        bot_layout = QHBoxLayout(bot_widget)
        bot_layout.setContentsMargins(0, 10, 0, 0)
        bot_layout.setSpacing(20)
        
        # KIRI BAWAH: CDS API & Request Builder
        grp0 = CardWidget("1. Kredensial CDS API & Target Variabel")
        
        self.inp_api = QLineEdit()
        self.inp_api.setPlaceholderText("Paste API Key Baru CDS (Contoh UUID: 24af6dec-...)")
        self.inp_api.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        cached_api = self.settings.value('cds_api', '')
        if cached_api: self.inp_api.setText(cached_api)
        
        # Menggunakan Grid Layout internal untuk Form
        g0 = QFormLayout()
        g0.setHorizontalSpacing(16)
        g0.setVerticalSpacing(16)
        g0.addRow(QLabel("API Key:"), self.inp_api)
        
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

        g0.addRow(QLabel("Katalog:"), self.var_list)
        
        safe_end_dt = QDateTime.currentDateTime().addDays(-5) 
        self.dt_start = QDateTimeEdit(safe_end_dt.addYears(-1))
        self.dt_start.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_start.setCalendarPopup(True)
        
        self.dt_end = QDateTimeEdit(safe_end_dt)
        self.dt_end.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_end.setCalendarPopup(True)
        
        self.dt_start.dateTimeChanged.connect(self._sync_time_to_state)
        self.dt_end.dateTimeChanged.connect(self._sync_time_to_state)
        
        h_date = QHBoxLayout()
        h_date.addWidget(self.dt_start)
        h_date.addWidget(QLabel(" s/d ", styleSheet="color:#9CA3AF; font-weight:bold;"))
        h_date.addWidget(self.dt_end)
        g0.addRow(QLabel("Rentang:"), h_date)
        grp0.add_layout(g0)
        
        self.btn_dl_era5 = ModernButton("↓ Mulai Unduh dari Server Copernicus (.nc)", "primary")
        self.btn_dl_era5.clicked.connect(self.run_era5_downloader)
        grp0.add_widget(self.btn_dl_era5)
        
        bot_layout.addWidget(grp0, stretch=5)
        
        # KANAN BAWAH: Metadata Reader & Manual Override
        grp2 = CardWidget("2. Macro-Boundary (Auto-AOI) & Ekstraksi IC")
        
        btn_load = ModernButton("📂 Validasi File .nc Lokal / Unduhan", "outline")
        btn_load.clicked.connect(self.load_era5_file)
        grp2.add_widget(btn_load)
        
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
            
        grp2.add_widget(self.grid_stats_frame)
        
        btn_nc = ModernButton("⚡ Ekstrak IC (Hs, Tp, Dir) & Broadcast Auto-AOI", "primary")
        btn_nc.clicked.connect(self.execute_era5_local)
        grp2.add_widget(btn_nc)
        
        # Manual Overrides
        g2 = QFormLayout()
        self.inp_man_hs = QLineEdit(); self.inp_man_hs.setPlaceholderText("Hs (m)")
        self.inp_man_tp = QLineEdit(); self.inp_man_tp.setPlaceholderText("Tp (s)")
        self.inp_man_dir = QLineEdit(); self.inp_man_dir.setPlaceholderText("Dir (°)")
        
        h_man = QHBoxLayout(); h_man.setSpacing(10)
        h_man.addWidget(self.inp_man_hs); h_man.addWidget(self.inp_man_tp); h_man.addWidget(self.inp_man_dir)
        g2.addRow(QLabel("Input Manual:"), h_man)
        
        btn_inj = ModernButton("Injeksi Manual (Tanpa .nc)", "danger")
        btn_inj.clicked.connect(self.manual_override_wave)
        g2.addRow("", btn_inj)
        grp2.add_layout(g2)
        
        # Terminal Sistem
        term_lbl = QLabel("Terminal Integrasi (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#8FC9DC; font-size: 14px; margin-top: 10px;")
        grp2.add_widget(term_lbl)
        
        self.log_era5 = QTextEdit()
        self.log_era5.setObjectName("TerminalOutput")
        self.log_era5.setReadOnly(True)
        self.log_era5.setMinimumHeight(100)
        grp2.add_widget(self.log_era5)
        
        bot_layout.addWidget(grp2, stretch=5)
        
        splitter.addWidget(bot_widget)
        splitter.setSizes([450, 450])
        
        self.scroll_base.add_widget(splitter)
        main_layout.addWidget(self.scroll_base)
        
        # Sync Initial Time Boundary
        self._sync_time_to_state()

    # --------------------------------------------------------------------------
    # STATE SYNCHRONIZATION & INTERACTION LOGIC
    # --------------------------------------------------------------------------
    
    def _sync_time_to_state(self):
        app_state.update_multiple({
            'sim_start_time': self.dt_start.dateTime().toString(Qt.DateFormat.ISODate),
            'sim_end_time': self.dt_end.dateTime().toString(Qt.DateFormat.ISODate)
        })

    def on_bulk_state_changed(self) -> None:
        self.on_global_state_changed('Hs') 

    def on_global_state_changed(self, key: str) -> None:
        if key in ['Hs', 'Tp', 'Dir']:
            self.inp_man_hs.setText(f"{app_state.get('Hs', 0):.2f}")
            self.inp_man_tp.setText(f"{app_state.get('Tp', 0):.2f}")
            self.inp_man_dir.setText(f"{app_state.get('Dir', 0):.2f}")
        elif key in ['sim_start_time', 'sim_end_time']:
            self.dt_start.blockSignals(True)
            self.dt_end.blockSignals(True)
            
            st_iso = app_state.get('sim_start_time', "")
            en_iso = app_state.get('sim_end_time', "")
            
            if st_iso: self.dt_start.setDateTime(QDateTime.fromString(st_iso, Qt.DateFormat.ISODate))
            if en_iso: self.dt_end.setDateTime(QDateTime.fromString(en_iso, Qt.DateFormat.ISODate))
            
            self.dt_start.blockSignals(False)
            self.dt_end.blockSignals(False)

    def update_era5_bbox(self, data: dict) -> None:
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

    def manual_update_bbox_vertical(self, item=None) -> None:
        if getattr(self, '_syncing', False): return
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
            pass

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
        
        self.log_era5.append("■ Menginjeksikan buffer spasial 0.5° untuk mencegah MARS Server Empty Area Error...")
        buffered_bbox = {
            'N': bbox['N'] + 0.5,
            'S': bbox['S'] - 0.5,
            'E': bbox['E'] + 0.5,
            'W': bbox['W'] - 0.5
        }
        
        self.btn_dl_era5.setEnabled(False)
        self.btn_dl_era5.setText("⏳ Sedang mengunduh via API satelit...")
        
        self.era_w = ERA5DownloaderWorker(api_key, buffered_bbox, params, dt_s, dt_e, out_file)
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
                
                self._sync_time_to_state()
                app_state.update_multiple({'He': hs, 'Hs': hs, 'Tp': tp, 'Dir': dir_, 'DoC': doc})
                
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
            
            self._sync_time_to_state()
            app_state.update_multiple({'He': hs, 'Hs': hs, 'Tp': tp, 'Dir': dir_, 'DoC': doc})
            self.log_era5.append(f"✅ Parameter di-inject manual: Hs={hs}m, Tp={tp}s, Dir={dir_}°")
            
        except ValueError:
            QMessageBox.warning(self, "Input Ditolak", "Input Manual harus berupa angka desimal.")
