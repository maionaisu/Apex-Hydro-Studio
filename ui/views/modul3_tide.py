# ==============================================================================
# APEX NEXUS TIER-0: MODUL 3 - TIDAL HARMONIX SYNTHESIZER (UI VIEW)
# ==============================================================================
import os
import logging
import traceback
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QGridLayout, QLineEdit, QSplitter, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from workers.tide_worker import TideAnalyzerWorker, TideGeneratorWorker
from core.state_manager import app_state

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS (FINTECH SLATE ADAPTATION) ---
STYLE_GROUPBOX = """
    QGroupBox {
        background-color: #2D3139;
        border: 1px solid #3A3F4A;
        border-radius: 12px;
        margin-top: 15px;
        padding-top: 35px; /* Space lapang agar title duduk manis di dalam */
        font-weight: 800;
        color: #FFFFFF;
        font-size: 14px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 6px 16px;
        background-color: transparent;
        color: #8FC9DC;
        top: 8px; /* Positif! Judul masuk ke dalam kotak */
        left: 10px;
    }
"""

STYLE_INPUTS = """
    QComboBox, QLineEdit {
        background-color: #1F2227;
        border: 1px solid #3A3F4A;
        border-radius: 8px;
        padding: 10px 14px;
        color: #FFFFFF;
        font-size: 13px;
        font-family: 'Consolas', 'Courier New', monospace; /* Monospace untuk angka agar rapi */
    }
    QComboBox:focus, QLineEdit:focus { border: 1px solid #595FF7; background-color: #2D3139; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #2D3139;
        color: #FFFFFF;
        selection-background-color: #595FF7;
        border: 1px solid #3A3F4A;
        border-radius: 8px;
    }
"""

STYLE_BTN_PRIMARY = """
    QPushButton#PrimaryBtn {
        background-color: #595FF7;
        color: #FFFFFF;
        border: none;
        border-radius: 10px;
        padding: 14px 16px;
        font-weight: 900;
        font-size: 14px;
    }
    QPushButton#PrimaryBtn:hover { background-color: #7176F8; }
    QPushButton#PrimaryBtn:disabled { background-color: #3A3F4A; color: #6B7280; }
"""

STYLE_BTN_OUTLINE = """
    QPushButton#OutlineBtn {
        background-color: transparent;
        color: #8FC9DC;
        border: 1px solid #3A3F4A;
        border-radius: 8px;
        padding: 12px 16px;
        font-weight: 800;
        font-size: 13px;
    }
    QPushButton#OutlineBtn:hover { background-color: rgba(143, 201, 220, 0.1); border-color: #8FC9DC; }
"""

LABEL_STYLE = "QLabel { color: #9CA3AF; font-weight: bold; font-size: 13px; }"


