# ==============================================================================
# APEX NEXUS TIER-0: MODUL 5 - DIMR HPC EXECUTION TERMINAL (UI VIEW)
# ==============================================================================
import os
import glob
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLineEdit, QLabel, QPushButton, QTextEdit, 
                             QFileDialog, QMessageBox, QFrame, QScrollArea, 
                             QFormLayout, QSplitter, QComboBox)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QCursor, QTextCursor

from engines.dimr_executor import DIMREngineManager
from core.state_manager import app_state

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
STYLE_BTNS = """
    QPushButton#PrimaryBtn { background-color: #595FF7; color: #FFFFFF; border: none; border-radius: 10px; padding: 14px 16px; font-weight: 900; font-size: 14px; }
    QPushButton#PrimaryBtn:hover { background-color: #7176F8; }
    QPushButton#PrimaryBtn:disabled { background-color: #3A3F4A; color: #6B7280; }
    
    QPushButton#DangerBtn { background-color: transparent; color: #FC3F4D; border: 2px solid #FC3F4D; border-radius: 10px; padding: 14px 16px; font-weight: 900; font-size: 14px; }
    QPushButton#DangerBtn:hover { background-color: rgba(252, 63, 77, 0.1); }
    QPushButton#DangerBtn:disabled { color: #6B7280; border-color: #3A3F4A; }
    
    QPushButton#OutlineBtn { background-color: transparent; color: #8FC9DC; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 16px; font-weight: 800; font-size: 13px; }
    QPushButton#OutlineBtn:hover { background-color: rgba(143, 201, 220, 0.1); border-color: #8FC9DC; }
"""


