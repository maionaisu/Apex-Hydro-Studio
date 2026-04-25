# ==============================================================================
# APEX NEXUS TIER-0: MASTER ENTRY POINT (APPLICATION SHELL)
# ==============================================================================
import sys
import os
import logging
import traceback

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFrame, 
                             QStackedWidget, QGridLayout, 
                             QMessageBox, QComboBox, QFileDialog, QSplashScreen, QGroupBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QCursor, QColor

# ── ENTERPRISE PATH RESOLUTION ────────────────────────────────────────────────
def enterprise_path_resolver(relative_path: str) -> str:
    """
    [TIER-0 SAFEGUARD] O(1) Absolute Path Resolver.
    Menjamin aset selalu ditemukan baik saat dijalankan via Python IDE, 
    maupun setelah di-compile menggunakan PyInstaller (.exe).
    """
    try:
        base_path = sys._MEIPASS # PyInstaller temp folder
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

try:
    from utils.config import resource_path, get_project_dirs
except ImportError:
    resource_path = enterprise_path_resolver
    def get_project_dirs(): pass

# [HARDENING]: Inisialisasi Direktori Utama sebelum modul dimuat
try:
    get_project_dirs()
except Exception as e:
    print(f"Warning: Failed to initialize project directories: {e}")

from core.state_manager import app_state

# Import View Modules
from ui.views.modul1_era5 import Modul1ERA5
from ui.views.modul2_sediment import Modul2Sediment
from ui.views.modul3_tide import Modul3Tide
from ui.views.modul4_mesh import Modul4Mesh
from ui.views.modul5_execution import Modul5Execution
from ui.views.modul6_postproc import Modul6PostProc
from ui.components.core_widgets import InteractiveTourOverlay

