# ==============================================================================
# APEX NEXUS TIER-0: MASTER ENTRY POINT (APPLICATION SHELL)
# ==============================================================================
import sys
import os
import logging
import traceback

# ── 1. ENTERPRISE PATH RESOLUTION & ENVIRONMENT GUARD ─────────────────────────
def get_app_root() -> str:
    """
    [TIER-0 SAFEGUARD] O(1) Root Path Resolver.
    Mencegah Fatal Data-Loss Bug pada PyInstaller. Jika berjalan sebagai .exe,
    semua data eksport/log akan disimpan di sebelah file .exe, BUKAN di folder Temp (_MEIPASS).
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def enterprise_path_resolver(relative_path: str) -> str:
    """Menjamin aset UI (QSS/Ico/HTML) selalu ditemukan dari paket internal kompilasi."""
    try:
        base_path = sys._MEIPASS # PyInstaller temp folder
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

APP_ROOT = get_app_root()
EXPORT_DIR = os.path.join(APP_ROOT, 'Apex_Data_Exports')
os.makedirs(EXPORT_DIR, exist_ok=True)
log_file = os.path.join(EXPORT_DIR, 'system_crash.log')

# Inisiasi Logging paling awal agar kegagalan Impor terekam di Disk
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'), 
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ApexMaster")

# [HARDENING]: Inisialisasi Direktori Utama
try:
    from utils.config import get_project_dirs
    get_project_dirs()
except ImportError:
    logger.warning("Fungsi get_project_dirs tidak ditemukan, mengabaikan inisialisasi...")
except Exception as e:
    logger.error(f"Gagal menginisialisasi direktori proyek: {e}")

# Import Modul UI Inti
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFrame, 
                             QStackedWidget, QGridLayout, 
                             QMessageBox, QComboBox, QFileDialog, QSplashScreen, QGroupBox)
from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtGui import QIcon, QPixmap, QCursor, QColor, QFont

from core.state_manager import app_state

from ui.views.modul1_era5 import Modul1ERA5
from ui.views.modul2_sediment import Modul2Sediment
from ui.views.modul3_tide import Modul3Tide
from ui.views.modul4_mesh import Modul4Mesh
from ui.views.modul5_execution import Modul5Execution
from ui.views.modul6_postproc import Modul6PostProc
from ui.components.core_widgets import InteractiveTourOverlay

# ── 2. GLOBAL EXCEPTION HANDLER ───────────────────────────────────────────────
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """[TIER-0 SAFEGUARD] Menangkap error fatal agar aplikasi tidak 'Silent Crash'."""
    logger.critical("UNCAUGHT FATAL EXCEPTION", exc_info=(exc_type, exc_value, exc_traceback))
    
    if QApplication.instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Apex Hydro-Studio : Kesalahan Sistem Fatal")
        msg.setText("Terjadi galat fatal pada kernel aplikasi.")
        msg.setInformativeText(f"Log galat telah disimpan secara permanen di:\n{log_file}")
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        msg.setDetailedText("".join(tb_lines))
        msg.setStyleSheet("QLabel { color: #000; background-color: transparent; }") 
        msg.exec()
    else:
        print("FATAL ERROR (UI Mati):", exc_value)

sys.excepthook = global_exception_handler

# ── 3. CORE APPLICATION ARCHITECTURE ──────────────────────────────────────────
class ApexHydroStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Apex Hydro-Studio: Enterprise Analytics (v18.0)")
        self.setMinimumSize(1450, 950)
        
        icon_path = enterprise_path_resolver(os.path.join('assets', 'Apex Wave Studio.ico'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        theme_path = enterprise_path_resolver(os.path.join("assets", "theme.qss"))
        if os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding='utf-8') as f:
                    self.setStyleSheet(f.read())
            except Exception as e:
                logger.error(f"Gagal memuat Tema QSS: {e}")
                
        self.main_w = QWidget()
        self.main_w.setObjectName("MainWidget")
        self.setCentralWidget(self.main_w)
        
        self.layout = QHBoxLayout(self.main_w)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.init_sidebar()
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget, stretch=1)
        self.modules_loaded = False

    def build_heavy_modules(self, splash: QSplashScreen):
        logger.info("Membangun arsitektur modul D-Flow FM & SWAN...")
        
        # [ENTERPRISE FIX]: Kunci interaksi pengguna selama loading agar tidak terjadi Race Condition
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            splash.showMessage("Memuat Modul 1: Sintesis Data ERA5...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
            self.modul1 = Modul1ERA5()
            QApplication.processEvents()

            splash.showMessage("Memuat Modul 2: Pemetaan Morfologi Sedimen...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
            self.modul2 = Modul2Sediment()
            QApplication.processEvents()

            splash.showMessage("Memuat Modul 3: Harmonik Pasang Surut...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
            self.modul3 = Modul3Tide()
            QApplication.processEvents()

            splash.showMessage("Memuat Modul 4: Pembangkit Mesh Digital Twin...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
            self.modul4 = Modul4Mesh()
            QApplication.processEvents()

            splash.showMessage("Memuat Modul 5: Eksekusi HPC DIMR...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
            self.modul5 = Modul5Execution()
            QApplication.processEvents()

            splash.showMessage("Memuat Modul 6: Pasca-Pemrosesan & Validasi...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
            self.modul6 = Modul6PostProc()
            QApplication.processEvents()
            
            self.modules = [self.modul1, self.modul2, self.modul3, self.modul4, self.modul5, self.modul6]
            for m in self.modules:
                self.stacked_widget.addWidget(m)

            app_state.state_updated.connect(self.update_global_state_ui)
            app_state.bulk_state_updated.connect(self.update_global_state_ui)

            self.tour_overlay = InteractiveTourOverlay(self)
            self.setup_interactive_guides()
            
            self.switch_page(0)
            self.modules_loaded = True
            logger.info("Apex Hydro-Studio siap untuk simulasi riset.")
            
        finally:
            # Kembalikan kursor ke normal apa pun yang terjadi
            QApplication.restoreOverrideCursor()

    def init_sidebar(self) -> None:
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarFrame") 
        self.sidebar.setFixedWidth(290)
        
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(22, 25, 22, 25)
        side_lay.setSpacing(10)

        h_brand = QHBoxLayout()
        png_path = enterprise_path_resolver(os.path.join('assets', 'Apex Wave Studio.png'))
        if os.path.exists(png_path):
            lbl_logo = QLabel()
            lbl_logo.setPixmap(QPixmap(png_path).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            h_brand.addWidget(lbl_logo)
            
        lbl_brand = QLabel("APEX STUDIO")
        lbl_brand.setStyleSheet("font-size: 22px; font-weight: 900; color: #FFFFFF; letter-spacing: 2px;")
        h_brand.addWidget(lbl_brand)
        h_brand.addStretch()
        side_lay.addLayout(h_brand)
        side_lay.addSpacing(20)
        
        lbl_hpc = QLabel("BACKEND KOMPUTASI:")
        lbl_hpc.setStyleSheet("color: #6B7280; font-size: 10px; font-weight: 800;")
        side_lay.addWidget(lbl_hpc)
        
        self.cmb_backend = QComboBox()
        self.cmb_backend.addItems(["🖥️ CPU (Bawaan)", "🚀 CUDA (GPU)", "🔥 HIBRIDA"])
        self.cmb_backend.currentTextChanged.connect(lambda t: app_state.update('compute_backend', t))
        side_lay.addWidget(self.cmb_backend)
        side_lay.addSpacing(15)

        self.nav_btns = []
        nav_items = [
            ("⛆  Sintesis ERA5", 0), 
            ("▤  Medan Sedimen", 1), 
            ("🌊  Harmonik Pasut", 2), 
            ("⚙  Orkestrator DIMR", 3), 
            ("🚀  Eksekusi HPC", 4), 
            ("📊  Lab Validasi", 5)
        ]
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("NavBtn")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda checked, i=idx: self.switch_page(i))
            self.nav_btns.append(btn)
            side_lay.addWidget(btn)

        side_lay.addSpacing(15)
        
        h_sess = QHBoxLayout()
        btn_save = QPushButton("💾 Simpan")
        btn_save.setObjectName("OutlineBtn")
        btn_save.clicked.connect(self.save_session)
        
        btn_load = QPushButton("📂 Muat")
        btn_load.setObjectName("OutlineBtn")
        btn_load.clicked.connect(self.load_session)
        
        h_sess.addWidget(btn_save)
        h_sess.addWidget(btn_load)
        side_lay.addLayout(h_sess)

        side_lay.addStretch()
        
        self.stat_grp = QGroupBox("Pelacak Memori Proyek")
        slay = QVBoxLayout(self.stat_grp)
        slay.setContentsMargins(15, 30, 15, 15)
        
        self.grid_tracker = QGridLayout()
        self.grid_tracker.setSpacing(12)
        
        self.lbl_st_hs = QLabel("Hs: 0.0m")
        self.lbl_st_tp = QLabel("Tp: 8.0s")
        self.lbl_st_sed = QLabel("Sedimen: Kosong")
        self.lbl_st_tide = QLabel("Pasut: Kosong")
        
        trackers = [("🌊", self.lbl_st_hs), ("⏱", self.lbl_st_tp), ("🪨", self.lbl_st_sed), ("⚓", self.lbl_st_tide)]
        for i, (icon, lbl) in enumerate(trackers):
            lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 800;")
            self.grid_tracker.addWidget(QLabel(icon), i//2, (i%2)*2)
            self.grid_tracker.addWidget(lbl, i//2, (i%2)*2 + 1)
            
        slay.addLayout(self.grid_tracker)
        side_lay.addWidget(self.stat_grp)
        
        self.layout.addWidget(self.sidebar)

    def switch_page(self, index: int) -> None:
        if not self.modules_loaded: return
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_btns):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_global_state_ui(self, key: str = "") -> None:
        state = app_state.get_all()
        hs, tp = state.get('Hs', 0), state.get('Tp', 8)
        sed = state.get('sediment_xyz', "")
        tide = state.get('tide_bc', "")
        
        STYLE_LOCKED = "color: #42E695; font-size: 11px; font-weight: 800;"
        STYLE_EMPTY = "color: #475569; font-size: 11px; font-weight: 800;"
        
        if hs > 0:
            self.lbl_st_hs.setText(f"Hs: {hs:.2f}m"); self.lbl_st_hs.setStyleSheet(STYLE_LOCKED)
            self.lbl_st_tp.setText(f"Tp: {tp:.1f}s"); self.lbl_st_tp.setStyleSheet(STYLE_LOCKED)
        else:
            self.lbl_st_hs.setText("Hs: 0.0m"); self.lbl_st_hs.setStyleSheet(STYLE_EMPTY)
            
        if sed:
            self.lbl_st_sed.setText("Sedimen: OK"); self.lbl_st_sed.setStyleSheet(STYLE_LOCKED)
        else:
            self.lbl_st_sed.setText("Sedimen: Kosong"); self.lbl_st_sed.setStyleSheet(STYLE_EMPTY)
            
        if tide:
            self.lbl_st_tide.setText("Pasut: Terikat"); self.lbl_st_tide.setStyleSheet(STYLE_LOCKED)
        else:
            self.lbl_st_tide.setText("Pasut: Kosong"); self.lbl_st_tide.setStyleSheet(STYLE_EMPTY)

    def save_session(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Ekspor Sesi Riset Apex", "", "Sesi Apex (*.apex)")
        if path:
            if app_state.export_session(path):
                QMessageBox.information(self, "Sukses", "Sesi proyek berhasil diekspor secara permanen.")

    def load_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Impor Sesi Riset Apex", "", "Sesi Apex (*.apex)")
        if path:
            if app_state.import_session(path):
                QMessageBox.information(self, "Sukses", "Sesi proyek berhasil dipulihkan ke dalam memori.")

    def setup_interactive_guides(self) -> None:
        self.modul_guides = {
            0: [{'widget': getattr(self.modul1, 'web_map_era5', None), 'title': 'Langkah 1', 'desc': 'Tentukan area makro ERA5 untuk batas unduhan.'}],
            4: [{'widget': getattr(self.modul5, 'terminal', None), 'title': 'Pemantauan HPC', 'desc': 'Pantau jalannya kalkulasi C++ Deltares secara langsung di sini.'}]
        }

    def closeEvent(self, event) -> None:
        if hasattr(self, 'modul5') and hasattr(self.modul5, 'dimr_manager'):
            if self.modul5.dimr_manager.process.state() != QProcess.ProcessState.NotRunning:
                msg = QMessageBox.warning(self, "Simulasi Aktif", 
                    "Mesin komputasi Deltares masih berjalan di latar belakang.\nHarap hentikan simulasi (Abort) di Modul 5 sebelum menutup aplikasi.",
                    QMessageBox.StandardButton.Ok)
                event.ignore()
                return
                
        logger.info("Apex Hydro-Studio ditutup secara aman.")
        event.accept()

# ── 4. ENTERPRISE BOOTSTRAPPER ────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion") 
        
        # Standarisasi Fon agar konsisten di semua Sistem Operasi
        default_font = QFont("Segoe UI", 9)
        default_font.setStyleHint(QFont.StyleHint.SansSerif)
        app.setFont(default_font)
        
        splash_img = enterprise_path_resolver(os.path.join('assets', 'Apex Wave Studio.png'))
        if os.path.exists(splash_img):
            pixmap = QPixmap(splash_img).scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        else:
            splash = QSplashScreen(QPixmap(400, 400), Qt.WindowType.WindowStaysOnTopHint) 
            
        splash.show()
        app.processEvents()
        
        # Inisialisasi UI Utama
        window = ApexHydroStudioApp()
        window.build_heavy_modules(splash)
        window.show()
        splash.finish(window)
        
        sys.exit(app.exec())
    except Exception as fatal_e:
        # [FAIL-SAFE]: Menulis ke file secara langsung jika logging system belum sempat diinisialisasi
        err_msg = f"Aplikasi gagal melakukan booting: {str(fatal_e)}\n{traceback.format_exc()}"
        logger.critical(err_msg)
        
        try:
            with open("fatal_boot_error.txt", "w") as f:
                f.write(err_msg)
        except Exception:
            pass
            
        sys.exit(1)
