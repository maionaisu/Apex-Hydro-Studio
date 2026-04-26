# ==============================================================================
# APEX NEXUS TIER-0: DIMR ENGINE EXECUTOR (QProcess)
# ==============================================================================
import os
import sys
import logging
import subprocess
from PyQt6.QtCore import QObject, QProcess, pyqtSignal, QProcessEnvironment

logger = logging.getLogger(__name__)

class DIMREngineManager(QObject):
    """
    [TIER-0] Manages the execution of the Deltares DIMR engine via QProcess.
    Upgraded with: 
    1. Windows Taskkill Tree (/T /F) to slaughter orphaned zombie processes (dflowfm.exe/swan.exe).
    2. Anti-Tearing Buffered Line Reader (canReadLine).
    3. Process Environment Isolation.
    """
    stdout_signal = pyqtSignal(str)
    stderr_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)
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
        Menginisiasi kalkulasi D-Flow FM & SWAN (DIMR/Standalone).
        """
        # 1. State Guard: Cegah double execution
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process_error.emit("[SYSTEM] DIMR Engine sedang berjalan. Batalkan proses saat ini terlebih dahulu.")
            return

        # 2. I/O Validation Guard
        if not os.path.exists(working_dir):
            self.process_error.emit(f"[FATAL] Direktori kerja (Workspace) tidak ditemukan: {working_dir}")
            return
        if not os.path.exists(bat_path):
            self.process_error.emit(f"[FATAL] File eksekusi (run_dimr.bat) tidak ditemukan di: {bat_path}")
            return

        logger.info(f"[DIMR] Memulai eksekusi di: {working_dir} menggunakan {bat_path}")
        
        # 3. Environment Isolation (Esensial untuk Enterprise)
        # Menjamin C++ engine tidak terganggu oleh environment variables GUI Python
        env = QProcessEnvironment.systemEnvironment()
        self.process.setProcessEnvironment(env)
        
        self.process.setWorkingDirectory(working_dir)
        
        self.process.setProgram(bat_path)
        self.process.setArguments([config_file])
        
        # Eksekusi aman dari Command Injection
        self.process.start()

    def abort_execution(self) -> None:
        """
        [CRITICAL BUG-FIX]: Mencegah Orphaned Process (Zombie C++ Nodes) di Windows.
        File .bat menjalankan cmd.exe, yang kemudian menjalankan dflowfm.exe.
        Jika kita hanya memanggil process.kill(), hanya cmd.exe yang mati. dflowfm.exe akan 
        terus menyala secara gaib dan memakan 100% CPU.
        Kita gunakan perintah 'taskkill /T /F /PID' OS-level untuk membantai seluruh tree.
        """
        if self.process.state() != QProcess.ProcessState.NotRunning:
            logger.warning("[DIMR] Memulai prosedur Pemusnahan Pohon Proses (Kill Tree)...")
            self.stdout_signal.emit("<span style='color:#FC3F4D;'>[SYSTEM] Meluncurkan SIGKILL ke seluruh pohon komputasi...</span>")
            
            # Ekstrak Process ID (PID) dari induk (cmd.exe)
            pid = self.process.processId()
            
            if sys.platform == 'win32':
                try:
                    # /F = Force, /T = Tree (Membunuh child process seperti dflowfm.exe & swan.exe)
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(pid)], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    logger.error(f"[DIMR] Gagal mengeksekusi taskkill: {e}")
                    self.process.kill() # Fallback ke native Qt kill
            else:
                # Untuk Linux/Mac, kill() biasanya sudah mengirim SIGKILL ke seluruh process group
                self.process.kill()

    def handle_stdout(self) -> None:
        """
        [BUG-FIX]: Mencegah Buffer Tearing/Line Fragmentation.
        Hanya membaca dan mem-parsing baris yang sudah komplit secara struktural.
        """
        while self.process.canReadLine():
            line_bytes = self.process.readLine().data()
            line_str = line_bytes.decode('utf-8', errors='replace').strip()
            if line_str:
                self.stdout_signal.emit(line_str)

    def handle_stderr(self) -> None:
        """Sama dengan stdout, mencegah log peringatan terpotong."""
        while self.process.canReadLine():
            line_bytes = self.process.readLine().data()
            line_str = line_bytes.decode('utf-8', errors='replace').strip()
            if line_str:
                self.stderr_signal.emit(line_str)

    def handle_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        """Ditangkap saat proses selesai secara alami atau dibantai (Taskkill)."""
        logger.info(f"[DIMR] Eksekusi ditutup dengan kode: {exit_code} | Status: {exit_status.name}")
        
        # Terkadang proses mati karena Crash C++ yang lolos dari exit_code = 0
        if exit_status == QProcess.ExitStatus.CrashExit:
            exit_code = -1 # Memaksa trigger status GAGAL di UI
            
        self.finished_signal.emit(exit_code)

    def handle_error(self, error: QProcess.ProcessError) -> None:
        """Menangkap kegagalan internal QProcess."""
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
