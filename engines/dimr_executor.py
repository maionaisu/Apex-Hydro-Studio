# ==============================================================================
# APEX NEXUS TIER-0: DIMR ENGINE EXECUTOR (QProcess)
# ==============================================================================
import os
import logging
from PyQt6.QtCore import QObject, QProcess, pyqtSignal

logger = logging.getLogger(__name__)

class DIMREngineManager(QObject):
    """
    [TIER-0] Manages the execution of the Deltares DIMR engine via QProcess.
    Stream output is strictly captured and emitted to the Qt Event Loop asynchronously
    to prevent GUI thread blocking (ANR).
    """
    stdout_signal = pyqtSignal(str)
    stderr_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)
    # Sinyal khusus untuk menembakkan error gagal start/crash level OS ke UI
    process_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.process = QProcess()
        
        # Pipa asinkron tanpa blokir (Non-blocking pipes)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished)
        self.process.errorOccurred.connect(self.handle_error)

    def start_execution(self, bat_path: str, working_dir: str, config_file: str = "dimr_config.xml") -> None:
        """
        Menginisiasi kalkulasi D-Flow FM & SWAN (DIMR).
        Dijaga ketat oleh guard rel rel I/O dan State Concurrency.
        """
        # 1. State Guard: Cegah double execution jika status bukan NotRunning
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process_error.emit("[SYSTEM] DIMR Engine sedang berjalan. Batalkan proses saat ini terlebih dahulu.")
            return

        # 2. I/O Validation Guard (Seksi 5.C Requirement)
        if not os.path.exists(working_dir):
            self.process_error.emit(f"[FATAL] Direktori kerja (Workspace) tidak ditemukan: {working_dir}")
            return
        if not os.path.exists(bat_path):
            self.process_error.emit(f"[FATAL] File eksekusi DIMR (run_dimr.bat) tidak ditemukan di: {bat_path}")
            return

        logger.info(f"[DIMR] Memulai eksekusi di: {working_dir} menggunakan {bat_path}")
        
        self.process.setWorkingDirectory(working_dir)
        args = [config_file]
        
        # Eksekusi (Di QProcess shell=False secara default untuk keamanan dari Command Injection)
        self.process.start(bat_path, args)

    def abort_execution(self) -> None:
        """Membunuh child process (C++ Delft3D) secara paksa dan aman."""
        # Pastikan proses memiliki status aktif (Starting / Running) sebelum di-kill
        if self.process.state() != QProcess.ProcessState.NotRunning:
            logger.warning("[DIMR] Menerima sinyal pembatalan (Kill/Abort). Terminasi paksa...")
            self.process.kill()

    def handle_stdout(self) -> None:
        # Decode menggunakan 'replace' mencegah error UTF-8 dari keluaran log CMD Windows
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        for line in data.splitlines():
            if line.strip():
                self.stdout_signal.emit(line)

    def handle_stderr(self) -> None:
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        for line in data.splitlines():
            if line.strip():
                self.stderr_signal.emit(line)

    def handle_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        """Ditangkap saat proses DIMR selesai secara alami atau di-kill."""
        logger.info(f"[DIMR] Eksekusi selesai dengan kode: {exit_code}")
        self.finished_signal.emit(exit_code)

    def handle_error(self, error: QProcess.ProcessError) -> None:
        """
        Menangkap kegagalan internal QProcess (Misal: permission denied, crash, missing DLL).
        """
        error_msgs = {
            QProcess.ProcessError.FailedToStart: "Proses gagal dimulai (File executable rusak atau izin OS ditolak).",
            QProcess.ProcessError.Crashed: "Proses DIMR crash secara tidak wajar (Kemungkinan Out of Memory / C++ SegFault).",
            QProcess.ProcessError.Timedout: "Proses DIMR mengalami timeout tak terduga.",
            QProcess.ProcessError.WriteError: "Gagal menulis instruksi ke memori proses.",
            QProcess.ProcessError.ReadError: "Gagal membaca aliran data dari proses.",
            QProcess.ProcessError.UnknownError: "Terjadi galat sistem operasi (OS Error) yang tidak diketahui."
        }
        msg = error_msgs.get(error, f"Kode Error Tidak Dikenal: {error}")
        logger.error(f"[DIMR QPROCESS ERROR] {msg}")
        self.process_error.emit(f"[FATAL QProcess] {msg}")
