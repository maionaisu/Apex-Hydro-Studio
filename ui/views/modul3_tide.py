import os
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QGridLayout, QLineEdit, QSplitter)
from PyQt6.QtCore import Qt

from workers.tide_worker import TideAnalyzerWorker, TideGeneratorWorker
from core.state_manager import app_state

class Modul3Tide(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        head = QVBoxLayout()
        t = QLabel("Tidal Harmonix Synthesizer")
        t.setStyleSheet("font-size: 24px; font-weight: 900; color: white;")
        d = QLabel("Ekstrak nilai konstanta harmonik murni (Least Squares) dari seri waktu pasang surut pelabuhan/SRGI.")
        d.setStyleSheet("color: #94A3B8; font-size: 13px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Middle Segment (Controls)
        ctrl_widget = QWidget()
        ctrl = QHBoxLayout(ctrl_widget)
        ctrl.setContentsMargins(0, 10, 0, 10)

        # Col 1: LSHA Control
        c1 = QVBoxLayout()
        grp1 = QGroupBox("1. Data Parser & Inversi LSHA")
        g1 = QFormLayout(grp1)
        
        self.btn_tide_f = QPushButton("Unggah File Observasi (.csv / .txt)")
        self.btn_tide_f.setObjectName("OutlineBtn")
        self.btn_tide_f.clicked.connect(self.load_tide_file)
        g1.addRow(self.btn_tide_f)
        
        self.tcmb_t = QComboBox()
        self.tcmb_z = QComboBox()
        g1.addRow("Kolom Waktu:", self.tcmb_t)
        g1.addRow("Kolom Elevasi:", self.tcmb_z)
        
        self.btn_ext = QPushButton("Jalankan LSHA Ekstraksi")
        self.btn_ext.setObjectName("ExecuteBtn")
        self.btn_ext.clicked.connect(self.run_tide_analyzer)
        g1.addRow(self.btn_ext)
        
        c1.addWidget(grp1)
        c1.addStretch()
        ctrl.addLayout(c1)

        # Col 2: Output Editing
        c2 = QVBoxLayout()
        grp2 = QGroupBox("2. Parameter Ekstraksi Harmonik / Override Manual")
        g2 = QGridLayout(grp2)
        
        self.inp_tides = {}
        consts = ['M2','S2','N2','K1','O1','P1','SA','SSA']
        
        for i, k in enumerate(consts):
            g2.addWidget(QLabel(k), i//2, (i%2)*3)
            
            amp = QLineEdit()
            amp.setPlaceholderText("Amp (m)")
            amp.setFixedWidth(60)
            
            pha = QLineEdit()
            pha.setPlaceholderText("Phase (°)")
            pha.setFixedWidth(60)
            
            self.inp_tides[k] = [amp, pha]
            g2.addWidget(amp, i//2, (i%2)*3 + 1)
            g2.addWidget(pha, i//2, (i%2)*3 + 2)
            
        self.btn_gen = QPushButton("Sintesis Forcing Boundary (.bc)")
        self.btn_gen.setObjectName("GreenBtn")
        self.btn_gen.clicked.connect(self.run_tide_generator)
        c2.addWidget(grp2)
        c2.addWidget(self.btn_gen)
        c2.addStretch()
        
        ctrl.addLayout(c2)
        splitter.addWidget(ctrl_widget)

        # Bottom Segment (Log)
        bot_wrap = QWidget()
        bl = QVBoxLayout(bot_wrap)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(QLabel("Terminal Log (LSHA):", styleSheet="font-weight:bold; color:#F59E0B;"))
        self.log_tide = QTextEdit()
        self.log_tide.setReadOnly(True)
        bl.addWidget(self.log_tide)
        splitter.addWidget(bot_wrap)

        splitter.setSizes([350, 450])
        main_layout.addWidget(splitter)

    def load_tide_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Buka Pasut Observasi", "", "Text/CSV (*.txt *.csv)")
        if not p: return
        
        try:
            # Detect metadata headers by checking row logic from monolithic legacy
            with open(p, 'r', errors='ignore') as f: 
                lines = f.readlines()
                
            skip = next((i for i, l in enumerate(lines[:50]) if any(k in l.lower() for k in ['z(m)','rad1','water', 'date', 'time'])), 0)
            self.tide_df = pd.read_csv(p, skiprows=skip, sep=r'\s{2,}|\t' if p.endswith('.txt') else ',', engine='python')
            
            cols = list(self.tide_df.columns)
            self.tcmb_t.clear()
            self.tcmb_z.clear()
            self.tcmb_t.addItems(cols)
            self.tcmb_z.addItems(cols)
            
            self.log_tide.append(f"▶ File observasi pasut = {os.path.basename(p)}")
        except Exception as e:
            self.log_tide.append(f"❌ Gagal mem-parsing DataFrame: {e}")

    def run_tide_analyzer(self):
        if not hasattr(self, 'tide_df'): return
        
        self.tide_a = TideAnalyzerWorker(self.tide_df, self.tcmb_t.currentText(), self.tcmb_z.currentText())
        self.tide_a.log_signal.connect(self.log_tide.append)
        
        def display_results(res):
            self.btn_ext.setEnabled(True)
            self.btn_ext.setText("Jalankan LSHA Ekstraksi")
            for k, v in res.items():
                if k in self.inp_tides:
                    self.inp_tides[k][0].setText(f"{v['amp']:.4f}")
                    self.inp_tides[k][1].setText(f"{v['pha']:.2f}")
            self.tide_a.deleteLater()
                    
        self.tide_a.result_signal.connect(display_results)
        
        self.btn_ext.setEnabled(False)
        self.btn_ext.setText("⏳ Sedang Mengekstrak Komponen...")
        self.tide_a.start()

    def run_tide_generator(self):
        # Build dictionary from input forms
        c = {}
        for k, v in self.inp_tides.items():
            try:
                amp = float(v[0].text() or 0)
                pha = float(v[1].text() or 0)
                c[k] = {'amp': amp, 'pha': pha}
            except ValueError:
                c[k] = {'amp': 0.0, 'pha': 0.0}
                
        out_dir = os.path.join(os.getcwd(), 'Apex_FM_Model_Final')
        self.tide_gen = TideGeneratorWorker(c, out_dir)
        
        def save_state(path):
            self.btn_gen.setEnabled(True)
            self.btn_gen.setText("Sintesis Forcing Boundary (.bc)")
            if path:
                app_state.update('tide_bc', path)
                self.log_tide.append("✅ Sinkronisasi Memory LSHA Sukses. File .bc siap diintegrasikan pada Modul 4.")
            self.tide_gen.deleteLater()
                
        self.tide_gen.finished_signal.connect(save_state)
        
        self.btn_gen.setEnabled(False)
        self.btn_gen.setText("⏳ Sedang Menulis Time-Series bc...")
        self.tide_gen.start()
