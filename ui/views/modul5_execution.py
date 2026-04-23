# ==============================================================================
# APEX NEXUS TIER-0: MODUL 5 - DIMR HPC EXECUTION TERMINAL (UI VIEW)
# ==============================================================================
import os
import glob
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLineEdit, QLabel, QPushButton, QTextEdit, 
                             QFileDialog, QMessageBox, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, QSettings

from engines.dimr_executor import DIMREngineManager
from core.state_manager import app_state

logger = logging.getLogger(__name__)

# --- ENTERPRISE QSS STYLESHEETS (REVOLUT / GRADIENTA INFLUENCE) ---
STYLE_GROUPBOX = """
    QGroupBox { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; margin-top: 24px; padding-top: 15px; font-weight: bold; color: #F1F5F9; font-size: 14px; }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 10px; background-color: #0F172A; border-radius: 6px; color: #F59E0B; top: -12px; left: 15px; }
"""
STYLE_INPUTS = """
    QLineEdit { background-color: #0F172A; border: 1px solid #475569; border-radius: 6px; padding: 8px 12px; color: #F8FAFC; font-size: 13px; }
    QLineEdit:focus { border: 1px solid #F59E0B; }
"""
STYLE_BTN_PRIMARY = """
    QPushButton#GreenBtn { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #047857); color: #FFFFFF; border: none; border-radius: 8px; padding: 12px 16px; font-weight: bold; font-size: 14px; }
    QPushButton#GreenBtn:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34D399, stop:1 #10B981); }
    QPushButton#GreenBtn:pressed { background-color: #064E3B; }
    QPushButton#GreenBtn:disabled { background-color: #1E293B; color: #64748B; border: 1px solid #334155; }
"""
STYLE_BTN_DANGER = """
    QPushButton#DangerBtn { background-color: transparent; color: #EF4444; border: 2px solid #EF4444; border-radius: 8px; padding: 12px 16px; font-weight: bold; font-size: 14px; }
    QPushButton#DangerBtn:hover { background-color: #7F1D1D; color: #FCA5A5; border-color: #FCA5A5; }
    QPushButton#DangerBtn:disabled { background-color: transparent; color: #64748B; border: 2px solid #334155; }
"""
STYLE_BTN_OUTLINE = """
    QPushButton#OutlineBtn { background-color: transparent; color: #F8FAFC; border: 1px solid #64748B; border-radius: 6px; padding: 8px 16px; font-weight: bold; }
    QPushButton#OutlineBtn:hover { background-color: #334155; border-color: #F59E0B; color: #F59E0B; }
"""


