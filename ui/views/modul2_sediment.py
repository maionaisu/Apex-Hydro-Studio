# ==============================================================================
# APEX NEXUS TIER-0: MODUL 2 - SPATIAL SEDIMENT & MANGROVE (FLUID UI)
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

# --- ENTERPRISE QSS STYLESHEETS (FINTECH SLATE FLUID ADAPTATION) ---
STYLE_GROUPBOX = """
    QGroupBox { background-color: #2D3139; border: 1px solid #3A3F4A; border-radius: 12px; margin-top: 15px; padding-top: 35px; font-weight: 800; color: #FFFFFF; font-size: 14px; }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 6px 16px; background-color: transparent; color: #8FC9DC; top: 8px; left: 10px; }
"""
STYLE_INPUTS = """
    QLineEdit, QComboBox, QSpinBox { background-color: #1F2227; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 14px; color: #FFFFFF; font-size: 13px; font-family: 'Consolas', monospace; }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #595FF7; background-color: #2D3139; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { background-color: #2D3139; color: #FFFFFF; selection-background-color: #595FF7; border: 1px solid #3A3F4A; border-radius: 8px; }
    QSpinBox::up-button, QSpinBox::down-button { background-color: #3A3F4A; border-radius: 2px; width: 16px; }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #595FF7; }
    QCheckBox { color: #9CA3AF; font-size: 13px; font-weight: 800; }
    QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #3A3F4A; background: #1F2227; }
    QCheckBox::indicator:checked { background: #595FF7; border: 1px solid #7176F8; }
"""
STYLE_BTN_PRIMARY = """
    QPushButton#ExecuteBtn { background-color: #595FF7; color: #FFFFFF; border: none; border-radius: 10px; padding: 14px 16px; font-weight: 900; font-size: 14px; }
    QPushButton#ExecuteBtn:hover { background-color: #7176F8; }
    QPushButton#ExecuteBtn:disabled { background-color: #3A3F4A; color: #6B7280; }
"""
STYLE_BTN_OUTLINE = """
    QPushButton { background-color: transparent; color: #8FC9DC; border: 1px solid #3A3F4A; border-radius: 8px; padding: 12px 16px; font-weight: 800; }
    QPushButton:hover { background-color: rgba(143, 201, 220, 0.1); border-color: #8FC9DC; color: #8FC9DC; }
    
    QPushButton#GreenBtn { color: #42E695; border-color: #3A3F4A; }
    QPushButton#GreenBtn:hover { background-color: rgba(66, 230, 149, 0.1); border-color: #42E695; }
    
    QPushButton#PurpleBtn { background-color: transparent; color: #F7C159; border-color: #3A3F4A; }
    QPushButton#PurpleBtn:hover { background-color: rgba(247, 193, 89, 0.1); border-color: #F7C159; }
"""
STYLE_TABS = """
    QTabWidget::pane { border: 1px solid #3A3F4A; border-radius: 12px; background: #1E2128; }
    QTabBar::tab { background: #1F2227; color: #9CA3AF; padding: 12px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; font-weight: 800; }
    QTabBar::tab:selected { background: #2D3139; color: #8FC9DC; border-bottom: 3px solid #8FC9DC; }
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
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_BTN_PRIMARY} {STYLE_BTN_OUTLINE} {STYLE_TABS}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER ---
        head = QVBoxLayout()
        title_container = QFrame()
        title_container.setStyleSheet("background-color: #1E2128; border: 1px solid #3A3F4A; border-radius: 12px;")
        tc_layout = QVBoxLayout(title_container)
        tc_layout.setContentsMargins(20, 20, 20, 20)
        tc_layout.setSpacing(8)
        
        t = QLabel("Spatial Sediments & Coastal Friction")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px; border: none;")
        
        d = QLabel(
            "<div style='text-align: justify; line-height: 1.6;'>"
            "Sistem pemetaan tingkat lanjut untuk distribusi densitas spasial Trachytope pada vegetasi Mangrove, Lamun, "
            "dan Terumbu Karang. Modul ini mendukung algoritma <b>Ordinary Kriging</b> untuk interpolasi ekologi yang presisi "
            "dan otomatis mengonversi kekasaran dasar laut (D50) menuju sistem ekuivalen Nikuradse (ks)."
            "</div>"
        )
        d.setStyleSheet("color: #9CA3AF; font-size: 13px; border: none;")
        d.setWordWrap(True)
        
        tc_layout.addWidget(t)
        tc_layout.addWidget(d)
        head.addWidget(title_container)
        main_layout.addLayout(head)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setStyleSheet("QSplitter::handle { background-color: transparent; width: 12px; }")

        # ==============================================================================
        # KIRI: KONTROL TABS (FLEX-LIKE SIDEBAR)
        # ==============================================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        self.tab_sediment = QWidget()
        self.build_tab_ui(self.tab_sediment, 'sediment', "📂 Load Survei Sedimen (.csv/.xlsx)", True)
        self.tabs.addTab(self.tab_sediment, "1. Sedimen (Nikuradse)")

        self.tab_mangrove = QWidget()
        self.build_tab_ui(self.tab_mangrove, 'mangrove', "🌲 Load Vegetasi Mangrove", False)
        self.tabs.addTab(self.tab_mangrove, "2. Mangrove")

        self.tab_submerged = QWidget()
        self.build_tab_ui(self.tab_submerged, 'submerged', "🪸 Load Submerged (.csv)", False)
        self.tabs.addTab(self.tab_submerged, "3. Ekosistem Bawah Air")

        left_layout.addWidget(self.tabs)
        main_splitter.addWidget(left_widget)

        # ==============================================================================
        # KANAN: VISUALISASI & LOG TERMINAL (VERTICAL SPLITTER)
        # ==============================================================================
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setChildrenCollapsible(False)
        right_splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")
        
        self.lbl_sed_viz = QLabel("Plot Spasial (Heatmap) akan di-render di sini.")
        self.lbl_sed_viz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sed_viz.setStyleSheet("border: 2px dashed #3A3F4A; background-color:#1E2128; border-radius: 12px; color: #6B7280; font-weight: bold; font-size: 16px;")
        
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: none; background: transparent;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(self.lbl_sed_viz)
        right_splitter.addWidget(top_wrap)

        bot_wrap = QWidget()
        bl = QVBoxLayout(bot_wrap)
        bl.setContentsMargins(0, 0, 0, 0)
        
        term_lbl = QLabel("Terminal Spasial (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#8FC9DC; font-size: 14px;")
        bl.addWidget(term_lbl)
        
        self.log_sed = QTextEdit()
        self.log_sed.setReadOnly(True)
        self.log_sed.setStyleSheet("background-color: #020617; color: #10B981; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #1E293B; border-radius: 8px; padding: 12px;")
        bl.addWidget(self.log_sed)
        
        right_splitter.addWidget(bot_wrap)
        right_splitter.setSizes([600, 200]) 
        
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([450, 650])
        main_layout.addWidget(main_splitter)

    def build_tab_ui(self, parent_widget: QWidget, mode_type: str, btn_text: str, show_ks: bool) -> None:
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 1. Dataset Loader Card
        grp1 = QGroupBox("A. Dataset Survei Lapangan")
        g1 = QVBoxLayout(grp1)
        g1.setSpacing(15)
        
        btn_load = QPushButton(btn_text)
        if mode_type == 'mangrove': btn_load.setObjectName("GreenBtn")
        elif mode_type == 'submerged': btn_load.setObjectName("PurpleBtn")
        else: btn_load.setObjectName("OutlineBtn")
            
        btn_load.clicked.connect(lambda checked, m=mode_type: self.load_file(m))
        g1.addWidget(btn_load)
        
        lbl_info = QLabel("<div style='text-align: justify; line-height: 1.5;'>Format Input: Kolom X (Longitude), Y (Latitude), dan Kolom Target (Z / D50 / Kerapatan). Pastikan desimal menggunakan titik (.).</div>")
        lbl_info.setStyleSheet("color: #9CA3AF; font-size: 12px; border: none;")
        lbl_info.setWordWrap(True)
        g1.addWidget(lbl_info)
        
        layout.addWidget(grp1)
        
        # 2. Mapper Configuration Card
        grp2 = QGroupBox("B. Konfigurasi Pemetaan (Kriging/Delaunay)")
        g2 = QFormLayout(grp2)
        g2.setHorizontalSpacing(15) 
        g2.setVerticalSpacing(12)   
        
        label_style = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 12px; border: none; }"
        
        # [ENTERPRISE FIX]: Injeksi Algoritma Kriging
        cmb_method = QComboBox()
        cmb_method.addItems([
            "Ordinary Kriging (Spherical)",
            "Ordinary Kriging (Exponential)",
            "Ordinary Kriging (Gaussian)",
            "Delaunay Triangulation (Fast Linear)"
        ])
        
        cmb_sheet = QComboBox()
        cmb_sheet.setEnabled(False)
        cmb_sheet.addItem("File Excel...")
        
        spn_header = QSpinBox()
        spn_header.setRange(0, 50)
        spn_header.setValue(0)
        
        cmb_x = QComboBox()
        cmb_y = QComboBox()
        cmb_val = QComboBox()
        
        g2.addRow(QLabel("Pilih Sheet:", styleSheet=label_style), cmb_sheet)
        g2.addRow(QLabel("Baris Header:", styleSheet=label_style), spn_header)
        
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setStyleSheet("background-color: #3A3F4A;")
        g2.addRow(line)
        
        g2.addRow(QLabel("Kolom X (Lon):", styleSheet=label_style), cmb_x)
        g2.addRow(QLabel("Kolom Y (Lat):", styleSheet=label_style), cmb_y)
        g2.addRow(QLabel("Kolom Target:", styleSheet=label_style), cmb_val)
        
        line2 = QFrame(); line2.setFrameShape(QFrame.Shape.HLine); line2.setStyleSheet("background-color: #3A3F4A;")
        g2.addRow(line2)
        
        g2.addRow(QLabel("Metode Interpolasi:", styleSheet="color:#F7C159; font-weight:bold; font-size:12px; border:none;"), cmb_method)
        
        chk_ks = QCheckBox("Ubah Otomatis D50 -> ks (2.5D)")
        if show_ks:
            chk_ks.setChecked(True)
            g2.addRow("", chk_ks)
        else:
            chk_ks.setVisible(False)
            
        layout.addWidget(grp2)
        
        # 3. Execution Button
        btn_run = QPushButton("⚡ Eksekusi Matriks & Heatmap")
        btn_run.setObjectName("ExecuteBtn")
        btn_run.clicked.connect(lambda checked, m=mode_type: self.run_interpolation(m))
        layout.addWidget(btn_run)
        
        layout.addStretch()
        
        setattr(self, f"cmb_sheet_{mode_type}", cmb_sheet)
        setattr(self, f"spn_header_{mode_type}", spn_header)
        setattr(self, f"cmb_x_{mode_type}", cmb_x)
        setattr(self, f"cmb_y_{mode_type}", cmb_y)
        setattr(self, f"cmb_v_{mode_type}", cmb_val)
        setattr(self, f"cmb_method_{mode_type}", cmb_method) # Simpan reference Kriging
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
        cmb_method = getattr(self, f"cmb_method_{mode_type}")
        chk_ks = getattr(self, f"chk_ks_{mode_type}")
        btn_run = getattr(self, f"btn_run_{mode_type}")
        
        col_x = cmb_x.currentText()
        col_y = cmb_y.currentText()
        col_val = cmb_v.currentText()
        interp_method = cmb_method.currentText()
        
        if 'unnamed' in col_x.lower() or 'unnamed' in col_y.lower():
            QMessageBox.warning(self, "Kolom Invalid", "Terdeteksi kolom 'Unnamed'. Naikkan angka 'Baris Header (0-idx)'.")
            return
            
        if not col_x or not col_y or not col_val:
            QMessageBox.critical(self, "Validasi Gagal", "Konfigurasi kolom X, Y, dan Target tidak lengkap.")
            return
        
        btn_run.setEnabled(False)
        btn_run.setText("⏳ Sedang Mengekstrak Matriks Spasial...")
        
        epsg_code = app_state.get('EPSG', '32749')
        
        self.sed_w = SedimentWorker(
            df=df,
            col_x=col_x,
            col_y=col_y,
            col_val=col_val,
            convert_ks=chk_ks.isChecked() if chk_ks.isVisible() else False,
            mode_type=mode_type,
            epsg=epsg_code,
            interp_method=interp_method # Meneruskan metode Kriging ke Worker
        )
        
        self.sed_w.log_signal.connect(self.log_sed.append)
        
        def update_img(img_path: str):
            if img_path and os.path.exists(img_path):
                pixmap = QPixmap(img_path).scaled(self.lbl_sed_viz.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_sed_viz.setPixmap(pixmap)
                
        self.sed_w.plot_signal.connect(update_img)
        
        def on_finished(xyz_path: str):
            btn_run.setEnabled(True)
            btn_run.setText("⚡ Eksekusi Matriks & Heatmap")
            
            if xyz_path and os.path.exists(xyz_path):
                app_state.update('sediment_xyz', xyz_path)
                self.log_sed.append(f"[STATE] File forcing `{os.path.basename(xyz_path)}` berhasil dikunci ke Memori Global.")
                
            self.sed_w.deleteLater()
            
        self.sed_w.finished_signal.connect(on_finished)
        self.sed_w.start()
