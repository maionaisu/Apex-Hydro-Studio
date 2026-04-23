# ==============================================================================
# APEX NEXUS TIER-0: MODUL 2 - SPATIAL SEDIMENT & MANGROVE (UI VIEW)
# ==============================================================================
import os
import logging
import traceback
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QCheckBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QSplitter, QTabWidget, QFrame, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from workers.sediment_worker import SedimentWorker
from core.state_manager import app_state

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS (REVOLUT / GRADIENTA INFLUENCE) ---
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

STYLE_INPUTS = """
    QComboBox {
        background-color: #0F172A;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 8px 12px;
        color: #F8FAFC;
        font-size: 13px;
    }
    QComboBox:focus { border: 1px solid #F59E0B; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #1E293B;
        color: #F8FAFC;
        selection-background-color: #334155;
        border: 1px solid #475569;
        border-radius: 6px;
    }
    QCheckBox { color: #CBD5E1; font-size: 13px; }
    QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #475569; background: #0F172A; }
    QCheckBox::indicator:checked { background: #F59E0B; border: 1px solid #D97706; }
"""

STYLE_BTN_PRIMARY = """
    QPushButton#ExecuteBtn {
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F59E0B, stop:1 #D97706);
        color: #022C22;
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton#ExecuteBtn:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FCD34D, stop:1 #F59E0B); }
    QPushButton#ExecuteBtn:pressed { background-color: #B45309; }
    QPushButton#ExecuteBtn:disabled { background-color: #334155; color: #94A3B8; }
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
    QPushButton:hover { background-color: #334155; border-color: #F59E0B; color: #F59E0B; }
    
    QPushButton#GreenBtn:hover { background-color: #064E3B; border-color: #10B981; color: #10B981; }
    QPushButton#PurpleBtn:hover { background-color: #4C1D95; border-color: #8B5CF6; color: #A78BFA; }
"""