class Modul3Tide(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_BTN_PRIMARY} {STYLE_BTN_OUTLINE}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER (FINTECH STYLE) ---
        head = QVBoxLayout()
        t = QLabel("Tidal Harmonix Synthesizer")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Ekstraksi konstanta harmonik (Least Squares) dan generasi Boundary Condition (Astronomic) untuk simulasi kontinyu D-FLOW.")
        d.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        # Splitter Layout Transparan
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")

        # --- 1. MIDDLE SEGMENT (CONTROLS) ---
        ctrl_widget = QWidget()
        ctrl = QHBoxLayout(ctrl_widget)
        ctrl.setContentsMargins(0, 10, 0, 10)
        ctrl.setSpacing(25)

        # KIRI: LSHA Control
        c1 = QVBoxLayout()
        grp1 = QGroupBox("1. Data Parser & Inversi LSHA")
        
        g1 = QFormLayout(grp1)
        g1.setHorizontalSpacing(20)
        g1.setVerticalSpacing(18)
        
        self.btn_tide_f = QPushButton("📂 Unggah File Observasi (.csv / .txt)")
        self.btn_tide_f.setObjectName("OutlineBtn")
        self.btn_tide_f.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_tide_f.clicked.connect(self.load_tide_file)
        g1.addRow(self.btn_tide_f)
        
        lbl_info = QLabel("Pastikan data memiliki baris header yang jelas\nuntuk waktu dan nilai elevasi air (Z).")
        lbl_info.setStyleSheet("color: #6B7280; font-size: 12px; font-style: italic;")
        g1.addRow("", lbl_info)
        
        self.tcmb_t = QComboBox()
        self.tcmb_z = QComboBox()
        
        l_t = QLabel("Kolom Waktu (T):"); l_t.setStyleSheet(LABEL_STYLE)
        l_z = QLabel("Kolom Elevasi (Z):"); l_z.setStyleSheet(LABEL_STYLE)
        
        g1.addRow(l_t, self.tcmb_t)
        g1.addRow(l_z, self.tcmb_z)
        
        g1.addRow("", QLabel("")) # Spacer
        
        self.btn_ext = QPushButton("⚡ JALANKAN KALKULASI LSHA")
        self.btn_ext.setObjectName("PrimaryBtn")
        self.btn_ext.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_ext.clicked.connect(self.run_tide_analyzer)
        g1.addRow(self.btn_ext)
        
        c1.addWidget(grp1)
        c1.addStretch()
        ctrl.addLayout(c1, stretch=4)

        # KANAN: Output Editing & Dashboard
        c2 = QVBoxLayout()
        grp2 = QGroupBox("2. Parameter Harmonik (Hasil / Manual Override)")
        g2_layout = QVBoxLayout(grp2)
        g2_layout.setSpacing(15)
        
        # Grid Kustom untuk Dashboard Konstanta
        g2 = QGridLayout()
        g2.setHorizontalSpacing(15)
        g2.setVerticalSpacing(12)
        
        # Header Kolom Grid
        headers = ["Konstanta", "Amp (m)", "Phase (°)", "    ", "Konstanta", "Amp (m)", "Phase (°)"]
        for col, text in enumerate(headers):
            if text.strip():
                lbl = QLabel(text)
                lbl.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: bold; border-bottom: 1px solid #3A3F4A; padding-bottom: 6px;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                g2.addWidget(lbl, 0, col)
        
        self.inp_tides = {}
        consts = ['M2', 'S2', 'N2', 'K1', 'O1', 'P1', 'SA', 'SSA']
        
        for i, k in enumerate(consts):
            row = (i // 2) + 1
            col_offset = (i % 2) * 4 # Jarak 4 kolom untuk grup sebelah kanan
            
            # Badge Konstanta
            lbl_k = QLabel(k)
            lbl_k.setStyleSheet("color: #8FC9DC; font-weight: bold; font-size: 13px; background-color: #1F2227; padding: 6px 10px; border-radius: 6px; border: 1px solid #3A3F4A;")
            lbl_k.setAlignment(Qt.AlignmentFlag.AlignCenter)
            g2.addWidget(lbl_k, row, col_offset)
            
            # Input Amplitudo
            amp = QLineEdit()
            amp.setPlaceholderText("0.0000")
            amp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Input Phase
            pha = QLineEdit()
            pha.setPlaceholderText("0.00")
            pha.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.inp_tides[k] = [amp, pha]
            g2.addWidget(amp, row, col_offset + 1)
            g2.addWidget(pha, row, col_offset + 2)
            
            # Spacer kolom tengah
            if col_offset == 0:
                spacer = QLabel("")
                spacer.setFixedWidth(20)
                g2.addWidget(spacer, row, 3)

        g2_layout.addLayout(g2)
        c2.addWidget(grp2)
        
        # Tombol Ekspor
        self.btn_gen = QPushButton("🌊 TULIS & KUNCI FORCING BOUNDARY (.bc)")
        self.btn_gen.setObjectName("PrimaryBtn")
        self.btn_gen.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_gen.clicked.connect(self.run_tide_generator)
        c2.addWidget(self.btn_gen)
        c2.addStretch()
        
        ctrl.addLayout(c2, stretch=6)
        splitter.addWidget(ctrl_widget)

        # --- 2. BOTTOM SEGMENT (LOG CONSOLE) ---
        bot_wrap = QWidget()
        bl = QVBoxLayout(bot_wrap)
        bl.setContentsMargins(0, 10, 0, 0)
        
        term_lbl = QLabel("Terminal Kalkulasi (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#8FC9DC; font-size: 14px;")
        bl.addWidget(term_lbl)
        
        self.log_tide = QTextEdit()
        self.log_tide.setReadOnly(True)
        self.log_tide.setStyleSheet("background-color: #1E2128; color: #42E695; font-family: Consolas, monospace; font-size: 13px; border: 1px solid #3A3F4A; border-radius: 8px; padding: 12px;")
        bl.addWidget(self.log_tide)
        
        splitter.addWidget(bot_wrap)
        
        # Proporsi: Controls 65%, Log 35%
        splitter.setSizes([450, 200])
        main_layout.addWidget(splitter)

    def load_tide_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Buka Pasut Observasi", "", "Text/CSV (*.txt *.csv)")
        if not p: return
        
        try:
            # Lazy check untuk headers yang tertanam di bawah info stasiun
            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                skip = 0
                for i, l in enumerate(f):
                    if i >= 50: break
                    if any(k in l.lower() for k in ['z(m)', 'rad1', 'water', 'date', 'time', 'elev']):
                        skip = i
                        break

            separator = r'\s{2,}|\t' if p.endswith('.txt') else ','
            self.tide_df = pd.read_csv(p, skiprows=skip, sep=separator, engine='python')
            
            cols = list(self.tide_df.columns)
            self.tcmb_t.clear()
            self.tcmb_z.clear()
            self.tcmb_t.addItems(cols)
            self.tcmb_z.addItems(cols)
            
            for c in cols:
                cl = str(c).lower()
                if 'time' in cl or 'date' in cl or 'waktu' in cl: self.tcmb_t.setCurrentText(c)
                if 'z' in cl or 'water' in cl or 'elev' in cl or 'val' in cl: self.tcmb_z.setCurrentText(c)
            
            self.log_tide.append(f"▶ File observasi pasut aktif: {os.path.basename(p)}")
        except Exception as e:
            logger.error(f"Gagal mem-parsing DataFrame pasut: {e}")
            self.log_tide.append(f"❌ Gagal mem-parsing file observasi: {e}")
            QMessageBox.critical(self, "I/O Error", f"Gagal membaca dataset:\n{e}")

    def run_tide_analyzer(self) -> None:
        if hasattr(self, 'tide_a') and self.tide_a.isRunning():
            QMessageBox.warning(self, "Konflik", "Sistem sedang mengkalkulasi matriks LSHA. Harap tunggu.")
            return

        if not hasattr(self, 'tide_df') or self.tide_df is None: 
            QMessageBox.warning(self, "Validasi", "Muat dataset observasi terlebih dahulu.")
            return
            
        col_t = self.tcmb_t.currentText()
        col_z = self.tcmb_z.currentText()
        
        if not col_t or not col_z: return
        
        self.btn_ext.setEnabled(False)
        self.btn_ext.setText("⏳ Sedang Mengekstrak Komponen...")
        
        self.tide_a = TideAnalyzerWorker(self.tide_df, col_t, col_z)
        self.tide_a.log_signal.connect(self.log_tide.append)
        
        def display_results(res: dict):
            self.btn_ext.setEnabled(True)
            self.btn_ext.setText("⚡ JALANKAN KALKULASI LSHA")
            for k, v in res.items():
                if k in self.inp_tides:
                    self.inp_tides[k][0].setText(f"{v['amp']:.4f}")
                    self.inp_tides[k][1].setText(f"{v['pha']:.2f}")
            self.tide_a.deleteLater()
                    
        self.tide_a.result_signal.connect(display_results)
        
        def on_error(status):
            if status != "SUCCESS":
                self.btn_ext.setEnabled(True)
                self.btn_ext.setText("⚡ JALANKAN KALKULASI LSHA")
                
        self.tide_a.finished_signal.connect(on_error)
        self.tide_a.start()

    def run_tide_generator(self) -> None:
        if hasattr(self, 'tide_gen') and self.tide_gen.isRunning(): return
        
        # [HARDENING FATAL SYNC]: Mengambil rentang waktu D-FLOW dari State Manager Modul 1
        t_start = app_state.get('sim_start_time')
        t_end = app_state.get('sim_end_time')
        
        if not t_start or not t_end:
            QMessageBox.critical(
                self, "Fatal Time Desync", 
                "Batas waktu simulasi (Start/End) belum di-set pada Global State.\n\n"
                "Silakan kembali ke 'Modul 1: ERA5 Synthesizer', pilih rentang waktu, lalu ekstrak/kunci datanya agar pasut ini sinkron dengan gelombang."
            )
            return

        # Build dictionary from input forms
        c = {}
        for k, v in self.inp_tides.items():
            try:
                amp = float(v[0].text() or 0)
                pha = float(v[1].text() or 0)
                c[k] = {'amp': amp, 'pha': pha}
            except ValueError:
                c[k] = {'amp': 0.0, 'pha': 0.0}
                
        out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_FM_Model_Final'))
        os.makedirs(out_dir, exist_ok=True)
        
        self.btn_gen.setEnabled(False)
        self.btn_gen.setText("⏳ Menulis File Boundary (.bc)...")
        
        self.log_tide.append(f"[SYNC] Merender Pasang Surut dari {t_start} hingga {t_end}")
        
        # [NOTE]: Jika workers/tide_worker.py belum di-update untuk menerima t_start & t_end, 
        # Anda wajib memperbaruinya agar file .bc memiliki rentang yang pas.
        self.tide_gen = TideGeneratorWorker(c, out_dir, t_start, t_end)
        
        def save_state(path: str):
            self.btn_gen.setEnabled(True)
            self.btn_gen.setText("🌊 TULIS & KUNCI FORCING BOUNDARY (.bc)")
            if path and os.path.exists(path):
                app_state.update('tide_bc', path)
                self.log_tide.append(f"✅ Sinkronisasi LSHA Sukses. File `.bc` (Astronomic) terkunci ke Global State.")
            self.tide_gen.deleteLater()
                
        self.tide_gen.finished_signal.connect(save_state)
        self.tide_gen.start()
