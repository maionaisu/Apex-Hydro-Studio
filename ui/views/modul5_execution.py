# ==============================================================================
# APEX NEXUS TIER-0: MODUL 5 - DIMR HPC Execution Terminal (UI VIEW)
# ==============================================================================
import os
import glob
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QLabel, QTextEdit, 
                             QFileDialog, QMessageBox, QFrame, 
                             QFormLayout, QSplitter, QComboBox, QSizePolicy)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QCursor, QTextCursor

# Integrasi Enterprise Flexbox
from ui.components.core_widgets import FlexScrollArea, CardWidget, ModernButton
from engines.dimr_executor import DIMREngineManager
from core.state_manager import app_state

logger = logging.getLogger(__name__)

class Modul5Execution(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('ApexStudio', 'HydroSettings')
        
        # Inisialisasi DIMR Manager dan sambungkan semua sinyal vital (TIER-0)
        self.dimr_manager = DIMREngineManager()
        self.dimr_manager.stdout_signal.connect(self.log_stdout)
        self.dimr_manager.stderr_signal.connect(self.log_stderr)
        self.dimr_manager.finished_signal.connect(self.on_process_finished)
        
        if hasattr(self.dimr_manager, 'error_signal'):
            self.dimr_manager.error_signal.connect(self.on_process_error)
        elif hasattr(self.dimr_manager, 'process_error'):
            self.dimr_manager.process_error.connect(self.on_process_error)
        
        self.setup_ui()

    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16) # Dikurangi agar tidak memakan layar
        main_layout.setSpacing(12)

        # --- COMPACT HEADER ---
        head = QVBoxLayout()
        title_container = QFrame()
        title_container.setObjectName("HeaderBox")
        title_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        title_container.setStyleSheet("QFrame#HeaderBox { background-color: #1E2128; border: 1px solid #3A3F4A; border-radius: 8px; }")
        
        tc_layout = QVBoxLayout(title_container)
        tc_layout.setContentsMargins(12, 8, 12, 8) # Padding tipis
        tc_layout.setSpacing(2) # Jarak baris dirapatkan
        
        t = QLabel("HPC Execution Terminal (DIMR)")
        t.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; border: none;")
        
        # Tag HTML <div> dihapus agar tidak ada margin ekstra
        d = QLabel(
            "Ruang kendali eksekusi komputasi C++ Deltares (D-Flow FM & SWAN) secara asinkron. "
            "Dilengkapi dengan Process Tree Isolation dan anti-memory leak logging buffer."
        )
        d.setStyleSheet("color: #9CA3AF; font-size: 11px; border: none;")
        d.setWordWrap(True)
        
        tc_layout.addWidget(t)
        tc_layout.addWidget(d)
        head.addWidget(title_container)
        main_layout.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")

        # ==============================================================================
        # 1. CONTROLS AREA (TOP - SCROLLABLE)
        # ==============================================================================
        self.scroll_ctrl = FlexScrollArea()
        
        h_groups = QHBoxLayout()
        h_groups.setContentsMargins(0, 0, 0, 0)
        h_groups.setSpacing(20)
        
        # --- KIRI: BINARY & TARGET CONFIG ---
        grp1 = CardWidget("1. Setup Engine & Target File")
        g1 = QFormLayout()
        g1.setHorizontalSpacing(16); g1.setVerticalSpacing(16)
        
        h_file = QHBoxLayout(); h_file.setSpacing(10); h_file.setContentsMargins(0, 0, 0, 0)
        self.inp_bat = QLineEdit()
        self.inp_bat.setPlaceholderText("C:/Program Files/Deltares/.../run_dimr.bat")
        
        btn_browse = ModernButton("📂 Telusuri", "outline")
        btn_browse.clicked.connect(self.browse_bat)
        h_file.addWidget(self.inp_bat, stretch=8); h_file.addWidget(btn_browse, stretch=2)
        
        label_style = "QLabel { color:#CBD5E1; font-weight:bold; font-size:12px; border:none; }"
        g1.addRow(QLabel("Executable (.bat):", styleSheet=label_style), h_file)
        
        self.cmb_config = QComboBox()
        self.cmb_config.addItems([
            "dimr_config.xml (Mode FULL COUPLING)",
            "Apex_Flow.mdu (Mode D-FLOW STANDALONE)",
            "Apex_Wave.mdw (Mode D-WAVES STANDALONE)"
        ])
        g1.addRow(QLabel("Target Eksekusi:", styleSheet=label_style), self.cmb_config)
        
        grp1.add_layout(g1)
        h_groups.addWidget(grp1, stretch=6)
        
        # --- KANAN: EXECUTION CONTROLS ---
        grp2 = CardWidget("2. Orchestration Controls")
        
        self.lbl_status = QLabel("⚪ System Status: Idle")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #9CA3AF; font-size: 13px; background-color: #1F2227; padding: 12px; border-radius: 8px; border: 1px solid #3A3F4A;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grp2.add_widget(self.lbl_status)
        
        h_exec = QHBoxLayout(); h_exec.setSpacing(16); h_exec.setContentsMargins(0, 0, 0, 0)
        
        self.btn_run = ModernButton("▶ JALANKAN ENGINE", "primary")
        self.btn_run.clicked.connect(self.start_engine)
        
        self.btn_stop = ModernButton("⏹ ABORT (KILL)", "danger")
        self.btn_stop.clicked.connect(self.abort_engine)
        self.btn_stop.setEnabled(False)
        
        h_exec.addWidget(self.btn_run, stretch=1)
        h_exec.addWidget(self.btn_stop, stretch=1)
        grp2.add_layout(h_exec)
        
        h_groups.addWidget(grp2, stretch=4)
        
        self.scroll_ctrl.add_layout(h_groups)
        splitter.addWidget(self.scroll_ctrl)
        
        # ==============================================================================
        # 2. TERMINAL AREA (BOTTOM)
        # ==============================================================================
        term_widget = QWidget()
        term_layout = QVBoxLayout(term_widget)
        term_layout.setContentsMargins(0, 5, 0, 0)
        
        term_lbl = QLabel("3. HPC Live Terminal (C++ Engine Log Stream):")
        term_lbl.setStyleSheet("font-weight:900; color:#8FC9DC; font-size: 14px;")
        term_layout.addWidget(term_lbl)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setUndoRedoEnabled(False) 
        self.terminal.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A; 
                color: #34D399; 
                font-family: 'Consolas', 'Courier New', monospace; 
                font-size: 12px; 
                border: 1px solid #3A3F4A; 
                border-radius: 8px; 
                padding: 12px;
                line-height: 1.4;
            }
        """)
        term_layout.addWidget(self.terminal)
        
        splitter.addWidget(term_widget)
        
        # Proporsi terminal disesuaikan
        splitter.setSizes([200, 600])
        main_layout.addWidget(splitter, stretch=1)

    # --------------------------------------------------------------------------
    # LOGIC & EVENTS
    # --------------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._auto_discover_dimr()

    def _auto_discover_dimr(self) -> None:
        if self.inp_bat.text().strip(): return
            
        saved_path = str(self.settings.value('dimr_bat_path', ''))
        if saved_path and saved_path.lower() != 'none' and os.path.exists(saved_path):
            self.inp_bat.setText(saved_path)
            self._update_status("Ready (Jalur Tersimpan Dimuat)", "#42E695", "rgba(66, 230, 149, 0.1)")
            return

        search_patterns = [
            "C:/Program Files/Deltares/*/x64/dimr/bin/run_dimr.bat",
            "C:/Program Files/Deltares/*/plugins/Dimr/bin/run_dimr.bat",
            "C:/Program Files/Deltares/*/plugins/DeltaShell.Dimr/kernels/x64/bin/run_dimr.bat",
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
            font-weight: bold; color: {color_hex}; font-size: 13px; 
            background-color: {bg_color}; padding: 12px; 
            border-radius: 8px; border: 1px solid {color_hex};
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
        target_file = self.cmb_config.currentText().split(" ")[0]
        config_path = os.path.join(working_dir, target_file)
        
        if not os.path.exists(config_path):
            QMessageBox.warning(self, "Konfigurasi Hilang", f"File '{target_file}' tidak ditemukan di folder model.\nPastikan Anda telah berhasil melakukan Kompilasi dengan mode yang sesuai di Modul 4.")
            return

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._update_status("RUNNING (Mengkalkulasi Numerik...)", "#F7C159", "rgba(247, 193, 89, 0.1)")
        
        self.terminal.clear()
        
        self.terminal.append("<span style='color:#595FF7; font-weight:bold;'>▶ [HPC ORCHESTRATOR] Memulai mesin komputasi C++...</span>")
        self.terminal.append(f"<span style='color:#8FC9DC;'>  ├ Workspace : {working_dir}</span>")
        self.terminal.append(f"<span style='color:#8FC9DC;'>  ├ Executable: {bat_path}</span>")
        self.terminal.append(f"<span style='color:#8FC9DC;'>  ├ Target File: {target_file}</span>")
        self.terminal.append(" ") 
        
        self.dimr_manager.start_execution(bat_path, working_dir, target_file)

    def abort_engine(self) -> None:
        reply = QMessageBox.question(self, "Abort Engine", "Anda yakin ingin menghentikan kalkulasi secara paksa?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._update_status("ABORTING (Membunuh Proses)...", "#FC3F4D", "rgba(252, 63, 77, 0.1)")
            self.dimr_manager.abort_execution()

    # --- QProcess Callbacks ---

    def log_stdout(self, text: str) -> None:
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        clean_text = text.strip()
        if clean_text:
            cursor.insertHtml(f"{clean_text}<br>")
        
        self.terminal.setTextCursor(cursor)
        
        scrollbar = self.terminal.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def log_stderr(self, text: str) -> None:
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f"<span style='color: #F59E0B;'>[DIMR WARN] {text.strip()}</span><br>")
        self.terminal.setTextCursor(cursor)

    def on_process_error(self, error_msg: str) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._update_status("FATAL ERROR (Engine Crash)", "#FC3F4D", "rgba(252, 63, 77, 0.1)")
        self.terminal.append(f"<span style='color: #FC3F4D; font-weight: bold;'>❌ {error_msg}</span><br>")

    def on_process_finished(self, exit_code: int) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        if exit_code == 0:
            self._update_status("SUCCESS (Kalkulasi Selesai)", "#42E695", "rgba(66, 230, 149, 0.1)")
            self.terminal.append("<br><span style='color: #10B981; font-weight: bold;'>✅ EKSEKUSI SELESAI DENGAN SUKSES. Output tersedia di folder model.</span><br>")
            QMessageBox.information(self, "Kalkulasi Selesai", "Operasi Engine Deltares telah sukses diselesaikan.")
        else:
            self._update_status(f"KILLED / CRASHED (Code {exit_code})", "#FC3F4D", "rgba(252, 63, 77, 0.1)")
            self.terminal.append(f"<br><span style='color: #EF4444; font-weight: bold;'>❌ PROSES DIHENTIKAN ATAU CRASH (Exit Code: {exit_code}).</span><br>")