class Modul2Sediment(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_BTN_PRIMARY} {STYLE_BTN_OUTLINE}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER (REVOLUT STYLE) ---
        head = QVBoxLayout()
        t = QLabel("Spatial Sediments & Coastal Friction")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Pemetaan densitas spasial Trachytope untuk Mangrove, Lamun, Karang, dan perhitungan kekasaran dasar laut (Nikuradse).")
        d.setStyleSheet("color: #94A3B8; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("""
            QSplitter::handle { background-color: #334155; height: 2px; margin: 4px 0px; }
        """)

        # --- 1. TOP WIDGET (VISUALIZATION) ---
        self.lbl_sed_viz = QLabel("Plot Spasial (Heatmap) akan muncul di sini.")
        self.lbl_sed_viz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sed_viz.setStyleSheet("border: 1px dashed #475569; background-color:#020617; border-radius: 8px; color: #64748B; font-weight: bold;")
        
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: 1px solid #1E293B; border-radius: 12px; background: #000;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(1, 1, 1, 1)
        tl.addWidget(self.lbl_sed_viz)
        splitter.addWidget(top_wrap)

        # --- 2. MIDDLE WIDGET (CONTROLS TABS) ---
        self.tabs = QTabWidget()
        self.tabs.setMaximumHeight(350)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; border-radius: 8px; background: #1E293B; }
            QTabBar::tab { background: #0F172A; color: #94A3B8; padding: 10px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;}
            QTabBar::tab:selected { background: #1E293B; color: #F59E0B; font-weight: bold; border-bottom: 2px solid #F59E0B;}
        """)
        
        # Panel 1: Sediment Dasar
        self.tab_sediment = QWidget()
        self.build_tab_ui(self.tab_sediment, 'sediment', "📂 Load Spasial Sedimen Dasar Laut (.csv/.xlsx)", True)
        self.tabs.addTab(self.tab_sediment, "1. Sedimen Dasar (Manning/Nikuradse)")

        # Panel 2: Mangrove (Baptist)
        self.tab_mangrove = QWidget()
        self.build_tab_ui(self.tab_mangrove, 'mangrove', "🌲 Load Node Vegetasi Mangrove (.csv/.xlsx)", False)
        self.tabs.addTab(self.tab_mangrove, "2. Mangrove (Trachytope Baptist)")

        # Panel 3: Submerged Vegetation
        self.tab_submerged = QWidget()
        self.build_tab_ui(self.tab_submerged, 'submerged', "🪸 Load Survei Ekosistem Bawah Laut (.csv/.xlsx)", False)
        self.tabs.addTab(self.tab_submerged, "3. Ekosistem (Karang/Lamun)")

        splitter.addWidget(self.tabs)

        # --- 3. BOTTOM WIDGET (LOG CONSOLE) ---
        bot_wrap = QWidget()
        bl = QVBoxLayout(bot_wrap)
        bl.setContentsMargins(0, 10, 0, 0)
        
        term_lbl = QLabel("Terminal Interpolasi (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#38BDF8; font-size: 14px;")
        bl.addWidget(term_lbl)
        
        self.log_sed = QTextEdit()
        self.log_sed.setReadOnly(True)
        self.log_sed.setStyleSheet("background-color: #020617; color: #10B981; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #1E293B; border-radius: 6px; padding: 8px;")
        bl.addWidget(self.log_sed)
        
        splitter.addWidget(bot_wrap)
        splitter.setSizes([400, 300, 200])
        main_layout.addWidget(splitter)
        
        # Data State Store untuk masing-masing tab
        self.tab_data = {
            'sediment': {'df': None},
            'mangrove': {'df': None},
            'submerged': {'df': None}
        }

    def build_tab_ui(self, parent_widget: QWidget, mode_type: str, btn_text: str, show_ks: bool) -> None:
        layout = QHBoxLayout(parent_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)
        
        # Col 1: Dataset Loader
        c1 = QVBoxLayout()
        grp1 = QGroupBox("A. Dataset Survei")
        g1 = QVBoxLayout(grp1)
        g1.setSpacing(12)
        
        btn_load = QPushButton(btn_text)
        if mode_type == 'mangrove': btn_load.setObjectName("GreenBtn")
        elif mode_type == 'submerged': btn_load.setObjectName("PurpleBtn")
        else: btn_load.setObjectName("OutlineBtn")
            
        btn_load.clicked.connect(lambda checked, m=mode_type: self.load_file(m))
        g1.addWidget(btn_load)
        
        lbl_info = QLabel("Pilih file CSV atau Excel yang mengandung kolom koordinat X (Longitude), Y (Latitude), dan nilai densitas/D50.")
        lbl_info.setStyleSheet("color: #64748B; font-size: 12px;")
        lbl_info.setWordWrap(True)
        g1.addWidget(lbl_info)
        g1.addStretch()
        
        c1.addWidget(grp1)
        layout.addLayout(c1, stretch=4)
        
        # Col 2: Mapper Configuration
        c2 = QVBoxLayout()
        grp2 = QGroupBox("B. Konfigurasi Pemetaan Spasial")
        g2 = QFormLayout(grp2)
        g2.setSpacing(14)
        
        cmb_x = QComboBox()
        cmb_y = QComboBox()
        cmb_val = QComboBox()
        
        g2.addRow("Kolom X (Lon):", cmb_x)
        g2.addRow("Kolom Y (Lat):", cmb_y)
        g2.addRow("Kolom Target:", cmb_val)
        
        chk_ks = QCheckBox("Transformasi D50 ke Nikuradse (ks = 2.5D)")
        if show_ks:
            chk_ks.setChecked(True)
            g2.addRow("", chk_ks)
        else:
            chk_ks.setVisible(False)
            
        btn_run = QPushButton("⚡ Eksekusi Interpolasi Delaunay & Heatmap")
        btn_run.setObjectName("ExecuteBtn")
        btn_run.clicked.connect(lambda checked, m=mode_type: self.run_interpolation(m))
        g2.addRow(btn_run)
        
        c2.addWidget(grp2)
        layout.addLayout(c2, stretch=6)
        
        # Dinamis Atribut Mapping (Menyimpan referensi QComboBox agar mudah ditarik di run_interpolation)
        setattr(self, f"cmb_x_{mode_type}", cmb_x)
        setattr(self, f"cmb_y_{mode_type}", cmb_y)
        setattr(self, f"cmb_v_{mode_type}", cmb_val)
        setattr(self, f"chk_ks_{mode_type}", chk_ks)
        setattr(self, f"btn_run_{mode_type}", btn_run)

    def load_file(self, mode_type: str) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Buka Data Spasial (Survei Lapangan)", "", "Data Spreadsheet (*.csv *.xlsx)")
        if not p: return
        
        try:
            # Membaca data ke RAM. (Operasi I/O ringan, cukup aman di Main Thread)
            df = pd.read_excel(p) if p.endswith('.xlsx') else pd.read_csv(p)
            self.tab_data[mode_type]['df'] = df
            cols = list(df.columns)
            
            cmb_x = getattr(self, f"cmb_x_{mode_type}")
            cmb_y = getattr(self, f"cmb_y_{mode_type}")
            cmb_v = getattr(self, f"cmb_v_{mode_type}")
            
            cmb_x.clear()
            cmb_y.clear()
            cmb_v.clear()
            
            cmb_x.addItems(cols)
            cmb_y.addItems(cols)
            cmb_v.addItems(cols)
            
            # Smart Auto-select berdasar heuristik nama kolom
            for c in cols:
                cl = str(c).lower()
                if 'lon' in cl or 'x' in cl or 'easting' in cl: cmb_x.setCurrentText(c)
                if 'lat' in cl or 'y' in cl or 'northing' in cl: cmb_y.setCurrentText(c)
                if 'd50' in cl or 'sedimen' in cl or 'val' in cl or 'friction' in cl or 'dens' in cl or 'z' in cl: 
                    cmb_v.setCurrentText(c)
                
            self.log_sed.append(f"[SYSTEM] Dataset {os.path.basename(p)} berhasil diload. Total data: {len(df)} titik.")
            
        except Exception as e:
            logger.error(f"[FATAL] Gagal membaca dataset spasial: {str(e)}\n{traceback.format_exc()}")
            self.log_sed.append(f"❌ Gagal memuat file untuk {mode_type}: {str(e)}")
            QMessageBox.critical(self, "I/O Error", f"Gagal membaca file spreadsheet: {str(e)}")

    def run_interpolation(self, mode_type: str) -> None:
        # 1. Thread Concurrency Guard (Seksi 5.B Requirement)
        if hasattr(self, 'sed_w') and self.sed_w.isRunning():
            QMessageBox.warning(self, "Konflik", "Proses interpolasi sedang berjalan. Harap tunggu.")
            return

        df = self.tab_data[mode_type]['df']
        
        # 2. Validation Guards
        if df is None:
            QMessageBox.warning(self, "Validasi Gagal", f"Harap muat dataset (.csv/.xlsx) untuk mode '{mode_type}' terlebih dahulu.")
            return
            
        cmb_x = getattr(self, f"cmb_x_{mode_type}")
        cmb_y = getattr(self, f"cmb_y_{mode_type}")
        cmb_v = getattr(self, f"cmb_v_{mode_type}")
        chk_ks = getattr(self, f"chk_ks_{mode_type}")
        btn_run = getattr(self, f"btn_run_{mode_type}")
        
        col_x = cmb_x.currentText()
        col_y = cmb_y.currentText()
        col_val = cmb_v.currentText()
        
        if not col_x or not col_y or not col_val:
            QMessageBox.critical(self, "Validasi Gagal", "Konfigurasi kolom X, Y, dan Target tidak lengkap.")
            return
        
        # 3. Lock UI and Delegate to Worker
        btn_run.setEnabled(False)
        btn_run.setText("⏳ Sedang Mengekstrak Matriks Spasial...")
        
        self.sed_w = SedimentWorker(
            df=df,
            col_x=col_x,
            col_y=col_y,
            col_val=col_val,
            convert_ks=chk_ks.isChecked() if chk_ks.isVisible() else False,
            mode_type=mode_type,
            epsg=app_state.get('EPSG', '32749')
        )
        
        # 4. Signal Wiring
        self.sed_w.log_signal.connect(self.log_sed.append)
        
        def update_img(img_path: str):
            if img_path and os.path.exists(img_path):
                pixmap = QPixmap(img_path).scaled(self.lbl_sed_viz.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_sed_viz.setPixmap(pixmap)
                
        self.sed_w.plot_signal.connect(update_img)
        
        def on_finished(xyz_path: str):
            btn_run.setEnabled(True)
            btn_run.setText("⚡ Eksekusi Interpolasi Delaunay & Heatmap")
            
            if xyz_path and os.path.exists(xyz_path):
                # Lock target friction layer inside global memory state
                app_state.update('sediment_xyz', xyz_path)
                self.log_sed.append(f"[STATE] File forcing `.xyz` berhasil dikunci ke Memori Global.")
                
            self.sed_w.deleteLater() # Garbage Collection
            
        self.sed_w.finished_signal.connect(on_finished)
        self.sed_w.start()
