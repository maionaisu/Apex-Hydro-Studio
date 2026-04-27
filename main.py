# ==============================================================================
# APEX NEXUS TIER-0: MASTER ENTRY POINT (APPLICATION SHELL)
# ==============================================================================
import sys
import os
import logging
import traceback

# ── 1. EARLY APPLICATION BOOTSTRAP (ANTI-CRASH GUARD) ────────────────────────
# [CRITICAL FIX]: PyQt6 WAJIB menginisialisasi QApplication sebelum modul C++
# atau file python lain (seperti state_manager) yang memuat QObject diimpor!
from PyQt6.QtWidgets import QApplication, QMessageBox

# [WEB-ENGINE BUG FIX]: Pustaka QtWebEngineWidgets mutlak harus diimpor 
# mendahului penciptaan instance QApplication untuk mengaktifkan konteks OpenGL.
from PyQt6.QtWebEngineWidgets import QWebEngineView

if not QApplication.instance():
    # Mengamankan OpenGL Konteks WebEngine mendahului QApplication
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()

# ── 2. ENTERPRISE PATH RESOLUTION & ENVIRONMENT GUARD ─────────────────────────
def get_app_root() -> str:
    """O(1) Root Path Resolver. Mencegah Fatal Data-Loss Bug pada PyInstaller."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def enterprise_path_resolver(relative_path: str) -> str:
    """Menjamin aset UI (QSS/Ico/HTML) selalu ditemukan dari paket internal kompilasi."""
    try:
        base_path = sys._MEIPASS 
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

APP_ROOT = get_app_root()
EXPORT_DIR = os.path.join(APP_ROOT, 'Apex_Data_Exports')
os.makedirs(EXPORT_DIR, exist_ok=True)
log_file = os.path.join(EXPORT_DIR, 'system_crash.log')

# Inisiasi Logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'), 
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ApexMaster")

# ── 3. GLOBAL EXCEPTION HANDLER ───────────────────────────────────────────────
def global_exception_handler(exc_type, exc_value, exc_traceback):
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

# ── 4. DEPENDENCY & MODULE IMPORTS (Aman, karena App sudah hidup) ────────────
try:
    from utils.config import get_project_dirs, cleanup_temp_buffer
    get_project_dirs()
    cleanup_temp_buffer() 
except ImportError:
    logger.warning("Fungsi init direktori tidak ditemukan, mengabaikan inisialisasi...")
except Exception as e:
    logger.error(f"Gagal menginisialisasi direktori proyek: {e}")

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFrame, 
                             QStackedWidget, QGridLayout, 
                             QComboBox, QFileDialog, QSplashScreen)
from PyQt6.QtCore import Qt, QProcess, QSettings, QSharedMemory
from PyQt6.QtGui import QIcon, QPixmap, QCursor, QColor, QFont

from core.state_manager import app_state

from ui.views.modul1_era5 import Modul1ERA5
from ui.views.modul2_sediment import Modul2Sediment
from ui.views.modul3_tide import Modul3Tide
from ui.views.modul4_mesh import Modul4Mesh
from ui.views.modul5_execution import Modul5Execution
from ui.views.modul6_postproc import Modul6PostProc
from ui.components.core_widgets import InteractiveTourOverlay, CardWidget

# ── 5. CORE APPLICATION ARCHITECTURE ──────────────────────────────────────────
class ApexHydroStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Apex Hydro-Studio")
        self.setMinimumSize(1400, 850)
        
        # Window State Persistence
        self.settings = QSettings('ApexStudio', 'MainWindow')
        if self.settings.value("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        if self.settings.value("windowState"):
            self.restoreState(self.settings.value("windowState"))
        
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

    def _safe_load_module(self, module_class, module_name: str, splash: QSplashScreen, splash_text: str):
        """[TIER-0 SAFEGUARD] Mengisolasi crash pada satu modul agar tidak meruntuhkan seluruh aplikasi."""
        splash.showMessage(splash_text, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
        QApplication.processEvents()
        
        try:
            return module_class()
        except Exception as e:
            err_msg = f"Gagal menginisiasi {module_name}:\n{str(e)}\n\n{traceback.format_exc()}"
            logger.error(err_msg)
            
            # Buat UI Pengganti agar aplikasi tetap bisa beroperasi (Graceful Degradation)
            err_widget = QWidget()
            err_layout = QVBoxLayout(err_widget)
            err_box = CardWidget(f"⚠️ Kegagalan Modul: {module_name}")
            err_lbl = QLabel(f"Modul ini dinonaktifkan sementara karena galat sistem:\n\n{str(e)}\n\nPeriksa kelengkapan Python library Anda (xarray, netcdf4, dask, dll).")
            err_lbl.setStyleSheet("color: #FC3F4D; font-size: 13px; font-weight: bold; border: none;")
            err_lbl.setWordWrap(True)
            err_box.add_widget(err_lbl)
            err_layout.addWidget(err_box)
            err_layout.addStretch()
            return err_widget

    def build_heavy_modules(self, splash: QSplashScreen):
        logger.info("Membangun arsitektur modul D-Flow FM & SWAN...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            self.modul1 = self._safe_load_module(Modul1ERA5, "Modul 1 (ERA5)", splash, "Memuat Modul 1: Sintesis Data ERA5...")
            self.modul2 = self._safe_load_module(Modul2Sediment, "Modul 2 (Sediment)", splash, "Memuat Modul 2: Pemetaan Morfologi Sedimen...")
            self.modul3 = self._safe_load_module(Modul3Tide, "Modul 3 (Tidal)", splash, "Memuat Modul 3: Harmonik Pasang Surut...")
            self.modul4 = self._safe_load_module(Modul4Mesh, "Modul 4 (Mesh)", splash, "Memuat Modul 4: Pembangkit Mesh Digital Twin...")
            self.modul5 = self._safe_load_module(Modul5Execution, "Modul 5 (DIMR)", splash, "Memuat Modul 5: Eksekusi HPC DIMR...")
            self.modul6 = self._safe_load_module(Modul6PostProc, "Modul 6 (Post-Proc)", splash, "Memuat Modul 6: Pasca-Pemrosesan & Validasi...")
            
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
            QApplication.restoreOverrideCursor()

    def init_sidebar(self) -> None:
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarFrame") 
        self.sidebar.setStyleSheet("QFrame#SidebarFrame { background-color: #121826; border-right: 1px solid #1E293B; }")
        self.sidebar.setFixedWidth(290)
        
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(22, 25, 22, 25)
        side_lay.setSpacing(8)

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
        side_lay.addSpacing(25)
        
        lbl_hpc = QLabel("BACKEND KOMPUTASI:")
        lbl_hpc.setStyleSheet("color: #6B7280; font-size: 10px; font-weight: 800;")
        side_lay.addWidget(lbl_hpc)
        
        self.cmb_backend = QComboBox()
        self.cmb_backend.addItems(["🖥️ CPU (Bawaan)", "🚀 CUDA (GPU)", "🔥 HIBRIDA"])
        self.cmb_backend.setStyleSheet("""
            QComboBox { background-color: #1F2227; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px 14px; color: #FFFFFF; font-weight: bold; }
            QComboBox::drop-down { border: none; }
        """)
        self.cmb_backend.currentTextChanged.connect(lambda t: app_state.update('compute_backend', t))
        side_lay.addWidget(self.cmb_backend)
        side_lay.addSpacing(20)

        self.style_nav_active = """
            QPushButton { background-color: #595FF7; color: #FFFFFF; border: none; border-radius: 10px; padding: 14px 18px; font-weight: 900; font-size: 14px; text-align: left; }
        """
        self.style_nav_inactive = """
            QPushButton { background-color: transparent; color: #9CA3AF; border: none; border-radius: 10px; padding: 14px 18px; font-weight: 800; font-size: 14px; text-align: left; }
            QPushButton:hover { background-color: #2D3139; color: #FFFFFF; }
        """

        self.nav_btns = []
        nav_items = [
            ("⛆   Sintesis ERA5", 0), 
            ("▤   Medan Sedimen", 1), 
            ("🌊   Harmonik Pasut", 2), 
            ("⚙   Orkestrator DIMR", 3), 
            ("🚀   Eksekusi", 4), 
            ("📊   Lab Validasi", 5)
        ]
        
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(self.style_nav_inactive)
            btn.clicked.connect(lambda checked, i=idx: self.switch_page(i))
            self.nav_btns.append(btn)
            side_lay.addWidget(btn)

        side_lay.addSpacing(20)
        
        h_sess = QHBoxLayout()
        btn_save = QPushButton("💾 Simpan")
        btn_save.setStyleSheet("background-color: transparent; color: #8FC9DC; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px; font-weight: 800;")
        btn_save.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_save.clicked.connect(self.save_session)
        
        btn_load = QPushButton("📂 Muat")
        btn_load.setStyleSheet("background-color: transparent; color: #F7C159; border: 1px solid #3A3F4A; border-radius: 8px; padding: 10px; font-weight: 800;")
        btn_load.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_load.clicked.connect(self.load_session)
        
        h_sess.addWidget(btn_save)
        h_sess.addWidget(btn_load)
        side_lay.addLayout(h_sess)

        side_lay.addStretch()
        
        self.stat_grp = CardWidget("Pelacak Memori Proyek")
        self.stat_grp.setStyleSheet("QFrame#CardWidget { background-color: #1E2128; border: 1px solid #3A3F4A; border-radius: 12px; }")
        self.grid_tracker = QGridLayout()
        self.grid_tracker.setSpacing(12)
        
        self.lbl_st_hs = QLabel("Hs: 0.0m")
        self.lbl_st_tp = QLabel("Tp: 8.0s")
        self.lbl_st_sed = QLabel("Sedimen: Kosong")
        self.lbl_st_tide = QLabel("Pasut: Kosong")
        
        trackers = [("🌊", self.lbl_st_hs), ("⏱", self.lbl_st_tp), ("🪨", self.lbl_st_sed), ("⚓", self.lbl_st_tide)]
        for i, (icon, lbl) in enumerate(trackers):
            lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 800; border: none;")
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("border: none;")
            self.grid_tracker.addWidget(icon_lbl, i//2, (i%2)*2)
            self.grid_tracker.addWidget(lbl, i//2, (i%2)*2 + 1)
            
        self.stat_grp.add_layout(self.grid_tracker)
        side_lay.addWidget(self.stat_grp)
        
        self.layout.addWidget(self.sidebar)

    def switch_page(self, index: int) -> None:
        if not self.modules_loaded: return
        self.stacked_widget.setCurrentIndex(index)
        
        for i, btn in enumerate(self.nav_btns):
            if i == index:
                btn.setStyleSheet(self.style_nav_active)
            else:
                btn.setStyleSheet(self.style_nav_inactive)

    def update_global_state_ui(self, key: str = "") -> None:
        state = app_state.get_all()
        hs, tp = state.get('Hs', 0), state.get('Tp', 8)
        sed = state.get('sediment_xyz', "")
        tide = state.get('tide_bc', "")
        
        STYLE_LOCKED = "color: #42E695; font-size: 11px; font-weight: 800; border: none;"
        STYLE_EMPTY = "color: #475569; font-size: 11px; font-weight: 800; border: none;"
        
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
        path, _ = QFileDialog.getSaveFileName(self, "Ekspor Sesi Riset Apex", "", "Project Apex (*.apex)")
        if path:
            if app_state.export_session(path):
                QMessageBox.information(self, "Sukses", "Proyek berhasil diekspor ke dalam memori.")

    def load_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Impor Sesi Riset Apex", "", "Project Apex (*.apex)")
        if path:
            if app_state.import_session(path):
                QMessageBox.information(self, "Sukses", "Proyek berhasil dimuat ke dalam memori.")

    def setup_interactive_guides(self) -> None:
        if isinstance(self.modul1, Modul1ERA5) and isinstance(self.modul5, Modul5Execution):
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
        
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        try:
            cleanup_temp_buffer()
        except Exception:
            pass
            
        logger.info("Apex Hydro-Studio ditutup secara aman.")
        event.accept()

# ── 6. ENTERPRISE BOOTSTRAPPER ────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        app.setStyle("Fusion") 
        
        default_font = QFont("Segoe UI", 9)
        default_font.setStyleHint(QFont.StyleHint.SansSerif)
        app.setFont(default_font)
        
        # [ENTERPRISE FIX]: Single-Instance Application Lock 
        shared_memory = QSharedMemory("ApexNexus_Enterprise_Lock_v18")
        if shared_memory.attach():
            QMessageBox.critical(None, "Akses Ditolak", 
                "Apex Hydro-Studio sedang berjalan. Anda tidak dapat membuka lebih dari satu instansi aplikasi pada waktu bersamaan.")
            sys.exit(1)
            
        if not shared_memory.create(1):
            QMessageBox.critical(None, "Sistem Galat", "Gagal menciptakan segmen Shared Memory untuk instansi tunggal.")
            sys.exit(1)
        
        splash_img = enterprise_path_resolver(os.path.join('assets', 'Apex Wave Studio.png'))
        if os.path.exists(splash_img):
            pixmap = QPixmap(splash_img).scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        else:
            splash = QSplashScreen(QPixmap(400, 400), Qt.WindowType.WindowStaysOnTopHint) 
            
        splash.show()
        app.processEvents()
        
        window = ApexHydroStudioApp()
        window.build_heavy_modules(splash)
        window.show()
        splash.finish(window)
        
        sys.exit(app.exec())
        
    except Exception as fatal_e:
        err_msg = f"Aplikasi gagal melakukan booting: {str(fatal_e)}\n{traceback.format_exc()}"
        logger.critical(err_msg)
        
        try:
            with open("fatal_boot_error.txt", "w") as f:
                f.write(err_msg)
        except Exception:
            pass
            
        sys.exit(1)
