# ==============================================================================
# APEX NEXUS TIER-0: MODUL 2 - SPATIAL SEDIMENT & MANGROVE (UI VIEW)
# ==============================================================================
import os
import gc
import logging
import traceback
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QCheckBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QSplitter, QTabWidget, QFrame, QMessageBox, QSpinBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from workers.sediment_worker import SedimentWorker
from core.state_manager import app_state

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS (THE "GOLDEN" CSS FIX) ---
STYLE_GROUPBOX = """
    QGroupBox {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        margin-top: 10px;
        padding-top: 40px; 
        font-weight: bold;
        color: #F1F5F9;
        font-size: 14px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 6px 15px;
        background-color: #0F172A;
        border-radius: 8px;
        color: #F59E0B;
        top: 10px; 
        left: 12px;
    }
"""

STYLE_INPUTS = """
    QComboBox, QSpinBox {
        background-color: #0F172A;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 10px 14px; 
        color: #F8FAFC;
        font-size: 13px;
        min-width: 150px;
    }
    QComboBox:focus, QSpinBox:focus { border: 1px solid #F59E0B; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #1E293B;
        color: #F8FAFC;
        selection-background-color: #334155;
        border: 1px solid #475569;
        border-radius: 6px;
    }
    QSpinBox::up-button, QSpinBox::down-button {
        background-color: #334155;
        border-radius: 2px;
        width: 16px;
    }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #F59E0B; }
    
    QCheckBox { color: #CBD5E1; font-size: 13px; font-weight: bold; }
    QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #475569; background: #0F172A; }
    QCheckBox::indicator:checked { background: #F59E0B; border: 1px solid #D97706; }
"""

STYLE_BTN_PRIMARY = """
    QPushButton#ExecuteBtn {
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F59E0B, stop:1 #D97706);
        color: #022C22;
        border: none;
        border-radius: 8px;
        padding: 12px 16px;
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
        padding: 12px 16px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #334155; border-color: #F59E0B; color: #F59E0B; }
    
    QPushButton#GreenBtn:hover { background-color: #064E3B; border-color: #10B981; color: #10B981; }
    QPushButton#PurpleBtn:hover { background-color: #4C1D95; border-color: #8B5CF6; color: #A78BFA; }
"""

