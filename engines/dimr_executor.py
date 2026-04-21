import os
from PyQt6.QtCore import QObject, QProcess, pyqtSignal

class DIMREngineManager(QObject):
    """
    Manages the execution of the Deltares DIMR engine via QProcess.
    This ensures that stdout/stderr stream directly to the Qt Event Loop.
    """
    stdout_signal = pyqtSignal(str)
    stderr_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished)

    def start_execution(self, bat_path, working_dir, config_file="dimr_config.xml"):
        self.process.setWorkingDirectory(working_dir)
        args = [config_file]
        self.process.start(bat_path, args)
        
    def abort_execution(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        for line in data.splitlines():
            if line.strip():
                self.stdout_signal.emit(line)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        for line in data.splitlines():
            if line.strip():
                self.stderr_signal.emit(line)

    def handle_finished(self, exit_code, exit_status):
        self.finished_signal.emit(exit_code)
