# ==============================================================================
# APEX NEXUS TIER-0: MODUL 6 - POST-PROCESSING & VALIDATION DASHBOARD
# ==============================================================================
import os
import json
import logging
import traceback
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QScrollArea, QSlider, QFrame,
                             QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget, 
                             QHeaderView, QSplitter, QGridLayout, QLineEdit)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QCursor

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

# --- ENTERPRISE QSS STYLESHEETS (FINTECH SLATE ADAPTATION) ---
STYLE_GROUPBOX = """
    QGroupBox { background-color: #2D3139; border: 1px solid #3A3F4A; border-radius: 12px; margin-top: 15px; padding-top: 35px; font-weight: 800; color: #FFFFFF; font-size: 14px; }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 6px 16px; background-color: transparent; color: #8FC9DC; top: 8px; left: 10px; }
"""
STYLE_INPUTS = """
    QLineEdit, QComboBox { background-color: #1F2227; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 14px; color: #FFFFFF; font-size: 13px; font-family: 'Consolas', monospace; }
    QLineEdit:focus, QComboBox:focus { border: 1px solid #595FF7; background-color: #2D3139; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { background-color: #2D3139; color: #FFFFFF; selection-background-color: #595FF7; border: 1px solid #3A3F4A; border-radius: 8px; }
"""
STYLE_TABLE = """
    QTableWidget { background-color: #1F2227; color: #FFFFFF; gridline-color: #3A3F4A; border: 1px solid #3A3F4A; border-radius: 8px; font-family: 'Consolas', monospace; }
    QHeaderView::section { background-color: #2D3139; color: #8FC9DC; padding: 8px; font-weight: 800; border: none; border-bottom: 1px solid #3A3F4A; border-right: 1px solid #3A3F4A; }
"""
STYLE_MAIN_TABS = """
    QTabWidget::pane { border: 1px solid #3A3F4A; border-radius: 12px; background: #1E2128; }
    QTabBar::tab { background: #1F2227; color: #9CA3AF; padding: 12px 24px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 6px; font-weight: 900; font-size: 14px; }
    QTabBar::tab:selected { background: #2D3139; color: #595FF7; border-bottom: 3px solid #595FF7; }
    QTabBar::tab:hover:!selected { background: #2D3139; color: #FFFFFF; }
"""
STYLE_BTNS = """
    QPushButton#PrimaryBtn { background-color: #595FF7; color: #FFFFFF; border: none; border-radius: 10px; padding: 14px 16px; font-weight: 900; font-size: 14px; }
    QPushButton#PrimaryBtn:hover { background-color: #7176F8; }
    QPushButton#PrimaryBtn:disabled { background-color: #3A3F4A; color: #6B7280; }
    QPushButton#OutlineBtn { background-color: transparent; color: #8FC9DC; border: 1px solid #3A3F4A; border-radius: 8px; padding: 12px 16px; font-weight: 800; font-size: 13px; }
    QPushButton#OutlineBtn:hover { background-color: rgba(143, 201, 220, 0.1); border-color: #8FC9DC; }
"""
STYLE_SLIDER = """
    QSlider::groove:horizontal { border-radius: 4px; height: 10px; background-color: #1F2227; border: 1px solid #3A3F4A; }
    QSlider::handle:horizontal { background-color: #FFFFFF; border: 3px solid #595FF7; width: 20px; height: 20px; margin: -6px 0; border-radius: 10px; }
    QSlider::sub-page:horizontal { background-color: #595FF7; border-radius: 4px; }
"""

LABEL_STYLE = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 13px; }"