class Modul5Execution(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('ApexStudio', 'HydroSettings')
        
        # Inisialisasi DIMR Manager dan sambungkan semua sinyal vital (TIER-0)
        self.dimr_manager = DIMREngineManager()
        self.dimr_manager.stdout_signal.connect(self.log_stdout)
        self.dimr_manager.stderr_signal.connect(self.log_stderr)
        self.dimr_manager.finished_signal.connect(self.on_process_finished)
        
        # [BUG FIX]: Safe-Binding untuk sinyal error (Menangani Typo Nama Sinyal)
        if hasattr(self.dimr_manager, 'error_signal'):
            self.dimr_manager.error_signal.connect(self.on_process_error)
        elif hasattr(self.dimr_manager, 'process_error'):
            self.dimr_manager.process_error.connect(self.on_process_error)
        
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setStyleSheet(f"{STYLE_GROUPBOX} {STYLE_INPUTS} {STYLE_BTNS}")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER ---
        head = QVBoxLayout()
        t = QLabel("HPC Execution Terminal (DIMR)")
        t.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")
        d = QLabel("Ruang kendali eksekusi komputasi C++ Deltares (D-Flow FM & SWAN) secara asinkron.")
        d.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")

        # ==============================================================================
        # 1. CONTROLS AREA (TOP)
        # ==============================================================================
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        
        # Menggunakan HBox untuk menjejajar Group 1 (Kiri) dan Group 2 (Kanan)
        h_groups = QHBoxLayout()
        h_groups.setSpacing(24)
        
        # --- KIRI: BINARY & TARGET CONFIG ---
        c1 = QVBoxLayout()
        grp1 = QGroupBox("1. Setup Engine & Target File")
        g1 = QFormLayout(grp1)
        g1.setHorizontalSpacing(16); g1.setVerticalSpacing(16)
        
        # Binary Locator
        h_file = QHBoxLayout(); h_file.setSpacing(10)
        self.inp_bat = QLineEdit()
        self.inp_bat.setPlaceholderText("C:/Program Files/Deltares/*/run_dimr.bat")
        btn_browse = QPushButton("📂 Telusuri")
        btn_browse.setObjectName("OutlineBtn")
        btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse.clicked.connect(self.browse_bat)
        h_file.addWidget(self.inp_bat, stretch=8); h_file.addWidget(btn_browse, stretch=2)
        g1.addRow(QLabel("Executable (.bat):", styleSheet="color:#CBD5E1; font-weight:bold;"), h_file)
        
        # Config Selector (Mengakomodasi Modul 4 Baru)
        self.cmb_config = QComboBox()
        self.cmb_config.addItems([
            "dimr_config.xml (Mode FULL COUPLING)",
            "Apex_Flow.mdu (Mode D-FLOW STANDALONE)",
            "Apex_Wave.mdw (Mode D-WAVES STANDALONE)"
        ])
        g1.addRow(QLabel("Target Eksekusi:", styleSheet="color:#CBD5E1; font-weight:bold;"), self.cmb_config)
        
        c1.addWidget(grp1); c1.addStretch()
        h_groups.addLayout(c1, stretch=6)
        
        # --- KANAN: EXECUTION CONTROLS ---
        c2 = QVBoxLayout()
        grp2 = QGroupBox("2. Orchestration Controls")
        g2 = QVBoxLayout(grp2)
        g2.setSpacing(16)
        
        # Status Label
        self.lbl_status = QLabel("⚪ System Status: Idle")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #9CA3AF; font-size: 14px; background-color: #1F2227; padding: 12px; border-radius: 8px; border: 1px solid #3A3F4A;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        g2.addWidget(self.lbl_status)
        
        # Buttons
        h_exec = QHBoxLayout(); h_exec.setSpacing(16)
        
        self.btn_run = QPushButton("▶ JALANKAN ENGINE")
        self.btn_run.setObjectName("PrimaryBtn")
        self.btn_run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_run.clicked.connect(self.start_engine)
        
        self.btn_stop = QPushButton("⏹ ABORT (KILL)")
        self.btn_stop.setObjectName("DangerBtn") 
        self.btn_stop.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_stop.clicked.connect(self.abort_engine)
        self.btn_stop.setEnabled(False)
        
        h_exec.addWidget(self.btn_run, stretch=1)
        h_exec.addWidget(self.btn_stop, stretch=1)
        g2.addLayout(h_exec)
        
        c2.addWidget(grp2); c2.addStretch()
        h_groups.addLayout(c2, stretch=4)
        
        ctrl_layout.addLayout(h_groups)
        splitter.addWidget(ctrl_widget)
        
        # ==============================================================================
        # 2. TERMINAL AREA (BOTTOM)
        # ==============================================================================
        term_widget = QWidget()
        term_layout = QVBoxLayout(term_widget)
        term_layout.setContentsMargins(0, 10, 0, 0)
        
        term_lbl = QLabel("3. HPC Live Terminal (C++ Engine Log Stream):")
        term_lbl.setStyleSheet("font-weight:900; color:#8FC9DC; font-size: 15px;")
        term_layout.addWidget(term_lbl)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        # [BUG FIX]: Membatasi undo/redo buffer yang dapat memakan memori RAM saat log panjang
        self.terminal.setUndoRedoEnabled(False)
        self.terminal.setStyleSheet("""
            QTextEdit {
                background-color: #1E2128; 
                color: #42E695; 
                font-family: 'Consolas', 'Courier New', monospace; 
                font-size: 13px; 
                border: 1px solid #3A3F4A; 
                border-radius: 8px; 
                padding: 14px;
                line-height: 1.5;
            }
        """)
        term_layout.addWidget(self.terminal)
        
        splitter.addWidget(term_widget)
        
        # Proporsi: Terminal mengambil porsi dominan (70% - 30%)
        splitter.setSizes([200, 500])
        main_layout.addWidget(splitter, stretch=1)

    # --------------------------------------------------------------------------
    # LOGIC & EVENTS
    # --------------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._auto_discover_dimr()

    def _auto_discover_dimr(self) -> None:
        """Pencarian cerdas jalur eksekutor Deltares berdasarkan QSettings/Program Files."""
        if self.inp_bat.text().strip(): return
            
        # [BUG FIX]: Pastikan nilai cast ke str() secara ketat untuk mencegah TypeError
        saved_path = str(self.settings.value('dimr_bat_path', ''))
        if saved_path and saved_path.lower() != 'none' and os.path.exists(saved_path):
            self.inp_bat.setText(saved_path)
            self._update_status("Ready (Jalur Tersimpan Dimuat)", "#42E695", "rgba(66, 230, 149, 0.1)")
            return

        search_patterns = [
            "C:/Program Files/Deltares/*/x64/dimr/bin/run_dimr.bat",
            "C:/Program Files/Deltares/*/plugins/Dimr/bin/run_dimr.bat",
            "C:/Program Files (x86)/Deltares/*/x64/dimr/bin/run_dimr.bat"
        ]
        
        for pattern in search_patterns:
            matches = glob.glob(pattern)
            if matches:
                found_path = os.path.abspath(matches[-1]).replace('\\', '/')
                self.inp_bat.setText(found_path)
                self.settings.setValue('dimr_bat_path', found_path)
                self._update_status("Ready (DIMR Terdeteksi Otomatis)", "#595FF7", "rgba(89, 95, 247, 0.1)")
                return
                
        self._update_status("Idle (Menunggu File .bat)", "#9CA3AF", "#1F2227")

    def _update_status(self, text: str, color_hex: str, bg_color: str) -> None:
        icon = "⚪"
        if color_hex == "#42E695": icon = "🟢"
        elif color_hex == "#F7C159": icon = "⚡"
        elif color_hex == "#FC3F4D": icon = "🔴"
        elif color_hex == "#595FF7": icon = "🔵"
        
        self.lbl_status.setText(f"{icon} System Status: {text}")
        self.lbl_status.setStyleSheet(f"""
            font-weight: bold; 
            color: {color_hex}; 
            font-size: 14px; 
            background-color: {bg_color}; 
            padding: 12px; 
            border-radius: 8px; 
            border: 1px solid {color_hex};
        """)

    def browse_bat(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Cari file eksekusi (run_dimr.bat)", "C:\\Program Files\\Deltares", "Batch Files (*.bat)")
        if p: 
            self.inp_bat.setText(p)
            self.settings.setValue('dimr_bat_path', p)
            self._update_status("Ready (Path Disetel Manual)", "#42E695", "rgba(66, 230, 149, 0.1)")

    def start_engine(self) -> None:
        bat_path = self.inp_bat.text().strip()
        if not bat_path or not os.path.exists(bat_path):
            QMessageBox.critical(self, "File Hilang", "Jalur menuju executable .bat tidak valid.")
            return
            
        working_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_FM_Model_Final'))
        
        # Ekstrak nama file target (contoh: "dimr_config.xml" dari "dimr_config.xml (Mode FULL COUPLING)")
        target_file = self.cmb_config.currentText().split(" ")[0]
        config_path = os.path.join(working_dir, target_file)
        
        if not os.path.exists(config_path):
            QMessageBox.warning(self, "Konfigurasi Hilang", f"File '{target_file}' tidak ditemukan di folder model.\nPastikan Anda telah berhasil melakukan Kompilasi dengan mode yang sesuai di Modul 4.")
            return

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._update_status("RUNNING (Mengkalkulasi Numerik...)", "#F7C159", "rgba(247, 193, 89, 0.1)")
        
        self.terminal.clear()
        
        # [BUG FIX]: Hapus <br><br> yang akan membuat whitespace membengkak di layar terminal
        self.terminal.append("<span style='color:#595FF7; font-weight:bold;'>▶ [HPC ORCHESTRATOR] Memulai mesin komputasi C++...</span>")
        self.terminal.append(f"<span style='color:#8FC9DC;'>  ├ Workspace : {working_dir}</span>")
        self.terminal.append(f"<span style='color:#8FC9DC;'>  ├ Executable: {bat_path}</span>")
        self.terminal.append(f"<span style='color:#8FC9DC;'>  ├ Target File: {target_file}</span>")
        self.terminal.append("") # Spacer murni
        
        # Meneruskan Target Config ke DIMR Manager
        self.dimr_manager.start_execution(bat_path, working_dir, target_file)

    def abort_engine(self) -> None:
        reply = QMessageBox.question(self, "Abort Engine", "Anda yakin ingin menghentikan kalkulasi secara paksa?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._update_status("ABORTING...", "#FC3F4D", "rgba(252, 63, 77, 0.1)")
            self.dimr_manager.abort_execution()

    # --- QProcess Callbacks ---

    def log_stdout(self, text: str) -> None:
        # [BUG FIX]: Menerapkan QTextCursor sejati agar UI tidak Freeze/Hang saat DIMR melompat ke 1000 baris/detik
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Bersihkan trailing newline dari engine agar tidak terbentuk ruang kosong
        clean_text = text.strip()
        if clean_text:
            cursor.insertHtml(f"{clean_text}<br>")
        
        self.terminal.setTextCursor(cursor)
        
        # Auto-scroll menuju bawah secara otomatis
        scrollbar = self.terminal.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def log_stderr(self, text: str) -> None:
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f"<span style='color: #F7C159;'>[DIMR WARN] {text.strip()}</span><br>")
        self.terminal.setTextCursor(cursor)

    def on_process_error(self, error_msg: str) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._update_status("FATAL ERROR (Engine Crash)", "#FC3F4D", "rgba(252, 63, 77, 0.1)")
        self.terminal.append(f"<br><span style='color: #FC3F4D; font-weight: bold;'>❌ {error_msg}</span>")

    def on_process_finished(self, *args) -> None:
        # [BUG FIX]: Penangkapan dinamis `*args` untuk membentengi aplikasi apabila QProcess 
        # melempar lebih dari 1 argumen (contoh: exit_code, exit_status) 
        exit_code = args[0] if len(args) > 0 else 1
        
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        if exit_code == 0:
            self._update_status("SUCCESS (Kalkulasi Selesai)", "#42E695", "rgba(66, 230, 149, 0.1)")
            self.terminal.append("<br><span style='color: #42E695; font-weight: bold;'>✅ EKSEKUSI SELESAI DENGAN SUKSES.</span>")
            QMessageBox.information(self, "Kalkulasi Selesai", "Operasi Engine Deltares telah sukses diselesaikan.")
        else:
            self._update_status(f"KILLED / CRASHED (Code {exit_code})", "#FC3F4D", "rgba(252, 63, 77, 0.1)")
            self.terminal.append(f"<br><span style='color: #FC3F4D; font-weight: bold;'>❌ PROSES DIHENTIKAN ATAU CRASH (Exit Code: {exit_code}).</span>")