# ── 1. ENTERPRISE LOGGING & EXCEPTION HANDLING ────────────────────────────────
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(APP_ROOT, 'Apex_Data_Exports')
os.makedirs(EXPORT_DIR, exist_ok=True)
log_file = os.path.join(EXPORT_DIR, 'system_crash.log')

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'), 
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ApexMaster")

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """[TIER-0 SAFEGUARD] Menangkap error fatal agar aplikasi tidak 'Silent Crash'."""
    logger.critical("UNCAUGHT FATAL EXCEPTION", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Pastikan QApplication ada sebelum memanggil QMessageBox
    if QApplication.instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Apex Hydro-Studio : Fatal System Error")
        msg.setText("Terjadi galat fatal pada kernel aplikasi.")
        msg.setInformativeText(f"Log error telah disimpan di:\n{log_file}")
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        msg.setDetailedText("".join(tb_lines))
        msg.setStyleSheet("QLabel { color: #000; background-color: transparent; }") 
        msg.exec()
    else:
        print("FATAL ERROR (UI Dead):", exc_value)

sys.excepthook = global_exception_handler

# ── 2. CORE APPLICATION ARCHITECTURE ──────────────────────────────────────────
class ApexHydroStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Apex Hydro-Studio: Enterprise Analytics (v18.0)")
        self.setMinimumSize(1450, 950)
        
        # Load Icon
        icon_path = enterprise_path_resolver(os.path.join('assets', 'Apex Wave Studio.ico'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # ── LOAD THEME ────────────────────────────────────────────────────────
        theme_path = enterprise_path_resolver(os.path.join("assets", "theme.qss"))
        if os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding='utf-8') as f:
                    self.setStyleSheet(f.read())
            except Exception as e:
                logger.error(f"Failed to load QSS Theme: {e}")
        else:
            logger.warning(f"Theme file missing at: {theme_path}")
                
        # ── CORE LAYOUT ───────────────────────────────────────────────────────
        self.main_w = QWidget()
        self.main_w.setObjectName("MainWidget")
        self.setCentralWidget(self.main_w)
        
        self.layout = QHBoxLayout(self.main_w)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # ── INITIALIZE COMPONENTS ────────────────────────────────────────────
        self.init_sidebar()
        
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget, stretch=1)

        # Modul akan diload secara bertahap oleh Splash Screen (Delayed Init)
        self.modules_loaded = False

    def build_heavy_modules(self, splash: QSplashScreen):
        """[PERFORMANCE OPTIMIZATION] Memuat modul berat dengan indikator Splash Screen."""
        logger.info("Membangun arsitektur modul D-Flow FM & SWAN...")
        
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

        splash.showMessage("Memuat Modul 5: DIMR HPC Execution...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
        self.modul5 = Modul5Execution()
        QApplication.processEvents()

        splash.showMessage("Memuat Modul 6: Post-Processing & Validasi...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
        self.modul6 = Modul6PostProc()
        QApplication.processEvents()
        
        self.modules = [self.modul1, self.modul2, self.modul3, self.modul4, self.modul5, self.modul6]
        for m in self.modules:
            self.stacked_widget.addWidget(m)

        # Sinkronisasi Antar Modul & State Manager
        app_state.state_updated.connect(self.update_global_state_ui)
        app_state.bulk_state_updated.connect(self.update_global_state_ui)

        self.tour_overlay = InteractiveTourOverlay(self)
        self.setup_interactive_guides()
        
        self.switch_page(0)
        self.modules_loaded = True
        logger.info("Apex Hydro-Studio siap untuk simulasi riset.")

    def init_sidebar(self) -> None:
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarFrame") 
        self.sidebar.setFixedWidth(290)
        
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(22, 25, 22, 25)
        side_lay.setSpacing(10)

        # Logo & Brand
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
        
        # HPC Selector
        lbl_hpc = QLabel("COMPUTE BACKEND:")
        lbl_hpc.setStyleSheet("color: #6B7280; font-size: 10px; font-weight: 800;")
        side_lay.addWidget(lbl_hpc)
        
        self.cmb_backend = QComboBox()
        self.cmb_backend.addItems(["🖥️ CPU (Default)", "🚀 CUDA (GPU)", "🔥 HYBRID"])
        self.cmb_backend.currentTextChanged.connect(lambda t: app_state.update('compute_backend', t))
        side_lay.addWidget(self.cmb_backend)
        side_lay.addSpacing(15)

        # Navigation
        self.nav_btns = []
        nav_items = [
            ("⛆  ERA5 Synthesizer", 0), 
            ("▤  Sediments Field", 1), 
            ("🌊  Tidal Harmonix", 2), 
            ("⚙  DIMR Orchestrator", 3), 
            ("🚀  HPC Execution", 4), 
            ("📊  Validation Lab", 5)
        ]
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("NavBtn")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda checked, i=idx: self.switch_page(i))
            self.nav_btns.append(btn)
            side_lay.addWidget(btn)

        side_lay.addSpacing(15)
        
        # Session Control
        h_sess = QHBoxLayout()
        btn_save = QPushButton("💾 Save")
        btn_save.setObjectName("OutlineBtn")
        btn_save.clicked.connect(self.save_session)
        
        btn_load = QPushButton("📂 Load")
        btn_load.setObjectName("OutlineBtn")
        btn_load.clicked.connect(self.load_session)
        
        h_sess.addWidget(btn_save)
        h_sess.addWidget(btn_load)
        side_lay.addLayout(h_sess)

        side_lay.addStretch()
        
        # ── LIVE STATE TRACKER (GLOBAL MEMORY) ──────────────────────────────
        self.stat_grp = QGroupBox("Project Memory Tracker")
        slay = QVBoxLayout(self.stat_grp)
        slay.setContentsMargins(15, 30, 15, 15)
        
        self.grid_tracker = QGridLayout()
        self.grid_tracker.setSpacing(12)
        
        self.lbl_st_hs = QLabel("Hs: 0.0m")
        self.lbl_st_tp = QLabel("Tp: 8.0s")
        self.lbl_st_sed = QLabel("Sed: None")
        self.lbl_st_tide = QLabel("Tide: No BC")
        
        trackers = [("🌊", self.lbl_st_hs), ("⏱", self.lbl_st_tp), ("🪨", self.lbl_st_sed), ("⚓", self.lbl_st_tide)]
        for i, (icon, lbl) in enumerate(trackers):
            lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 800;")
            self.grid_tracker.addWidget(QLabel(icon), i//2, (i%2)*2)
            self.grid_tracker.addWidget(lbl, i//2, (i%2)*2 + 1)
            
        slay.addLayout(self.grid_tracker)
        side_lay.addWidget(self.stat_grp)
        
        self.layout.addWidget(self.sidebar)

    def switch_page(self, index: int) -> None:
        """Navigasi antar modul dengan visual feedback pada sidebar."""
        if not self.modules_loaded: return
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_btns):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_global_state_ui(self, key: str = "") -> None:
        """Sinkronisasi Mutlak: Menjamin Sidebar selalu mencerminkan Global RAM."""
        state = app_state.get_all()
        hs, tp = state.get('Hs', 0), state.get('Tp', 8)
        sed = state.get('sediment_xyz', "")
        tide = state.get('tide_bc', "")
        
        STYLE_LOCKED = "color: #42E695; font-size: 11px; font-weight: 800;" # Teal Green
        STYLE_EMPTY = "color: #475569; font-size: 11px; font-weight: 800;" # Muted Slate
        
        if hs > 0:
            self.lbl_st_hs.setText(f"Hs: {hs:.2f}m")
            self.lbl_st_hs.setStyleSheet(STYLE_LOCKED)
            self.lbl_st_tp.setText(f"Tp: {tp:.1f}s")
            self.lbl_st_tp.setStyleSheet(STYLE_LOCKED)
        else:
            self.lbl_st_hs.setText("Hs: 0.0m")
            self.lbl_st_hs.setStyleSheet(STYLE_EMPTY)
            
        if sed:
            self.lbl_st_sed.setText("Roughness: OK")
            self.lbl_st_sed.setStyleSheet(STYLE_LOCKED)
        else:
            self.lbl_st_sed.setText("Roughness: None")
            self.lbl_st_sed.setStyleSheet(STYLE_EMPTY)
            
        if tide:
            self.lbl_st_tide.setText("Tide: Linked")
            self.lbl_st_tide.setStyleSheet(STYLE_LOCKED)
        else:
            self.lbl_st_tide.setText("Tide: No BC")
            self.lbl_st_tide.setStyleSheet(STYLE_EMPTY)

    def save_session(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Apex Research Session", "", "Apex Session (*.apex)")
        if path:
            if app_state.export_session(path):
                QMessageBox.information(self, "Success", "Sesi proyek berhasil diekspor ke disk.")

    def load_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Apex Research Session", "", "Apex Session (*.apex)")
        if path:
            if app_state.import_session(path):
                QMessageBox.information(self, "Success", "Sesi proyek berhasil dipulihkan.")

    def setup_interactive_guides(self) -> None:
        """Konfigurasi tutorial interaktif per modul."""
        self.modul_guides = {
            0: [{'widget': getattr(self.modul1, 'web_map_era5', None), 'title': 'Langkah 1', 'desc': 'Tentukan area makro ERA5.'}],
            4: [{'widget': getattr(self.modul5, 'terminal', None), 'title': 'Monitoring', 'desc': 'Pantau log C++ Deltares di sini.'}]
        }

    def closeEvent(self, event) -> None:
        """[TIER-0 SECURITY] Mencegah penutupan aplikasi saat simulasi C++ masih menyala di memori."""
        if hasattr(self, 'modul5') and hasattr(self.modul5, 'dimr_manager'):
            if self.modul5.dimr_manager.process.state() != 0:
                msg = QMessageBox.warning(self, "Simulasi Aktif", 
                    "Mesin Deltares sedang berjalan di latar belakang. Hentikan simulasi di Modul 5 sebelum keluar.",
                    QMessageBox.StandardButton.Ok)
                event.ignore()
                return
                
        logger.info("Apex Hydro-Studio ditutup secara aman.")
        event.accept()

# ── 3. ENTERPRISE BOOTSTRAPPER ────────────────────────────────────────────────
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    
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