class Modul2Sediment(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_data = {
            'sediment': {'df': None, 'file': None},
            'mangrove': {'df': None, 'file': None},
            'submerged': {'df': None, 'file': None}
        }
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
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 10px; }")

        # --- 1. TOP WIDGET (VISUALIZATION - MASSIVE SIZE) ---
        self.lbl_sed_viz = QLabel("Plot Spasial (Heatmap) akan di-render dalam mode resolusi tinggi di sini.")
        self.lbl_sed_viz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sed_viz.setStyleSheet("border: 2px dashed #334155; background-color:#020617; border-radius: 12px; color: #64748B; font-weight: bold; font-size: 16px;")
        
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: none; background: transparent;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(self.lbl_sed_viz)
        splitter.addWidget(top_wrap)

        # --- 2. MIDDLE WIDGET (CONTROLS TABS) ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; border-radius: 12px; background: #1E293B; }
            QTabBar::tab { background: #0F172A; color: #94A3B8; padding: 12px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; font-weight: bold;}
            QTabBar::tab:selected { background: #1E293B; color: #F59E0B; border-bottom: 3px solid #F59E0B;}
        """)
        
        self.tab_sediment = QWidget()
        self.build_tab_ui(self.tab_sediment, 'sediment', "📂 Load Survei Sedimen (.csv/.xlsx)", True)
        self.tabs.addTab(self.tab_sediment, "1. Sedimen (Nikuradse)")

        self.tab_mangrove = QWidget()
        self.build_tab_ui(self.tab_mangrove, 'mangrove', "🌲 Load Vegetasi Mangrove (.csv/.xlsx)", False)
        self.tabs.addTab(self.tab_mangrove, "2. Mangrove (Trachytope)")

        self.tab_submerged = QWidget()
        self.build_tab_ui(self.tab_submerged, 'submerged', "🪸 Load Terumbu Karang/Lamun (.csv/.xlsx)", False)
        self.tabs.addTab(self.tab_submerged, "3. Submerged Ecosystem")

        splitter.addWidget(self.tabs)

        # --- 3. BOTTOM WIDGET (LOG CONSOLE) ---
        bot_wrap = QWidget()
        bl = QVBoxLayout(bot_wrap)
        bl.setContentsMargins(0, 10, 0, 0)
        
        term_lbl = QLabel("Terminal Spasial (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#38BDF8; font-size: 14px;")
        bl.addWidget(term_lbl)
        
        self.log_sed = QTextEdit()
        self.log_sed.setReadOnly(True)
        self.log_sed.setStyleSheet("background-color: #020617; color: #10B981; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #1E293B; border-radius: 8px; padding: 10px;")
        bl.addWidget(self.log_sed)
        
        splitter.addWidget(bot_wrap)
        
        splitter.setSizes([600, 350, 100])
        main_layout.addWidget(splitter)

    def build_tab_ui(self, parent_widget: QWidget, mode_type: str, btn_text: str, show_ks: bool) -> None:
        layout = QHBoxLayout(parent_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(25)
        
        # Col 1: Dataset Loader
        c1 = QVBoxLayout()
        grp1 = QGroupBox("A. Dataset Survei Lapangan")
        g1 = QVBoxLayout(grp1)
        g1.setSpacing(15)
        
        btn_load = QPushButton(btn_text)
        if mode_type == 'mangrove': btn_load.setObjectName("GreenBtn")
        elif mode_type == 'submerged': btn_load.setObjectName("PurpleBtn")
        else: btn_load.setObjectName("OutlineBtn")
            
        btn_load.clicked.connect(lambda checked, m=mode_type: self.load_file(m))
        g1.addWidget(btn_load)
        
        lbl_info = QLabel("Format: Tabel dengan X (Longitude), Y (Latitude), dan Kolom Target (Z / D50 / Densitas).")
        lbl_info.setStyleSheet("color: #94A3B8; font-size: 13px; line-height: 1.4;")
        lbl_info.setWordWrap(True)
        g1.addWidget(lbl_info)
        g1.addStretch()
        
        c1.addWidget(grp1)
        layout.addLayout(c1, stretch=4)
        
        # Col 2: Mapper Configuration
        c2 = QVBoxLayout()
        grp2 = QGroupBox("B. Konfigurasi Pemetaan Spasial")
        
        g2 = QFormLayout(grp2)
        g2.setHorizontalSpacing(20) 
        g2.setVerticalSpacing(16)   
        
        label_style = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 13px; }"
        
        cmb_sheet = QComboBox()
        cmb_sheet.setEnabled(False)
        cmb_sheet.addItem("Membutuhkan File Excel...")
        
        spn_header = QSpinBox()
        spn_header.setRange(0, 50)
        spn_header.setValue(0)
        spn_header.setToolTip("Jika kolom 'Unnamed' muncul, naikkan angka ini untuk mencari baris judul (Header) yang tepat.")
        
        cmb_x = QComboBox()
        cmb_y = QComboBox()
        cmb_val = QComboBox()
        
        l_sheet = QLabel("Pilih Sheet (Excel):"); l_sheet.setStyleSheet(label_style)
        l_hdr = QLabel("Baris Header (0-idx):"); l_hdr.setStyleSheet(label_style)
        l_x = QLabel("Kolom X (Lon):"); l_x.setStyleSheet(label_style)
        l_y = QLabel("Kolom Y (Lat):"); l_y.setStyleSheet(label_style)
        l_z = QLabel("Kolom Target:"); l_z.setStyleSheet(label_style)
        
        g2.addRow(l_sheet, cmb_sheet)
        g2.addRow(l_hdr, spn_header)
        
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setStyleSheet("background-color: #334155;")
        g2.addRow(line)
        
        g2.addRow(l_x, cmb_x)
        g2.addRow(l_y, cmb_y)
        g2.addRow(l_z, cmb_val)
        
        chk_ks = QCheckBox("Transformasi Otomatis D50 -> Nikuradse (ks = 2.5D)")
        if show_ks:
            chk_ks.setChecked(True)
            g2.addRow("", chk_ks)
        else:
            chk_ks.setVisible(False)
            
        btn_run = QPushButton("⚡ Eksekusi Grid Spasial & Render Heatmap")
        btn_run.setObjectName("ExecuteBtn")
        btn_run.clicked.connect(lambda checked, m=mode_type: self.run_interpolation(m))
        g2.addRow(btn_run)
        
        c2.addWidget(grp2)
        layout.addLayout(c2, stretch=6)
        
        setattr(self, f"cmb_sheet_{mode_type}", cmb_sheet)
        setattr(self, f"spn_header_{mode_type}", spn_header)
        setattr(self, f"cmb_x_{mode_type}", cmb_x)
        setattr(self, f"cmb_y_{mode_type}", cmb_y)
        setattr(self, f"cmb_v_{mode_type}", cmb_val)
        setattr(self, f"chk_ks_{mode_type}", chk_ks)
        setattr(self, f"btn_run_{mode_type}", btn_run)
        
        cmb_sheet.currentTextChanged.connect(lambda t, m=mode_type: self.on_sheet_or_header_changed(m))
        spn_header.valueChanged.connect(lambda v, m=mode_type: self.on_sheet_or_header_changed(m))

    def load_file(self, mode_type: str) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Buka Data Spasial (Survei Lapangan)", "", "Data Spreadsheet (*.csv *.xlsx)")
        if not p: return
        
        self.tab_data[mode_type]['file'] = p
        cmb_sheet = getattr(self, f"cmb_sheet_{mode_type}")
        spn_header = getattr(self, f"spn_header_{mode_type}")
        
        spn_header.blockSignals(True)
        spn_header.setValue(0)
        spn_header.blockSignals(False)
        
        try:
            if p.endswith('.xlsx'):
                # [HARDENING]: Memastikan File Handle ditutup dengan context manager
                with pd.ExcelFile(p) as xl:
                    sheet_names = xl.sheet_names
                
                cmb_sheet.blockSignals(True)
                cmb_sheet.clear()
                cmb_sheet.addItems(sheet_names)
                cmb_sheet.setEnabled(True)
                cmb_sheet.blockSignals(False)
                
                self.load_sheet_data(mode_type, sheet_names[0], 0)
            else:
                cmb_sheet.blockSignals(True)
                cmb_sheet.clear()
                cmb_sheet.addItem("CSV File Aktif")
                cmb_sheet.setEnabled(False)
                cmb_sheet.blockSignals(False)
                
                self.load_sheet_data(mode_type, None, 0)
                
        except Exception as e:
            logger.error(f"[FATAL] Gagal menginisiasi file: {str(e)}\n{traceback.format_exc()}")
            self.log_sed.append(f"❌ Gagal memuat file untuk {mode_type}: {str(e)}")
            QMessageBox.critical(self, "I/O Error", f"Gagal membaca file spreadsheet: {str(e)}")

    def on_sheet_or_header_changed(self, mode_type: str) -> None:
        cmb_sheet = getattr(self, f"cmb_sheet_{mode_type}")
        spn_header = getattr(self, f"spn_header_{mode_type}")
        
        sheet = cmb_sheet.currentText()
        header_row = spn_header.value()
        self.load_sheet_data(mode_type, sheet, header_row)

    def load_sheet_data(self, mode_type: str, sheet_name: str, header_row: int) -> None:
        p = self.tab_data[mode_type].get('file')
        if not p: return
        
        # [MEMORY MANAGEMENT]: Clear old DataFrame to prevent OOM
        if self.tab_data[mode_type]['df'] is not None:
            del self.tab_data[mode_type]['df']
            gc.collect()
        
        try:
            if p.endswith('.xlsx') and sheet_name and sheet_name != "CSV File Aktif":
                df = pd.read_excel(p, sheet_name=sheet_name, header=header_row)
            else:
                df = pd.read_csv(p, header=header_row)
                
            self.tab_data[mode_type]['df'] = df
            cols = [str(c) for c in df.columns]
            
            cmb_x = getattr(self, f"cmb_x_{mode_type}")
            cmb_y = getattr(self, f"cmb_y_{mode_type}")
            cmb_v = getattr(self, f"cmb_v_{mode_type}")
            
            cmb_x.blockSignals(True); cmb_y.blockSignals(True); cmb_v.blockSignals(True)
            cmb_x.clear(); cmb_y.clear(); cmb_v.clear()
            
            cmb_x.addItems(cols)
            cmb_y.addItems(cols)
            cmb_v.addItems(cols)
            
            cmb_x.blockSignals(False); cmb_y.blockSignals(False); cmb_v.blockSignals(False)
            
            # Auto-Detect AI
            for c in cols:
                cl = str(c).lower()
                if 'lon' in cl or 'x' in cl or 'easting' in cl: cmb_x.setCurrentText(c)
                if 'lat' in cl or 'y' in cl or 'northing' in cl: cmb_y.setCurrentText(c)
                if any(k in cl for k in ['d50', 'sedimen', 'val', 'friction', 'dens', 'z', 'target']): 
                    cmb_v.setCurrentText(c)
                
            sht_log = f"Sheet '{sheet_name}'" if sheet_name else "CSV"
            self.log_sed.append(f"[SYSTEM] {sht_log} (Header: {header_row}) ter-load. Baris Data: {len(df)}")
            
        except pd.errors.EmptyDataError:
            self.log_sed.append(f"❌ Error: File kosong atau sheet '{sheet_name}' tidak memiliki data.")
        except Exception as e:
            logger.warning(f"Gagal memuat subset data: {e}")

    def run_interpolation(self, mode_type: str) -> None:
        if hasattr(self, 'sed_w') and self.sed_w.isRunning():
            QMessageBox.warning(self, "Konflik", "Proses interpolasi sedang berjalan. Harap tunggu.")
            return

        df = self.tab_data[mode_type]['df']
        if df is None:
            QMessageBox.warning(self, "Validasi Gagal", f"Harap muat dataset (.csv/.xlsx) untuk mode '{mode_type}'.")
            return
            
        cmb_x = getattr(self, f"cmb_x_{mode_type}")
        cmb_y = getattr(self, f"cmb_y_{mode_type}")
        cmb_v = getattr(self, f"cmb_v_{mode_type}")
        chk_ks = getattr(self, f"chk_ks_{mode_type}")
        btn_run = getattr(self, f"btn_run_{mode_type}")
        
        col_x = cmb_x.currentText()
        col_y = cmb_y.currentText()
        col_val = cmb_v.currentText()
        
        if 'unnamed' in col_x.lower() or 'unnamed' in col_y.lower():
            QMessageBox.warning(self, "Kolom Invalid", "Terdeteksi kolom 'Unnamed'. Naikkan angka 'Baris Header (0-idx)'.")
            return
            
        if not col_x or not col_y or not col_val:
            QMessageBox.critical(self, "Validasi Gagal", "Konfigurasi kolom X, Y, dan Target tidak lengkap.")
            return
        
        btn_run.setEnabled(False)
        btn_run.setText("⏳ Sedang Mengekstrak Matriks Spasial...")
        
        # Mengunci EPSG 32749 Sesuai Skripsi CMC Malang Selatan
        epsg_code = app_state.get('EPSG', '32749')
        
        self.sed_w = SedimentWorker(
            df=df,
            col_x=col_x,
            col_y=col_y,
            col_val=col_val,
            convert_ks=chk_ks.isChecked() if chk_ks.isVisible() else False,
            mode_type=mode_type,
            epsg=epsg_code
        )
        
        self.sed_w.log_signal.connect(self.log_sed.append)
        
        def update_img(img_path: str):
            if img_path and os.path.exists(img_path):
                pixmap = QPixmap(img_path).scaled(self.lbl_sed_viz.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_sed_viz.setPixmap(pixmap)
                
        self.sed_w.plot_signal.connect(update_img)
        
        def on_finished(xyz_path: str):
            btn_run.setEnabled(True)
            btn_run.setText("⚡ Eksekusi Grid Spasial & Render Heatmap")
            
            if xyz_path and os.path.exists(xyz_path):
                app_state.update('sediment_xyz', xyz_path)
                self.log_sed.append(f"[STATE] File forcing `{os.path.basename(xyz_path)}` berhasil dikunci ke Memori Global.")
                
            self.sed_w.deleteLater()
            
        self.sed_w.finished_signal.connect(on_finished)
        self.sed_w.start()
