# ==============================================================================
# APEX NEXUS TIER-0: MODUL 3 - TIDAL HARMONIX SYNTHESIZER (UI VIEW)
# ==============================================================================
import os
import logging
import traceback
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QComboBox, QLabel, QTextEdit, QFileDialog, 
                             QGridLayout, QLineEdit, QSplitter, QMessageBox, QFrame)
from PyQt6.QtCore import Qt

# Integrasi Enterprise Flexbox
from ui.components.core_widgets import FlexScrollArea, CardWidget, ModernButton
from workers.tide_worker import TideAnalyzerWorker, TideGeneratorWorker
from core.state_manager import app_state

logger = logging.getLogger(__name__)

class Modul3Tide(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
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
        
        t = QLabel("Tidal Harmonix Synthesizer")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px; border: none;")
        
        d = QLabel(
            "<div style='text-align: justify; line-height: 1.6;'>"
            "Ekstraksi konstanta harmonik (Least Squares Harmonic Analysis) dan generasi <b>Boundary Condition (Astronomic)</b> "
            "untuk simulasi kontinyu D-FLOW FM. Modul ini dilengkapi dengan <i>Rayleigh Criterion Guard</i> dan Z-Score Outlier Rejection."
            "</div>"
        )
        d.setStyleSheet("color: #9CA3AF; font-size: 13px; border: none;")
        d.setWordWrap(True)
        
        tc_layout.addWidget(t)
        tc_layout.addWidget(d)
        head.addWidget(title_container)
        main_layout.addLayout(head)

        # Splitter Transparan
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")

        # --- 1. TOP SEGMENT (FLEX SCROLL CONTROLS) ---
        # Membungkus kontrol ke dalam FlexScrollArea untuk mencegah "cemet"
        self.scroll_ctrl = FlexScrollArea()
        
        # Container horizontal untuk membagi panel kiri & kanan di dalam Scroll Area
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(20)

        # KIRI: LSHA Control
        c1 = QVBoxLayout()
        grp1 = CardWidget("1. Data Parser & Inversi LSHA")
        
        self.btn_tide_f = ModernButton("📂 Unggah File Observasi (.csv / .txt)", "outline")
        self.btn_tide_f.clicked.connect(self.load_tide_file)
        grp1.add_widget(self.btn_tide_f)
        
        lbl_info = QLabel("Pastikan data memiliki baris header yang jelas untuk waktu dan nilai elevasi air (Z).")
        lbl_info.setStyleSheet("color: #6B7280; font-size: 12px; font-style: italic;")
        lbl_info.setWordWrap(True)
        grp1.add_widget(lbl_info)
        
        g1 = QFormLayout()
        g1.setHorizontalSpacing(15); g1.setVerticalSpacing(12)
        
        self.tcmb_t = QComboBox()
        self.tcmb_z = QComboBox()
        
        label_style = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 12px; border: none; }"
        g1.addRow(QLabel("Kolom Waktu (T):", styleSheet=label_style), self.tcmb_t)
        g1.addRow(QLabel("Kolom Elevasi (Z):", styleSheet=label_style), self.tcmb_z)
        
        grp1.add_layout(g1)
        
        self.btn_ext = ModernButton("⚡ JALANKAN KALKULASI LSHA", "primary")
        self.btn_ext.clicked.connect(self.run_tide_analyzer)
        grp1.add_widget(self.btn_ext)
        
        c1.addWidget(grp1)
        c1.addStretch()
        h_layout.addLayout(c1, stretch=4)

        # KANAN: Output Editing & Dashboard
        c2 = QVBoxLayout()
        grp2 = CardWidget("2. Parameter Harmonik (Hasil / Manual Override)")
        
        # Grid Kustom untuk Dashboard Konstanta
        g2 = QGridLayout()
        g2.setHorizontalSpacing(15)
        g2.setVerticalSpacing(12)
        
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
            col_offset = (i % 2) * 4 
            
            lbl_k = QLabel(k)
            lbl_k.setStyleSheet("color: #8FC9DC; font-weight: bold; font-size: 13px; background-color: #1F2227; padding: 6px 10px; border-radius: 6px; border: 1px solid #3A3F4A;")
            lbl_k.setAlignment(Qt.AlignmentFlag.AlignCenter)
            g2.addWidget(lbl_k, row, col_offset)
            
            amp = QLineEdit()
            amp.setPlaceholderText("0.0000")
            amp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            pha = QLineEdit()
            pha.setPlaceholderText("0.00")
            pha.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.inp_tides[k] = [amp, pha]
            g2.addWidget(amp, row, col_offset + 1)
            g2.addWidget(pha, row, col_offset + 2)
            
            if col_offset == 0:
                spacer = QLabel("")
                spacer.setFixedWidth(20)
                g2.addWidget(spacer, row, 3)

        grp2.add_layout(g2)
        
        self.btn_gen = ModernButton("🌊 TULIS & KUNCI FORCING BOUNDARY (.bc)", "primary")
        self.btn_gen.clicked.connect(self.run_tide_generator)
        grp2.add_widget(self.btn_gen)
        
        c2.addWidget(grp2)
        c2.addStretch()
        h_layout.addLayout(c2, stretch=6)
        
        # Masukkan container horizontal ke dalam ScrollArea
        self.scroll_ctrl.add_layout(h_layout)
        self.scroll_ctrl.add_stretch()
        splitter.addWidget(self.scroll_ctrl)

        # --- 2. BOTTOM SEGMENT (LOG CONSOLE) ---
        bot_wrap = QWidget()
        bl = QVBoxLayout(bot_wrap)
        bl.setContentsMargins(0, 10, 0, 0)
        
        term_lbl = QLabel("Terminal Kalkulasi (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#8FC9DC; font-size: 14px;")
        bl.addWidget(term_lbl)
        
        self.log_tide = QTextEdit()
        self.log_tide.setReadOnly(True)
        self.log_tide.setObjectName("TerminalOutput")
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
                    if any(k in l.lower() for k in ['z(m)', 'rad1', 'water', 'date', 'time', 'elev', 'waktu']):
                        skip = i
                        break

            separator = r'\s{2,}|\t' if p.endswith('.txt') else ','
            self.tide_df = pd.read_csv(p, skiprows=skip, sep=separator, engine='python')
            
            cols = list(self.tide_df.columns)
            self.tcmb_t.clear(); self.tcmb_z.clear()
            self.tcmb_t.addItems(cols); self.tcmb_z.addItems(cols)
            
            for c in cols:
                cl = str(c).lower()
                if any(k in cl for k in ['time', 'date', 'waktu', 'tanggal']): self.tcmb_t.setCurrentText(c)
                if any(k in cl for k in ['z', 'water', 'elev', 'val', 'tinggi']): self.tcmb_z.setCurrentText(c)
            
            self.log_tide.append(f"▶ File observasi pasut aktif: {os.path.basename(p)}")
            self.btn_tide_f.setText(f"✅ Dimuat: {os.path.basename(p)}")
            self.btn_tide_f.setStyleSheet("color: #42E695; border: 1px solid #42E695;")
            
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
                "Silakan kembali ke 'Modul 1: ERA5 Synthesizer', pilih rentang waktu kalender, lalu ekstrak/kunci datanya agar pasut ini sinkron dengan gelombang."
            )
            return

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
