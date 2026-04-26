# ==============================================================================
# APEX NEXUS TIER-0: MODUL 6 - POST-PROCESSING & VALIDATION DASHBOARD
# ==============================================================================
import os
import json
import logging
import traceback
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QFormLayout, QComboBox, QLabel, 
                             QTextEdit, QFileDialog, QSlider, QFrame,
                             QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget, 
                             QHeaderView, QSplitter, QGridLayout, QLineEdit, QSizePolicy)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QCursor

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False

from utils.config import get_leaflet_html
from workers.postproc_worker import PostProcAnimationWorker, ValidationWorker
from core.state_manager import app_state
from ui.components.web_bridge import WebBridge
from ui.components.core_widgets import FlexScrollArea, CardWidget, ModernButton

logger = logging.getLogger(__name__)

LABEL_STYLE = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 12px; border: none; }"

class Modul6PostProc(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.nc_file = ""
        self.val_nc_file = ""
        self.val_csv_file = ""
        self.current_max_time = 0
        self.setup_ui()

    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # --- COMPACT HEADER ---
        head = QVBoxLayout()
        title_container = QFrame()
        title_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        title_container.setStyleSheet("QFrame { background-color: #1E2128; border: 1px solid #3A3F4A; border-radius: 8px; }")
        
        tc_layout = QVBoxLayout(title_container)
        tc_layout.setContentsMargins(12, 8, 12, 8)
        tc_layout.setSpacing(2)
        
        t = QLabel("Post-Processing & Validation Dashboard")
        t.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; border: none;")
        
        d = QLabel(
            "Render animasi spasial perambatan gelombang (NetCDF Overlay) dan "
            "Validasi statistik Point-Extraction menggunakan KD-Tree Nearest Neighbor (Wave Spectra)."
        )
        d.setStyleSheet("color: #9CA3AF; font-size: 11px; border: none;")
        d.setWordWrap(True)
        
        tc_layout.addWidget(t)
        tc_layout.addWidget(d)
        head.addWidget(title_container)
        main_layout.addLayout(head)

        # ==============================================================================
        # MASTER TABS: SPATIAL ANIMATION vs POINT VALIDATION
        # ==============================================================================
        self.master_tabs = QTabWidget()
        self.master_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3A3F4A; border-radius: 12px; background: transparent; top: -1px; }
            QTabBar::tab { background: #1F2227; color: #9CA3AF; padding: 12px 24px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; font-weight: 900; font-size: 13px; border: 1px solid #3A3F4A; border-bottom: none; }
            QTabBar::tab:selected { background: #2D3139; color: #595FF7; border-top: 3px solid #595FF7; color: #FFFFFF; }
            QTabBar::tab:hover:!selected { background: #2D3139; color: #FFFFFF; }
        """)
        
        self.tab_spatial = QWidget()
        self.build_spatial_tab()
        self.master_tabs.addTab(self.tab_spatial, "🗺️ Animasi Spasial Dinamis")
        
        self.tab_validation = QWidget()
        self.build_validation_tab()
        self.master_tabs.addTab(self.tab_validation, "📊 Validasi Matriks (Model vs Obs)")
        
        main_layout.addWidget(self.master_tabs, stretch=1)

    def build_spatial_tab(self) -> None:
        """Membangun antarmuka untuk animasi Heatmap spasial."""
        layout = QVBoxLayout(self.tab_spatial)
        layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")
        
        # --- TOP: MAP (Full Width) ---
        map_frame = QFrame()
        map_frame.setStyleSheet("border: none; border-radius: 0px; background: #000; overflow: hidden;")
        ml = QVBoxLayout(map_frame); ml.setContentsMargins(1, 1, 1, 1)
        self.web_map = QWebEngineView()
        self.web_map.setHtml(get_leaflet_html("postproc"))
        ml.addWidget(self.web_map)
        splitter.addWidget(map_frame)
        
        # --- BOTTOM: CONTROLS & TIMELINE (FLEX SCROLL) ---
        self.scroll_spatial = FlexScrollArea()
        
        h_ctrl = QHBoxLayout()
        h_ctrl.setContentsMargins(0,0,0,0)
        h_ctrl.setSpacing(16)
        
        # File & Var Configuration
        grp1 = CardWidget("1. Konfigurasi Visual Output")
        g1 = QFormLayout()
        g1.setVerticalSpacing(12); g1.setHorizontalSpacing(12)
        
        self.btn_nc = ModernButton("📂 Load Model NetCDF (.nc)", "outline")
        self.btn_nc.clicked.connect(lambda: self.load_file('spatial_nc'))
        g1.addRow(self.btn_nc)
        
        self.cmb_var = QComboBox()
        self.cmb_var.addItems(['Hsig', 'Tp', 'Wdir', 'mesh2d_s1', 'mesh2d_ucx', 'mesh2d_taus'])
        self.cmb_var.setStyleSheet("background-color: #1F2227; border: 1px solid #3A3F4A; border-radius: 6px; padding: 6px; color: white;")
        g1.addRow(QLabel("Variabel Target: ", styleSheet=LABEL_STYLE), self.cmb_var)
        
        self.btn_ren = ModernButton("▶ RENDER FRAME", "primary")
        self.btn_ren.clicked.connect(lambda: self.trigger_render(self.sld_time.value()))
        g1.addRow(self.btn_ren)
        grp1.add_layout(g1)
        
        h_ctrl.addWidget(grp1, stretch=3)
        
        # Scrubber
        grp2 = CardWidget("2. Spatio-Temporal Scrubber (Time Series)")
        g2 = QVBoxLayout()
        g2.setSpacing(16)
        
        h_info = QHBoxLayout()
        self.lbl_t_idx = QLabel("Idx: [ 0 ]")
        self.lbl_t_idx.setStyleSheet("color:#38BDF8; font-weight:900; font-size:14px; font-family:'Consolas'; border: none;")
        
        self.lbl_t_str = QLabel("Waktu Aktual: -")
        self.lbl_t_str.setStyleSheet("color:#42E695; font-weight:900; font-size:14px; font-family:'Consolas'; background-color:#1F2227; padding:6px 12px; border-radius:6px; border:1px solid #3A3F4A;")
        
        h_info.addWidget(self.lbl_t_idx); h_info.addStretch(); h_info.addWidget(self.lbl_t_str)
        g2.addLayout(h_info)
        
        self.sld_time = QSlider(Qt.Orientation.Horizontal)
        self.sld_time.setRange(0, 0); self.sld_time.setValue(0); self.sld_time.setEnabled(False)
        self.sld_time.setStyleSheet("""
            QSlider::groove:horizontal { border-radius: 4px; height: 10px; background-color: #1F2227; border: 1px solid #3A3F4A; }
            QSlider::handle:horizontal { background-color: #FFFFFF; border: 3px solid #595FF7; width: 20px; height: 20px; margin: -6px 0; border-radius: 10px; }
            QSlider::sub-page:horizontal { background-color: #595FF7; border-radius: 4px; }
        """)
        self.sld_time.valueChanged.connect(self.on_slider_moved)
        self.sld_time.sliderReleased.connect(self.on_slider_released)
        g2.addWidget(self.sld_time)
        
        # Petunjuk
        hint = QLabel("Geser tuas (*slider*) untuk melihat dinamika gelombang/pasut dari waktu ke waktu. Klik Render untuk mengekspor gambar ke peta.")
        hint.setStyleSheet("color:#64748B; font-size:11px; font-style:italic; border:none;")
        hint.setWordWrap(True)
        g2.addWidget(hint)
        
        grp2.add_layout(g2)
        h_ctrl.addWidget(grp2, stretch=7)
        
        self.scroll_spatial.add_layout(h_ctrl)
        splitter.addWidget(self.scroll_spatial)
        
        splitter.setSizes([600, 250])
        layout.addWidget(splitter)

    def build_validation_tab(self) -> None:
        """Membangun antarmuka untuk ekstraksi titik tunggal dan perbandingan (Model vs Observasi)."""
        layout = QVBoxLayout(self.tab_validation)
        layout.setContentsMargins(16, 16, 16, 16)
        
        splitter_val = QSplitter(Qt.Orientation.Vertical)
        splitter_val.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")
        
        # --- TOP CONTROLS (FLEX SCROLL) ---
        self.scroll_val = FlexScrollArea()
        
        h_ctrl = QHBoxLayout()
        h_ctrl.setSpacing(16); h_ctrl.setContentsMargins(0,0,0,0)
        
        # 1. Dataset Input
        grp1 = CardWidget("1. Dataset Masukan (Model & Ground Truth)")
        g1 = QFormLayout()
        g1.setHorizontalSpacing(16); g1.setVerticalSpacing(12)
        
        self.btn_v_nc = ModernButton("📂 D-Waves Output (.nc)", "outline")
        self.btn_v_nc.clicked.connect(lambda: self.load_file('val_nc'))
        self.lbl_v_nc = QLabel("Kosong"); self.lbl_v_nc.setStyleSheet("color:#6B7280; font-weight:bold; font-size:11px; border:none;")
        
        self.btn_v_csv = ModernButton("📊 Observasi Stat (*.csv)", "outline")
        self.btn_v_csv.clicked.connect(lambda: self.load_file('val_csv'))
        self.lbl_v_csv = QLabel("Kosong"); self.lbl_v_csv.setStyleSheet("color:#6B7280; font-weight:bold; font-size:11px; border:none;")
        
        h_nc = QHBoxLayout(); h_nc.addWidget(self.btn_v_nc); h_nc.addWidget(self.lbl_v_nc)
        h_csv = QHBoxLayout(); h_csv.addWidget(self.btn_v_csv); h_csv.addWidget(self.lbl_v_csv)
        
        g1.addRow(h_nc); g1.addRow(h_csv)
        
        self.cmb_v_var = QComboBox()
        self.cmb_v_var.addItems(['Hsig (Tinggi Gelombang)', 'Tp (Periode Puncak)'])
        self.cmb_v_var.setStyleSheet("background-color: #1F2227; border: 1px solid #3A3F4A; border-radius: 6px; padding: 6px; color: white;")
        g1.addRow(QLabel("Target Validasi:", styleSheet=LABEL_STYLE), self.cmb_v_var)
        
        grp1.add_layout(g1)
        h_ctrl.addWidget(grp1, stretch=5)
        
        # 2. Lokasi Observasi
        grp2 = CardWidget("2. Lokasi Stasiun WG & Sync")
        g2 = QFormLayout()
        g2.setHorizontalSpacing(16); g2.setVerticalSpacing(12)
        
        info_val = QLabel("Engine menggunakan KD-Tree Spatial Search ($O(\\log N)$) untuk presisi ekstraksi dan `merge_asof` untuk Time Sync.")
        info_val.setStyleSheet("color:#9CA3AF; font-size:11px; line-height:1.4; border:none;")
        info_val.setWordWrap(True)
        g2.addRow(info_val)
        
        self.inp_wg_lat = QLineEdit(); self.inp_wg_lat.setPlaceholderText("-8.4412")
        self.inp_wg_lon = QLineEdit(); self.inp_wg_lon.setPlaceholderText("112.6841")
        self.inp_wg_lat.setStyleSheet("background-color: #1F2227; border: 1px solid #3A3F4A; border-radius: 6px; padding: 6px; color: white;")
        self.inp_wg_lon.setStyleSheet(self.inp_wg_lat.styleSheet())
        
        h_coord = QHBoxLayout()
        h_coord.addWidget(QLabel("Lat (Y):", styleSheet=LABEL_STYLE)); h_coord.addWidget(self.inp_wg_lat)
        h_coord.addWidget(QLabel("Lon (X):", styleSheet=LABEL_STYLE)); h_coord.addWidget(self.inp_wg_lon)
        g2.addRow(h_coord)
        
        self.btn_run_val = ModernButton("⚡ JALANKAN VALIDASI KINERJA", "primary")
        self.btn_run_val.clicked.connect(self.run_validation)
        g2.addRow(self.btn_run_val)
        
        grp2.add_layout(g2)
        h_ctrl.addWidget(grp2, stretch=5)
        
        self.scroll_val.add_layout(h_ctrl)
        splitter_val.addWidget(self.scroll_val)
        
        # --- BOTTOM: RESULTS DASHBOARD ---
        res_widget = QWidget()
        res_layout = QHBoxLayout(res_widget)
        res_layout.setContentsMargins(0, 0, 0, 0)
        res_layout.setSpacing(16)
        
        # Left: Statistical Metrics
        metrics_grp = QFrame()
        metrics_grp.setStyleSheet("background-color: transparent; border: none;")
        ml = QVBoxLayout(metrics_grp)
        ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(12)
        
        self.metrics_labels = {}
        for metric, color in [("RMSE (Error)", "#FC3F4D"), ("Bias (Selisih)", "#F7C159"), ("Pearson R² (Akurasi)", "#42E695")]:
            f = QFrame()
            f.setStyleSheet(f"background-color: #1F2227; border: 1px solid #3A3F4A; border-left: 4px solid {color}; border-radius: 8px; padding: 8px;")
            fl = QVBoxLayout(f); fl.setContentsMargins(10, 10, 10, 10)
            
            lbl_title = QLabel(metric); lbl_title.setStyleSheet("color:#9CA3AF; font-size:12px; font-weight:bold; border:none;")
            lbl_val = QLabel("—"); lbl_val.setStyleSheet(f"color:{color}; font-size:22px; font-weight:900; font-family:'Consolas'; border:none;")
            
            fl.addWidget(lbl_title); fl.addWidget(lbl_val)
            self.metrics_labels[metric.split(" ")[0]] = lbl_val
            ml.addWidget(f)
            
        ml.addStretch()
        res_layout.addWidget(metrics_grp, stretch=3)
        
        # Right: Matplotlib Plot Image
        plot_grp = QFrame()
        plot_grp.setStyleSheet("background-color: #1E2128; border: 1px solid #3A3F4A; border-radius: 12px;")
        pl = QVBoxLayout(plot_grp)
        pl.setContentsMargins(8, 8, 8, 8)
        
        self.lbl_val_plot = QLabel("Grafik Validasi HD (Academic Theme) akan muncul di sini.")
        self.lbl_val_plot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_val_plot.setStyleSheet("color: #5C637A; font-weight: 800; font-size:14px; background-color:#1E2128; border-radius:8px; border:2px dashed #3A3F4A;")
        pl.addWidget(self.lbl_val_plot)
        res_layout.addWidget(plot_grp, stretch=7)
        
        splitter_val.addWidget(res_widget)
        splitter_val.setSizes([200, 600])
        layout.addWidget(splitter_val)

    # --------------------------------------------------------------------------
    # SPATIAL ANIMATION LOGIC
    # --------------------------------------------------------------------------
    def load_file(self, target: str) -> None:
        if target in ['spatial_nc', 'val_nc']:
            p, _ = QFileDialog.getOpenFileName(self, "Pilih Output NetCDF", "", "NetCDF (*.nc)")
            if p: 
                if target == 'spatial_nc':
                    self.nc_file = os.path.abspath(p)
                    self.btn_nc.setText(f"📂 {os.path.basename(p)}")
                    self.btn_nc.setStyleSheet("color: #42E695; border-color: #42E695;")
                    
                    # Membaca dimensi waktu dari NetCDF untuk mengaktifkan Slider
                    if HAS_XARRAY:
                        try:
                            with xr.open_dataset(self.nc_file, engine='netcdf4') as ds:
                                time_len = len(ds['time'])
                                self.current_max_time = max(0, time_len - 1)
                                self.sld_time.setRange(0, self.current_max_time)
                                self.sld_time.setEnabled(True)
                                self.lbl_t_idx.setText(f"Idx: [ 0 / {self.current_max_time} ]")
                        except Exception as e:
                            QMessageBox.warning(self, "Warning", f"Gagal membaca index waktu NetCDF: {str(e)}")
                    
                else:
                    self.val_nc_file = os.path.abspath(p)
                    self.lbl_v_nc.setText("✓ " + os.path.basename(p))
                    self.lbl_v_nc.setStyleSheet("color: #42E695; border:none;")
        elif target == 'val_csv':
            p, _ = QFileDialog.getOpenFileName(self, "Pilih WaveSpectra Statistics", "", "CSV Data (*.csv)")
            if p:
                self.val_csv_file = os.path.abspath(p)
                self.lbl_v_csv.setText("✓ " + os.path.basename(p))
                self.lbl_v_csv.setStyleSheet("color: #42E695; border:none;")

    def on_slider_moved(self, val: int) -> None:
        self.lbl_t_idx.setText(f"Idx: [ {val} / {self.current_max_time} ]")

    def on_slider_released(self) -> None:
        self.trigger_render(self.sld_time.value())

    def trigger_render(self, time_idx: int) -> None:
        if not self.nc_file:
            QMessageBox.warning(self, "Validasi", "Harap unggah file NetCDF (.nc) terlebih dahulu.")
            return
            
        epsg = app_state.get('EPSG', '32749')
        var_name = self.cmb_var.currentText()
        out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))

        self.btn_ren.setEnabled(False)
        self.btn_ren.setText("⏳ MENG-RENDER OVERLAY HD...")

        self.anim_w = PostProcAnimationWorker(self.nc_file, var_name, time_idx, epsg, out_dir)
        self.anim_w.frame_signal.connect(self.apply_overlay)

        def on_finished(success: bool):
            self.btn_ren.setEnabled(True)
            self.btn_ren.setText("▶ RENDER FRAME")
            if not success:
                QMessageBox.warning(self, "Render Gagal", "Gagal merender TriContourf frame dari file NetCDF.")
            self.anim_w.deleteLater()

        self.anim_w.finished_signal.connect(on_finished)
        self.anim_w.start()

    def apply_overlay(self, data: dict) -> None:
        """Menyuntikkan Base64 PNG TriContourf Overlay ke WebEngine Leaflet."""
        b = data['bounds']
        
        js_code = f"""
            if(window.currentOverlay) {{ map.removeLayer(window.currentOverlay); }}
            var bounds = [[{b['S']}, {b['W']}], [{b['N']}, {b['E']}]];
            window.currentOverlay = L.imageOverlay('{data['base64_img']}', bounds, {{opacity: 0.85}}).addTo(map);
            map.fitBounds(bounds);
        """
        self.web_map.page().runJavaScript(js_code)
        
        self.lbl_t_str.setText(f"Waktu: {data['time_str']}")
        self.lbl_t_idx.setText(f"Idx: [ {self.sld_time.value()} / {self.current_max_time} ]")

    # --------------------------------------------------------------------------
    # VALIDATION DASHBOARD LOGIC (KD-TREE)
    # --------------------------------------------------------------------------
    def run_validation(self) -> None:
        if not self.val_nc_file or not self.val_csv_file:
            QMessageBox.critical(self, "Syarat Kurang", "Harap unggah file D-Waves NetCDF (.nc) dan WaveSpectra Statistics (.csv) terlebih dahulu.")
            return
            
        lat_str = self.inp_wg_lat.text()
        lon_str = self.inp_wg_lon.text()
        if not lat_str or not lon_str:
            QMessageBox.critical(self, "Syarat Kurang", "Koordinat Lat/Lon Wave Gauge wajib diisi.")
            return
            
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            QMessageBox.warning(self, "Tipe Data", "Koordinat harus berupa angka desimal.")
            return

        if hasattr(self, 'val_worker') and self.val_worker.isRunning():
            return

        self.btn_run_val.setEnabled(False)
        self.btn_run_val.setText("⏳ KD-TREE NEAREST NEIGHBOR EXTRACTION...")
        
        epsg = app_state.get('EPSG', '32749')
        out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))
        target_var = self.cmb_v_var.currentText()
        
        self.val_worker = ValidationWorker(self.val_nc_file, self.val_csv_file, target_var, lat, lon, epsg, out_dir)
        
        def display_results(res: dict):
            self.metrics_labels["RMSE"].setText(f"{res['rmse']:.3f}")
            bias_str = f"+{res['bias']:.3f}" if res['bias'] > 0 else f"{res['bias']:.3f}"
            self.metrics_labels["Bias"].setText(bias_str)
            self.metrics_labels["Pearson"].setText(f"{res['r2']:.3f}")
            
            img_path = res.get('plot_path')
            if img_path and os.path.exists(img_path):
                pixmap = QPixmap(img_path).scaled(self.lbl_val_plot.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_val_plot.setPixmap(pixmap)

        def on_finished(success: bool):
            self.btn_run_val.setEnabled(True)
            self.btn_run_val.setText("⚡ JALANKAN VALIDASI KINERJA")
            if success:
                QMessageBox.information(self, "Validasi Selesai", "Data berhasil disinkronisasi dan grafik validasi White Academic Theme telah di-render!")
            else:
                QMessageBox.warning(self, "Validasi Gagal", "Terjadi kesalahan saat menyelaraskan data Observasi dan Model.")
            self.val_worker.deleteLater()
            
        self.val_worker.result_signal.connect(display_results)
        self.val_worker.finished_signal.connect(on_finished)
        self.val_worker.start()
