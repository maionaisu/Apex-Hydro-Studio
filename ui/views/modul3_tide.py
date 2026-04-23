# ==============================================================================
# APEX NEXUS TIER-0: MODUL 3 - TIDAL HARMONIX SYNTHESIZER (UI VIEW)
# ==============================================================================
import os
import logging
import traceback
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QGridLayout, QLineEdit, QSplitter, QMessageBox, QFrame)
from PyQt6.QtCore import Qt

from workers.tide_worker import TideAnalyzerWorker, TideGeneratorWorker
from core.state_manager import app_state

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS (THE "GOLDEN" CSS FIX) ---
STYLE_GROUPBOX = """
    QGroupBox {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        margin-top: 10px;
        padding-top: 40px; /* Space lapang agar title duduk manis di dalam */
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
        top: 10px; /* Positif! Judul masuk ke dalam kotak */
        left: 12px;
    }
"""

STYLE_INPUTS = """
    QComboBox, QLineEdit {
        background-color: #0F172A;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 10px 14px;
        color: #F8FAFC;
        font-size: 13px;
        font-family: 'Consolas', 'Courier New', monospace; /* Monospace untuk angka agar rapi */
    }
    QComboBox:focus, QLineEdit:focus { border: 1px solid #F59E0B; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #1E293B;
        color: #F8FAFC;
        selection-background-color: #334155;
        border: 1px solid #475569;
        border-radius: 6px;
    }
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
    
    QPushButton#GreenBtn {
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #047857);
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 12px 16px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton#GreenBtn:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34D399, stop:1 #10B981); }
    QPushButton#GreenBtn:pressed { background-color: #064E3B; }
    QPushButton#GreenBtn:disabled { background-color: #334155; color: #94A3B8; }
"""

STYLE_BTN_OUTLINE = """
    QPushButton#OutlineBtn {
        background-color: transparent;
        color: #F8FAFC;
        border: 1px solid #64748B;
        border-radius: 8px;
        padding: 12px 16px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton#OutlineBtn:hover { background-color: #334155; border-color: #F59E0B; color: #F59E0B; }
"""

LABEL_STYLE = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 13px; }"


class Modul3Tide(QWidget):
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
        t = QLabel("Tidal Harmonix Synthesizer")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Ekstrak nilai konstanta harmonik murni (Least Squares) dari deret waktu pasang surut SRGI / Observasi Lapangan.")
        d.setStyleSheet("color: #94A3B8; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        # Splitter Layout Transparan
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 10px; }")

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
        self.btn_tide_f.clicked.connect(self.load_tide_file)
        g1.addRow(self.btn_tide_f)
        
        lbl_info = QLabel("Pastikan data memiliki baris header yang jelas\nuntuk waktu dan nilai elevasi (Z).")
        lbl_info.setStyleSheet("color: #64748B; font-size: 12px; font-style: italic;")
        g1.addRow("", lbl_info)
        
        self.tcmb_t = QComboBox()
        self.tcmb_z = QComboBox()
        
        l_t = QLabel("Kolom Waktu (T):"); l_t.setStyleSheet(LABEL_STYLE)
        l_z = QLabel("Kolom Elevasi (Z):"); l_z.setStyleSheet(LABEL_STYLE)
        
        g1.addRow(l_t, self.tcmb_t)
        g1.addRow(l_z, self.tcmb_z)
        
        g1.addRow("", QLabel("")) # Spacer
        
        self.btn_ext = QPushButton("⚡ Jalankan Kalkulasi LSHA")
        self.btn_ext.setObjectName("ExecuteBtn")
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
                lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold; border-bottom: 1px solid #334155; padding-bottom: 4px;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                g2.addWidget(lbl, 0, col)
        
        self.inp_tides = {}
        consts = ['M2', 'S2', 'N2', 'K1', 'O1', 'P1', 'SA', 'SSA']
        
        for i, k in enumerate(consts):
            row = (i // 2) + 1
            col_offset = (i % 2) * 4 # Jarak 4 kolom untuk grup sebelah kanan
            
            # Badge Konstanta
            lbl_k = QLabel(k)
            lbl_k.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 13px; background-color: #0F172A; padding: 6px 10px; border-radius: 6px; border: 1px solid #1E293B;")
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
        self.btn_gen = QPushButton("🌊 Tulis & Kunci Forcing Boundary (.bc)")
        self.btn_gen.setObjectName("GreenBtn")
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
        term_lbl.setStyleSheet("font-weight:900; color:#38BDF8; font-size: 14px;")
        bl.addWidget(term_lbl)
        
        self.log_tide = QTextEdit()
        self.log_tide.setReadOnly(True)
        self.log_tide.setStyleSheet("background-color: #020617; color: #10B981; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #1E293B; border-radius: 8px; padding: 10px;")
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
                    if i >= 50:
                        break
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
            QMessageBox.warning(self, "Validasi", "Muat dataset file terlebih dahulu.")
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
            self.btn_ext.setText("⚡ Jalankan Kalkulasi LSHA")
            for k, v in res.items():
                if k in self.inp_tides:
                    self.inp_tides[k][0].setText(f"{v['amp']:.4f}")
                    self.inp_tides[k][1].setText(f"{v['pha']:.2f}")
            self.tide_a.deleteLater()
                    
        self.tide_a.result_signal.connect(display_results)
        
        def on_error(status):
            if status != "SUCCESS":
                self.btn_ext.setEnabled(True)
                self.btn_ext.setText("⚡ Jalankan Kalkulasi LSHA")
                
        self.tide_a.finished_signal.connect(on_error)
        self.tide_a.start()

    def run_tide_generator(self) -> None:
        if hasattr(self, 'tide_gen') and self.tide_gen.isRunning(): return
        
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
        self.btn_gen.setText("⏳ Sedang Menulis Time-Series bc...")
        
        self.tide_gen = TideGeneratorWorker(c, out_dir)
        
        def save_state(path: str):
            self.btn_gen.setEnabled(True)
            self.btn_gen.setText("🌊 Tulis & Kunci Forcing Boundary (.bc)")
            if path and os.path.exists(path):
                app_state.update('tide_bc', path)
                self.log_tide.append("✅ Sinkronisasi LSHA Sukses. File `.bc` terkunci di Global State dan siap diintegrasikan di Modul 4.")
            self.tide_gen.deleteLater()
                
        self.tide_gen.finished_signal.connect(save_state)
        self.tide_gen.start()
