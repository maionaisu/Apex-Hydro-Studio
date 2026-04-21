import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLineEdit, QLabel, QPushButton, QTextEdit, 
                             QFileDialog, QMessageBox, QFrame, QScrollArea)
from PyQt6.QtCore import Qt

from engines.dimr_executor import DIMREngineManager

class Modul5Execution(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dimr_manager = DIMREngineManager()
        self.dimr_manager.stdout_signal.connect(self.log_stdout)
        self.dimr_manager.stderr_signal.connect(self.log_stderr)
        self.dimr_manager.finished_signal.connect(self.on_process_finished)
        
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        head = QVBoxLayout()
        t = QLabel("DIMR Engine Execution")
        t.setStyleSheet("font-size: 20pt; font-weight: 900; color: white;")
        d = QLabel("Mengeksekusi binari Deltares (run_dimr.bat) melalui QProcess Streaming Terminal.")
        d.setStyleSheet("color: #94A3B8; font-size: 10pt;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 10, 0, 0)
        
        # 1. Top: Controls
        grp1 = QGroupBox("Target Binary (run_dimr.bat) Configuration")
        g1 = QHBoxLayout(grp1)
        
        self.inp_bat = QLineEdit()
        self.inp_bat.setPlaceholderText("C:/Program Files/.../run_dimr.bat")
        btn_browse = QPushButton("Cari .bat")
        btn_browse.setObjectName("OutlineBtn")
        btn_browse.clicked.connect(self.browse_bat)
        
        g1.addWidget(self.inp_bat)
        g1.addWidget(btn_browse)
        scroll_layout.addWidget(grp1)
        
        h_exec = QHBoxLayout()
        self.btn_run = QPushButton("▶ RUN DELTARES DIMR")
        self.btn_run.setObjectName("GreenBtn")
        self.btn_run.clicked.connect(self.start_engine)
        
        self.btn_stop = QPushButton("⏹ ABORT EXECUTION")
        self.btn_stop.setObjectName("ExecuteBtn") 
        self.btn_stop.clicked.connect(self.abort_engine)
        self.btn_stop.setEnabled(False)
        
        h_exec.addWidget(self.btn_run)
        h_exec.addWidget(self.btn_stop)
        scroll_layout.addLayout(h_exec)

        # 2. Bottom: Terminal
        self.lbl_status = QLabel("Status: Idle")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #10B981; font-size: 11pt; margin-top: 15px;")
        scroll_layout.addWidget(self.lbl_status)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setMinimumHeight(400)
        self.terminal.setStyleSheet("background-color: #020617; color: #E2E8F0; font-family: Consolas, monospace; font-size: 10pt;")
        scroll_layout.addWidget(self.terminal, stretch=1)
        scroll_layout.addStretch()
        
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

    def showEvent(self, event):
        super().showEvent(event)
        # Enterprise Polish: Auto-discover run_dimr.bat when user navigates to Modul 5
        if not self.inp_bat.text():
            default_path = os.path.join(os.getcwd(), 'Apex_FM_Model_Final', 'run_dimr.bat')
            if os.path.exists(default_path):
                self.inp_bat.setText(default_path)
                self.lbl_status.setText("Status: Ready (DIMR Auto-Detected)")
                self.lbl_status.setStyleSheet("font-weight: bold; color: #10B981; font-size: 11pt; margin-top: 15px;")
            else:
                self.lbl_status.setText("Status: Idle (Menunggu run_dimr.bat)")

    def browse_bat(self):
        p, _ = QFileDialog.getOpenFileName(self, "Pilih run_dimr.bat", "C:\\", "Batch Files (*.bat)")
        if p: self.inp_bat.setText(p)

    def start_engine(self):
        bat_path = self.inp_bat.text()
        if not bat_path or not os.path.exists(bat_path):
            QMessageBox.warning(self, "Error", "Path run_dimr.bat tidak valid!")
            return
            
        working_dir = os.path.join(os.getcwd(), 'Apex_FM_Model_Final')
        config_xml = os.path.join(working_dir, 'dimr_config.xml')
        
        if not os.path.exists(config_xml):
            QMessageBox.warning(self, "Error", "Folder Model_Final / dimr_config.xml tidak ditemukan. Harap pastikan Modul 4 telah di-compile.")
            return

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("Status: RUNNING HYDROMORPHODYNAMICS...")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #F59E0B; font-size: 11pt;")
        self.terminal.clear()
        self.terminal.append(f"▶ Memulai eksekusi DIMR di: {working_dir}\n")
        
        self.dimr_manager.start_execution(bat_path, working_dir, "dimr_config.xml")

    def abort_engine(self):
        self.dimr_manager.abort_execution()
        
    def log_stdout(self, text):
        self.terminal.append(text)
        
    def log_stderr(self, text):
        self.terminal.append(f"<span style='color: #EF4444;'>{text}</span>")

    def on_process_finished(self, code):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if code == 0:
            self.lbl_status.setText("Status: SUCCESS")
            self.lbl_status.setStyleSheet("font-weight: bold; color: #10B981; font-size: 11pt;")
            self.terminal.append("\n✅ EKSEKUSI SELESAI DENGAN SUKSES. Buka Modul 6 untuk Post-Processing melihat hasilnya.")
        else:
            self.lbl_status.setText(f"Status: KILLED/CRASHED (Code {code})")
            self.lbl_status.setStyleSheet("font-weight: bold; color: #EF4444; font-size: 11pt;")
            self.terminal.append(f"\n❌ PROSES DIMR DIHENTIKAN ATAU CRASH (Exit Code: {code}).")