class Modul6PostProc(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.nc_file = ""
        self.val_nc_file = ""
        self.val_csv_file = ""
        self.current_max_time = 0
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_TABLE} {STYLE_BTNS} {STYLE_SLIDER} {STYLE_MAIN_TABS}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER ---
        head = QVBoxLayout()
        t = QLabel("Post-Processing & Validation Dashboard")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Render animasi spasial perambatan gelombang (NetCDF) dan Validasi statistik Point-Extraction (Wave Spectra).")
        d.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        # ==============================================================================
        # MASTER TABS: SPATIAL ANIMATION vs POINT VALIDATION
        # ==============================================================================
        self.master_tabs = QTabWidget()
        
        # ------------------------------------------------------------------------------
        # TAB 1: SPATIAL ANIMATION (LEAFLET HEATMAP)
        # ------------------------------------------------------------------------------
        self.tab_spatial = QWidget()
        self.build_spatial_tab()
        self.master_tabs.addTab(self.tab_spatial, "🗺️ Animasi Spasial Dinamis")
        
        # ------------------------------------------------------------------------------
        # TAB 2: VALIDATION DASHBOARD (WAVE GAUGE VS MODEL)
        # ------------------------------------------------------------------------------
        self.tab_validation = QWidget()
        self.build_validation_tab()
        self.master_tabs.addTab(self.tab_validation, "📊 Validasi Wave Spectra (Model vs Obs)")
        
        main_layout.addWidget(self.master_tabs, stretch=1)

    def build_spatial_tab(self) -> None:
        """Membangun antarmuka untuk animasi Heatmap spasial."""
        layout = QVBoxLayout(self.tab_spatial)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")
        
        # --- TOP: MAP & AOI ---
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Kiri: Map
        map_frame = QFrame()
        map_frame.setStyleSheet("border: 1px solid #3A3F4A; border-radius: 12px; background: #000; overflow: hidden;")
        ml = QVBoxLayout(map_frame); ml.setContentsMargins(1, 1, 1, 1)
        self.web_map = QWebEngineView()
        self.web_map.setHtml(get_leaflet_html("postproc"))
        ml.addWidget(self.web_map)
        top_layout.addWidget(map_frame, stretch=7)
        
        # Kanan: AOI Subset
        aoi_grp = QGroupBox("Area Subset & Render Target")
        al = QVBoxLayout(aoi_grp)
        al.addWidget(QLabel("Tentukan batas area (Zoom) render spesifik:", styleSheet=LABEL_STYLE))
        btn_shp = QPushButton("📂 Muat SHP/LDB Batas Render")
        btn_shp.setObjectName("OutlineBtn")
        btn_shp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_shp.clicked.connect(self.import_aoi_shapefile)
        al.addWidget(btn_shp)
        
        self.tbl_bbox = QTableWidget(4, 1)
        self.tbl_bbox.setVerticalHeaderLabels(["North", "South", "East", "West"])
        self.tbl_bbox.horizontalHeader().setVisible(False)
        self.tbl_bbox.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for j in range(4): 
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_bbox.setItem(j, 0, item)
        self.tbl_bbox.itemChanged.connect(self.manual_update_bbox)
        al.addWidget(self.tbl_bbox)
        al.addStretch()
        top_layout.addWidget(aoi_grp, stretch=3)
        splitter.addWidget(top_widget)
        
        # --- BOTTOM: CONTROLS & TIMELINE ---
        bot_widget = QWidget()
        bot_layout = QHBoxLayout(bot_widget)
        bot_layout.setContentsMargins(0, 10, 0, 0)
        
        # File & Var
        c1 = QVBoxLayout()
        grp1 = QGroupBox("1. Konfigurasi Visual")
        g1 = QFormLayout(grp1); g1.setVerticalSpacing(16)
        
        self.btn_nc = QPushButton("📂 Load Model NetCDF (.nc)")
        self.btn_nc.setObjectName("OutlineBtn")
        self.btn_nc.clicked.connect(lambda: self.load_file('spatial_nc'))
        g1.addRow(self.btn_nc)
        
        self.cmb_var = QComboBox()
        self.cmb_var.addItems(['mesh2d_s1', 'Hsig', 'Tp', 'Wdir', 'mesh2d_ucx', 'mesh2d_taus'])
        g1.addRow(QLabel("Variabel: ", styleSheet=LABEL_STYLE), self.cmb_var)
        
        self.btn_ren = QPushButton("▶ RENDER FRAME")
        self.btn_ren.setObjectName("PrimaryBtn")
        self.btn_ren.clicked.connect(lambda: self.trigger_render(self.sld_time.value()))
        g1.addRow(self.btn_ren)
        c1.addWidget(grp1); c1.addStretch()
        bot_layout.addLayout(c1, stretch=3)
        
        # Scrubber
        c2 = QVBoxLayout()
        grp2 = QGroupBox("2. Spatio-Temporal Scrubber")
        g2 = QVBoxLayout(grp2); g2.setSpacing(16)
        
        h_info = QHBoxLayout()
        self.lbl_t_idx = QLabel("Idx: [ 0 ]"); self.lbl_t_idx.setStyleSheet("color:#38BDF8; font-weight:900; font-size:14px; font-family:'Consolas';")
        self.lbl_t_str = QLabel("Waktu: -"); self.lbl_t_str.setStyleSheet("color:#42E695; font-weight:900; font-size:14px; font-family:'Consolas'; background-color:#1F2227; padding:6px 12px; border-radius:6px; border:1px solid #3A3F4A;")
        h_info.addWidget(self.lbl_t_idx); h_info.addStretch(); h_info.addWidget(self.lbl_t_str)
        g2.addLayout(h_info)
        
        self.sld_time = QSlider(Qt.Orientation.Horizontal)
        self.sld_time.setRange(0, 0); self.sld_time.setValue(0); self.sld_time.setEnabled(False)
        self.sld_time.valueChanged.connect(self.on_slider_moved)
        self.sld_time.sliderReleased.connect(self.on_slider_released)
        g2.addWidget(self.sld_time)
        c2.addWidget(grp2); c2.addStretch()
        bot_layout.addLayout(c2, stretch=7)
        
        splitter.addWidget(bot_widget)
        splitter.setSizes([600, 200])
        layout.addWidget(splitter)

    def build_validation_tab(self) -> None:
        """Membangun antarmuka untuk ekstraksi titik tunggal dan perbandingan (Model vs Observasi)."""
        layout = QVBoxLayout(self.tab_validation)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(20)
        
        # --- TOP CONTROLS ---
        top_ctrl = QHBoxLayout()
        top_ctrl.setSpacing(20)
        
        # 1. Dataset Input
        grp1 = QGroupBox("1. Dataset Masukan (Model & Ground Truth)")
        g1 = QFormLayout(grp1)
        g1.setHorizontalSpacing(16); g1.setVerticalSpacing(16)
        
        self.btn_v_nc = QPushButton("📂 D-Waves Output (.nc)")
        self.btn_v_nc.setObjectName("OutlineBtn")
        self.btn_v_nc.clicked.connect(lambda: self.load_file('val_nc'))
        self.lbl_v_nc = QLabel("Kosong"); self.lbl_v_nc.setStyleSheet("color:#6B7280; font-weight:bold; font-size:12px;")
        
        self.btn_v_csv = QPushButton("📊 WaveSpectra Stat (*_Statistics.csv)")
        self.btn_v_csv.setObjectName("OutlineBtn")
        self.btn_v_csv.clicked.connect(lambda: self.load_file('val_csv'))
        self.lbl_v_csv = QLabel("Kosong"); self.lbl_v_csv.setStyleSheet("color:#6B7280; font-weight:bold; font-size:12px;")
        
        h_nc = QHBoxLayout(); h_nc.addWidget(self.btn_v_nc); h_nc.addWidget(self.lbl_v_nc)
        h_csv = QHBoxLayout(); h_csv.addWidget(self.btn_v_csv); h_csv.addWidget(self.lbl_v_csv)
        
        g1.addRow(h_nc)
        g1.addRow(h_csv)
        
        self.cmb_v_var = QComboBox()
        self.cmb_v_var.addItems(['Hsig (Tinggi Gelombang)', 'Tp (Periode Puncak)'])
        g1.addRow(QLabel("Target Validasi:", styleSheet=LABEL_STYLE), self.cmb_v_var)
        top_ctrl.addWidget(grp1, stretch=5)
        
        # 2. Lokasi Observasi
        grp2 = QGroupBox("2. Lokasi Alat & Sinkronisasi")
        g2 = QFormLayout(grp2)
        g2.setHorizontalSpacing(16); g2.setVerticalSpacing(16)
        
        info_val = QLabel("Engine akan mencari Node NetCDF terdekat dengan koordinat ini, mengekstrak Time-Seriesnya, dan menyelaraskan (Interpolate) waktunya dengan CSV.")
        info_val.setStyleSheet("color:#9CA3AF; font-size:12px; line-height:1.4;")
        info_val.setWordWrap(True)
        g2.addRow(info_val)
        
        self.inp_wg_lat = QLineEdit(); self.inp_wg_lat.setPlaceholderText("-8.4412")
        self.inp_wg_lon = QLineEdit(); self.inp_wg_lon.setPlaceholderText("112.6841")
        h_coord = QHBoxLayout()
        h_coord.addWidget(QLabel("Lat (Y):", styleSheet=LABEL_STYLE)); h_coord.addWidget(self.inp_wg_lat)
        h_coord.addWidget(QLabel("Lon (X):", styleSheet=LABEL_STYLE)); h_coord.addWidget(self.inp_wg_lon)
        g2.addRow(h_coord)
        
        self.btn_run_val = QPushButton("⚡ JALANKAN VALIDASI & EKSTRAKSI")
        self.btn_run_val.setObjectName("PrimaryBtn")
        self.btn_run_val.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_run_val.clicked.connect(self.run_validation)
        g2.addRow(self.btn_run_val)
        top_ctrl.addWidget(grp2, stretch=5)
        
        layout.addLayout(top_ctrl)
        
        # --- BOTTOM: RESULTS DASHBOARD ---
        splitter_val = QSplitter(Qt.Orientation.Horizontal)
        splitter_val.setStyleSheet("QSplitter::handle { background-color: transparent; width: 12px; }")
        
        # Left: Statistical Metrics
        metrics_grp = QGroupBox("Matriks Kinerja Validasi")
        ml = QVBoxLayout(metrics_grp)
        ml.setSpacing(15)
        
        self.metrics_labels = {}
        for metric, color in [("RMSE (Error)", "#FC3F4D"), ("Bias (Selisih)", "#F7C159"), ("Pearson R² (Korelasi)", "#42E695")]:
            f = QFrame()
            f.setStyleSheet(f"background-color: #1F2227; border: 1px solid #3A3F4A; border-left: 4px solid {color}; border-radius: 8px; padding: 12px;")
            fl = QVBoxLayout(f); fl.setContentsMargins(10, 10, 10, 10)
            
            lbl_title = QLabel(metric); lbl_title.setStyleSheet("color:#9CA3AF; font-size:12px; font-weight:bold; border:none;")
            lbl_val = QLabel("—"); lbl_val.setStyleSheet(f"color:{color}; font-size:20px; font-weight:900; font-family:'Consolas'; border:none;")
            
            fl.addWidget(lbl_title); fl.addWidget(lbl_val)
            self.metrics_labels[metric.split(" ")[0]] = lbl_val
            ml.addWidget(f)
            
        ml.addStretch()
        splitter_val.addWidget(metrics_grp)
        
        # Right: Matplotlib Plot Image
        plot_grp = QGroupBox("Grafik Time-Series & Scatter Plot")
        pl = QVBoxLayout(plot_grp)
        self.lbl_val_plot = QLabel("Grafik Validasi akan muncul di sini.\n(Garis Model vs Titik Observasi)")
        self.lbl_val_plot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_val_plot.setStyleSheet("color: #5C637A; font-weight: 800; font-size:14px; background-color:#1E2128; border-radius:8px; border:2px dashed #3A3F4A;")
        pl.addWidget(self.lbl_val_plot)
        splitter_val.addWidget(plot_grp)
        
        splitter_val.setSizes([300, 700])
        layout.addWidget(splitter_val, stretch=1)

    # --------------------------------------------------------------------------
    # SPATIAL ANIMATION LOGIC (Existing)
    # --------------------------------------------------------------------------
    def load_file(self, target: str) -> None:
        if target in ['spatial_nc', 'val_nc']:
            p, _ = QFileDialog.getOpenFileName(self, "Pilih Output NetCDF", "", "NetCDF (*.nc)")
            if p: 
                if target == 'spatial_nc':
                    self.nc_file = os.path.abspath(p)
                    self.btn_nc.setText(f"📂 {os.path.basename(p)}")
                    self.btn_nc.setStyleSheet("color: #42E695; border-color: #42E695;")
                else:
                    self.val_nc_file = os.path.abspath(p)
                    self.lbl_v_nc.setText("✓ " + os.path.basename(p))
                    self.lbl_v_nc.setStyleSheet("color: #42E695;")
        elif target == 'val_csv':
            p, _ = QFileDialog.getOpenFileName(self, "Pilih WaveSpectra Statistics", "", "CSV Data (*.csv)")
            if p:
                self.val_csv_file = os.path.abspath(p)
                self.lbl_v_csv.setText("✓ " + os.path.basename(p))
                self.lbl_v_csv.setStyleSheet("color: #42E695;")

    def import_aoi_shapefile(self) -> None:
        pass # Existing logic...
    def manual_update_bbox(self) -> None:
        pass # Existing logic...
    def on_slider_moved(self, val: int) -> None:
        self.lbl_t_idx.setText(f"Idx: [ {val} / {self.current_max_time} ]")
    def on_slider_released(self) -> None:
        self.trigger_render(self.sld_time.value())
    def trigger_render(self, time_idx: int) -> None:
        pass # Existing worker delegation...
    def apply_overlay(self, data: dict) -> None:
        pass # Existing JS injection...

    # --------------------------------------------------------------------------
    # VALIDATION DASHBOARD LOGIC (New Features)
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
        self.btn_run_val.setText("⏳ MENGEKSTRAK NETCDF & SINKRONISASI WAKTU...")
        
        epsg = app_state.get('EPSG', '32749')
        out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))
        target_var = self.cmb_v_var.currentText()
        
        # Import ValidationWorker directly here to avoid circular imports if any
        from workers.postproc_worker import ValidationWorker
        
        self.val_worker = ValidationWorker(self.val_nc_file, self.val_csv_file, target_var, lat, lon, epsg, out_dir)
        
        def display_results(res: dict):
            # Update Mathematical Matrices
            self.metrics_labels["RMSE"].setText(f"{res['rmse']:.3f}")
            # Format Bias with +/- sign
            bias_str = f"+{res['bias']:.3f}" if res['bias'] > 0 else f"{res['bias']:.3f}"
            self.metrics_labels["Bias"].setText(bias_str)
            self.metrics_labels["Pearson"].setText(f"{res['r2']:.3f}")
            
            # Show Plot Image on Canvas
            img_path = res.get('plot_path')
            if img_path and os.path.exists(img_path):
                pixmap = QPixmap(img_path).scaled(self.lbl_val_plot.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_val_plot.setPixmap(pixmap)

        def on_finished(success: bool):
            self.btn_run_val.setEnabled(True)
            self.btn_run_val.setText("⚡ JALANKAN VALIDASI & EKSTRAKSI")
            if success:
                QMessageBox.information(self, "Validasi Selesai", "Data berhasil disinkronisasi dan grafik validasi telah di-render!")
            self.val_worker.deleteLater()
            
        self.val_worker.result_signal.connect(display_results)
        self.val_worker.finished_signal.connect(on_finished)
        self.val_worker.start()