class Modul5Execution(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('ApexStudio', 'HydroSettings')
        
        # Inisialisasi DIMR Manager dan sambungkan semua sinyal vital
        self.dimr_manager = DIMREngineManager()
        self.dimr_manager.stdout_signal.connect(self.log_stdout)
        self.dimr_manager.stderr_signal.connect(self.log_stderr)
        self.dimr_manager.finished_signal.connect(self.on_process_finished)
        
        # [CRITICAL FIX]: Tangkap sinyal kegagalan OS/C++ dari executor
        self.dimr_manager.process_error.connect(self.on_process_error)
        
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_BTN_PRIMARY} {STYLE_BTN_DANGER} {STYLE_BTN_OUTLINE}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER ---
        head = QVBoxLayout()
        t = QLabel("HPC Execution Terminal (DIMR)")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Ruang kendali eksekusi komputasi C++ Deltares (D-Flow FM & SWAN) secara asinkron.")
        d.setStyleSheet("color: #94A3B8; font-size: 14px;")
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
        
        # --- 1. CONTROLS ---
        grp1 = QGroupBox("Target Binary Deltares (run_dimr.bat)")
        g1 = QHBoxLayout(grp1)
        g1.setSpacing(10)
        
        self.inp_bat = QLineEdit()
        self.inp_bat.setPlaceholderText("C:/Program Files/Deltares/D-Flow FM/x64/dimr/bin/run_dimr.bat")
        btn_browse = QPushButton("Cari .bat")
        btn_browse.setObjectName("OutlineBtn")
        btn_browse.clicked.connect(self.browse_bat)
        
        g1.addWidget(self.inp_bat)
        g1.addWidget(btn_browse)
        scroll_layout.addWidget(grp1)
        
        h_exec = QHBoxLayout()
        h_exec.setSpacing(16)
        h_exec.setContentsMargins(0, 10, 0, 10)
        
        self.btn_run = QPushButton("▶ RUN DELTARES DIMR")
        self.btn_run.setObjectName("GreenBtn")
        self.btn_run.clicked.connect(self.start_engine)
        
        self.btn_stop = QPushButton("⏹ ABORT EXECUTION")
        self.btn_stop.setObjectName("DangerBtn") 
        self.btn_stop.clicked.connect(self.abort_engine)
        self.btn_stop.setEnabled(False)
        
        h_exec.addWidget(self.btn_run)
        h_exec.addWidget(self.btn_stop)
        scroll_layout.addLayout(h_exec)

        # --- 2. TERMINAL ---
        self.lbl_status = QLabel("Status: Idle")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #64748B; font-size: 14px; margin-top: 5px;")
        scroll_layout.addWidget(self.lbl_status)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setMinimumHeight(450)
        self.terminal.setStyleSheet("""
            QTextEdit {
                background-color: #020617; 
                color: #A7F3D0; 
                font-family: 'Consolas', 'Courier New', monospace; 
                font-size: 12px; 
                border: 1px solid #1E293B; 
                border-radius: 8px; 
                padding: 12px;
            }
        """)
        scroll_layout.addWidget(self.terminal, stretch=1)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

    def showEvent(self, event):
        super().showEvent(event)
        self._auto_discover_dimr()

    def _auto_discover_dimr(self) -> None:
        """
        Algoritma pencarian pintar untuk lokasi run_dimr.bat Deltares.
        Memprioritaskan riwayat simpanan (QSettings), lalu mencari di Program Files.
        """
        if self.inp_bat.text().strip(): 
            return
            
        # 1. Cek penyimpanan persisten dari eksekusi sebelumnya
        saved_path = self.settings.value('dimr_bat_path', '')
        if saved_path and os.path.exists(saved_path):
            self.inp_bat.setText(saved_path)
            self._update_status("Ready (Jalur Tersimpan Dimuat)", "#10B981")
            return

        # 2. Heuristik pencarian otomatis di instalasi default Windows
        search_patterns = [
            "C:/Program Files/Deltares/*/x64/dimr/bin/run_dimr.bat",
            "C:/Program Files/Deltares/*/plugins/Dimr/bin/run_dimr.bat",
            "C:/Program Files (x86)/Deltares/*/x64/dimr/bin/run_dimr.bat"
        ]
        
        for pattern in search_patterns:
            matches = glob.glob(pattern)
            if matches:
                # Ambil versi terbaru yang ditemukan
                found_path = os.path.abspath(matches[-1]).replace('\\', '/')
                self.inp_bat.setText(found_path)
                self.settings.setValue('dimr_bat_path', found_path)
                self._update_status("Ready (DIMR Auto-Detected dari Sistem)", "#38BDF8")
                return
                
        self._update_status("Idle (Menunggu run_dimr.bat)", "#64748B")

    def _update_status(self, text: str, color_hex: str) -> None:
        self.lbl_status.setText(f"Status: {text}")
        self.lbl_status.setStyleSheet(f"font-weight: bold; color: {color_hex}; font-size: 14px; margin-top: 5px;")

    def browse_bat(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Cari binari eksekusi Deltares (run_dimr.bat)", "C:\\Program Files\\Deltares", "Batch Files (*.bat)")
        if p: 
            self.inp_bat.setText(p)
            self.settings.setValue('dimr_bat_path', p)
            self._update_status("Ready (Path Disetel Manual)", "#10B981")

    def start_engine(self) -> None:
        bat_path = self.inp_bat.text().strip()
        if not bat_path or not os.path.exists(bat_path):
            QMessageBox.critical(self, "File Hilang", "Jalur menuju executable run_dimr.bat tidak valid atau file tidak ada.")
            return
            
        working_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_FM_Model_Final'))
        config_xml = os.path.join(working_dir, 'dimr_config.xml')
        
        if not os.path.exists(config_xml):
            QMessageBox.warning(self, "XML Coupler Hilang", "Folder 'Apex_FM_Model_Final' atau 'dimr_config.xml' tidak ditemukan.\nPastikan Anda telah berhasil melakukan Kompilasi MDU/SWAN di Modul 4.")
            return

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._update_status("RUNNING (Mengkalkulasi Hidrodinamika...)", "#F59E0B")
        
        self.terminal.clear()
        self.terminal.append(f"<span style='color:#38BDF8;'>▶ [HPC ORCHESTRATOR] Memulai mesin komputasi C++...</span>")
        self.terminal.append(f"<span style='color:#64748B;'>  ├ Workspace: {working_dir}</span>")
        self.terminal.append(f"<span style='color:#64748B;'>  ├ Target: {bat_path}</span><br><br>")
        
        # Mendelegasikan eksekusi shell ke QProcess Manager (Non-Blocking)
        self.dimr_manager.start_execution(bat_path, working_dir, "dimr_config.xml")

    def abort_engine(self) -> None:
        """Memaksa penghentian child process secara darurat."""
        reply = QMessageBox.question(self, "Abort Engine", "Anda yakin ingin menghentikan kalkulasi secara paksa? Data yang belum tersimpan oleh DIMR mungkin akan rusak.", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._update_status("ABORTING...", "#EF4444")
            self.dimr_manager.abort_execution()

    # --- QProcess Callbacks ---

    def log_stdout(self, text: str) -> None:
        # Menampilkan keluaran standar dari Delft3D dengan warna hijau terminal
        self.terminal.append(text)
        
    def log_stderr(self, text: str) -> None:
        # Warning/Error internal dari C++ dicetak dengan warna oranye atau merah
        self.terminal.append(f"<span style='color: #FCD34D;'>[DIMR WARN] {text}</span>")

    def on_process_error(self, error_msg: str) -> None:
        """Dipanggil jika QProcess gagal start (Crash/Izin Ditolak/SegFault)."""
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._update_status("FATAL ERROR (Engine Crash)", "#EF4444")
        self.terminal.append(f"<br><span style='color: #EF4444; font-weight: bold;'>❌ {error_msg}</span>")

    def on_process_finished(self, exit_code: int) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        if exit_code == 0:
            self._update_status("SUCCESS (Kalkulasi Selesai)", "#10B981")
            self.terminal.append("<br><span style='color: #10B981; font-weight: bold;'>✅ EKSEKUSI SELESAI DENGAN SUKSES.</span>")
            self.terminal.append("<span style='color: #A7F3D0;'>Silakan melangkah ke Modul 6 (Post-Processing) untuk me-render hasil Output NetCDF menjadi Animasi/Overlay Peta.</span>")
            
            QMessageBox.information(self, "Kalkulasi Selesai", "Operasi hidromorfodinamika DIMR telah sukses diselesaikan.")
        else:
            self._update_status(f"KILLED / CRASHED (Exit Code {exit_code})", "#EF4444")
            self.terminal.append(f"<br><span style='color: #EF4444; font-weight: bold;'>❌ PROSES DIMR DIHENTIKAN ATAU CRASH (Exit Code: {exit_code}).</span>")
