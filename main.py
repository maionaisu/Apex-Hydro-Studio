import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFrame, 
                             QStackedWidget, QLineEdit, QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QCursor

from utils.config import resource_path
from core.state_manager import app_state
from ui.views.modul1_era5 import Modul1ERA5
from ui.views.modul2_sediment import Modul2Sediment
from ui.views.modul3_tide import Modul3Tide
from ui.views.modul4_mesh import Modul4Mesh
from ui.views.modul5_execution import Modul5Execution
from ui.views.modul6_postproc import Modul6PostProc
from ui.components.core_widgets import InteractiveTourOverlay

class ApexHydroStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Apex Hydro-Studio: Enterprise Edition")
        self.setGeometry(50, 50, 1400, 900)
        
        # Load Theme
        theme_path = resource_path(os.path.join("assets", "theme.qss"))
        if os.path.exists(theme_path):
            with open(theme_path, "r") as f:
                self.setStyleSheet(f.read())
                
        icon_path = resource_path(os.path.join('assets', 'Apex Wave Studio.ico'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.main_w = QWidget()
        self.setCentralWidget(self.main_w)
        main_layout = QHBoxLayout(self.main_w)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.tour_overlay = InteractiveTourOverlay(self)
        
        self.init_sidebar(main_layout)
        
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background-color: #030712;")
        main_layout.addWidget(self.stacked_widget, stretch=1)

        # Build Modules
        self.modul1 = Modul1ERA5()
        self.modul2 = Modul2Sediment()
        self.modul3 = Modul3Tide()
        self.modul4 = Modul4Mesh()
        self.modul5 = Modul5Execution()
        self.modul6 = Modul6PostProc()
        self.stacked_widget.addWidget(self.modul1)
        self.stacked_widget.addWidget(self.modul2)
        self.stacked_widget.addWidget(self.modul3)
        self.stacked_widget.addWidget(self.modul4)
        self.stacked_widget.addWidget(self.modul5)
        self.stacked_widget.addWidget(self.modul6)

        # App state sync to UI
        app_state.state_updated.connect(self.update_global_state_ui)

        # Modul Guides (Initialized after all modules are built)
        self.modul_guides = {
            0: [
                {'widget': self.modul1.web_map_era5, 'title': 'Langkah 1: Peta Interaktif', 'desc': 'Gunakan Peta Interaktif ini untuk menggambar Bounding Box (Batas Ekstraksi). Gunakan toolbar di sebelah kiri peta.'},
                {'widget': self.modul1.tabs_aoi, 'title': 'Langkah 2: Panel Parameter', 'desc': 'Setelah menggambar, koordinat akan muncul di tab ini. Anda dapat berpindah ke "Manual Params" untuk mengubah titik koordinat N/S/E/W.'},
                {'widget': self.modul1.btn_dl_era5, 'title': 'Langkah 3: Unduh & Ekstrak', 'desc': 'Bila parameter selesai dikonfigurasi, klik panah Download ERA5. Xarray Worker akan mulai mengunduh di Background.'}
            ],
            1: [
                {'widget': self.modul2.btn_load_sediment, 'title': 'Langkah 1: Load Dataset', 'desc': 'Pilih data .csv / .xlsx pengamatan sedimen lapangan.'},
                {'widget': self.modul2.cmb_v_sediment, 'title': 'Langkah 2: Pilih Variabel Fisik', 'desc': 'Tentukan kolom di excel Anda yang merepresentasikan D50 atau Nilai Sedimen.'},
                {'widget': self.modul2.chk_ks_sediment, 'title': 'Langkah 3: Persamaan Nikuradse', 'desc': 'Centang ini jika Anda ingin mengkonversi D50 ke Kekasaran Pipa Nikuradse untuk Flow Model (Ks = 2.5D).'},
                {'widget': self.modul2.btn_run_sediment, 'title': 'Langkah 4: Proses Spasial', 'desc': 'Tekan Eksekusi. Sistem akan merender Heatmap spasial Delaunay 2D interpolasi ke dalam kanvas peta latar biru.'}
            ],
            2: [
                {'widget': self.modul3.btn_tide_f, 'title': 'Langkah 1: Load Tide', 'desc': 'Pilih file Time-Series pasang surut (Txt/CSV/Excel).'},
                {'widget': self.modul3.btn_ext, 'title': 'Langkah 2: Analisis LSQ', 'desc': 'LSHA Worker akan memisahkan gelombang kompleks menjadi konstanta harmonik seketika (M2, S2, K1, O1, dll).'},
                {'widget': self.modul3.btn_gen, 'title': 'Langkah 3: Tulis File Boundary', 'desc': 'File boundary condition (.bc) akan dihasilkan berdasarkan Amplitudo dan Phase hasil kalkulasi kotak-kotak di atas.'}
            ],
            3: [
                {'widget': self.modul4.gis_tabs_m, 'title': 'Langkah 1: Pratinjau Map', 'desc': 'Peta di sini menampilkan garis batas dan transect. Jika Anda ingin menyunting geometri, lihat panel kanan.'},
                {'widget': self.modul4.tabs_aoi, 'title': 'Langkah 2: Geometri Manual', 'desc': 'Ubah koordinat BBox atau letak Node Transek untuk Cross-Section di panel Segmented ini.'},
                {'widget': self.modul4.sld_max, 'title': 'Langkah 3: Resolusi Jaring', 'desc': 'Kunci kualitas model Anda: Resolusi Max untuk laut dalam, Min untuk area pantai. Perhatikan beban komputasi!'},
                {'widget': self.modul4.btn_mesh, 'title': 'Langkah 4: Kompilasi DIMR', 'desc': 'Tekan tombol Compile! Sistem akan merakit file MDU, MDW, dan XML Coupler untuk Flow-Wave secara paralel.'}
            ],
            4: [
                {'widget': self.modul5.terminal, 'title': 'Langkah 1: Monitor Terminal', 'desc': 'Jendela ini merekam output komputasi C++ secara Real-Time.'},
                {'widget': self.modul5.btn_run, 'title': 'Langkah 2: Run Engine', 'desc': 'Pilih file run_dimr.bat dari hasil Modul 4 dan tekan START. DFM akan mulai iterasi hidrodinamika numerik!'}
            ],
            5: [
                {'widget': self.modul6.web_map, 'title': 'Langkah 1: Visualisasi Interaktif', 'desc': 'Kanvas Map untuk merender animasi spatio-temporal dari output NetCDF.'},
                {'widget': self.modul6.cmb_var, 'title': 'Langkah 2: Dropdown Variabel', 'desc': 'Pilih paramater output yang ingin divisualisasikan (Hsig, ucx, taus).'},
                {'widget': self.modul6.btn_ren, 'title': 'Langkah 3: Tembakan Awal', 'desc': 'Setelah memilih Variabel, tekan Render Frame Awal untuk meload frame indeks 0.'},
                {'widget': self.modul6.sld_time, 'title': 'Langkah 4: Scrubber Waktu', 'desc': 'Geser-geser slider waktu ini untuk melihat perambatan gelombang dinamis dalam layer peta.'}
            ],
        }
        
        self.switch_page(0)

    def init_sidebar(self, layout):
        self.sidebar = QFrame()
        self.sidebar.setStyleSheet("background-color: #0B0F19; border-right: 1px solid #1E293B;")
        self.sidebar.setFixedWidth(280)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(20, 30, 20, 20)

        # Logo
        h_logo = QHBoxLayout()
        png_path = resource_path(os.path.join('assets', 'Apex Wave Studio.png'))
        if os.path.exists(png_path):
            lbl_logo = QLabel()
            lbl_logo.setPixmap(QPixmap(png_path).scaled(35, 35, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            h_logo.addWidget(lbl_logo)
            
        lbl_title = QLabel("APEX STUDIO")
        lbl_title.setStyleSheet("font-family: 'Orbitron', sans-serif; font-size: 20px; font-weight: 900; color: #F8FAFC; letter-spacing: 1px;")
        h_logo.addWidget(lbl_title)
        h_logo.addStretch()
        side_layout.addLayout(h_logo)
        side_layout.addSpacing(30)

        self.nav_btns = []
        labels = ["⛆  ERA5 Synthesizer", "▤  Sediment & Mangrove", "🌊  Tidal Harmonix", 
                  "⚙  DIMR Orchestrator", "🚀  Engine Execution", "📊  Post-Processing"]
                  
        for i, text in enumerate(labels):
            btn = QPushButton(text)
            btn.setObjectName("NavBtn")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda checked, idx=i: self.switch_page(idx))
            self.nav_btns.append(btn)
            side_layout.addWidget(btn)

        side_layout.addSpacing(20)
        self.btn_tips = QPushButton("💡 Tips & Guide")
        self.btn_tips.setObjectName("TipsBtn")
        self.btn_tips.clicked.connect(self.tour_overlay.start_tour)
        side_layout.addWidget(self.btn_tips)
        side_layout.addStretch()
        
        # State Container
        self.stat_grp = QGroupBox("Global Memory State Tracker")
        self.stat_grp.setStyleSheet("background-color: transparent; border: none; border-top: 1px solid #1E293B;")
        slay = QVBoxLayout(self.stat_grp)
        slay.setContentsMargins(0, 15, 0, 0)
        slay.setSpacing(10)
        
        epsg_lay = QHBoxLayout()
        lbl_epsg = QLabel("📍 UTM EPSG:")
        lbl_epsg.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 9pt;")
        self.inp_epsg = QLineEdit(app_state.get('EPSG'))
        self.inp_epsg.textChanged.connect(lambda t: app_state.update('EPSG', t.strip()))
        epsg_lay.addWidget(lbl_epsg)
        epsg_lay.addWidget(self.inp_epsg)
        slay.addLayout(epsg_lay)

        # Status Grid layout
        ind_grid = QGridLayout()
        ind_grid.setContentsMargins(5, 5, 5, 5)
        ind_grid.setSpacing(12)
        
        self.lbl_state_he = QLabel("Hs: 0.0m")
        self.lbl_state_doc = QLabel("DoC: 0.0m")
        self.lbl_state_sed = QLabel("Sed: None")
        self.lbl_state_tide = QLabel("Bnd: None")
        
        indicators = [
            ("🌊", self.lbl_state_he),
            ("⏬", self.lbl_state_doc),
            ("🪨", self.lbl_state_sed),
            ("⏱", self.lbl_state_tide)
        ]
        
        for i, (icon, lbl) in enumerate(indicators):
            lbl.setStyleSheet("color: #64748B; font-size: 9pt; font-weight: 600;")
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size: 11pt;")
            ind_grid.addWidget(icon_lbl, i//2, (i%2)*2)
            ind_grid.addWidget(lbl, i//2, (i%2)*2 + 1)
        
        slay.addLayout(ind_grid)
        side_layout.addWidget(self.stat_grp)
        layout.addWidget(self.sidebar)


    def switch_page(self, index):
        if index < self.stacked_widget.count():
            self.stacked_widget.setCurrentIndex(index)
            # Update contextual tips
            if index in self.modul_guides:
                self.tour_overlay.set_steps(self.modul_guides[index])
                
        for i, btn in enumerate(self.nav_btns):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_global_state_ui(self):
        hs = app_state.get('Hs', 0)
        doc = app_state.get('DoC', 0)
        sed = app_state.get('sediment_xyz', "")
        tide = app_state.get('tide_bc', "")
        
        if hs > 0: 
            self.lbl_state_he.setText(f"Hs: {hs:.1f}m | Tp: {app_state.get('Tp', 8):.1f}s")
            self.lbl_state_he.setStyleSheet("color: #10B981; font-size: 9pt; font-weight: bold;")
        if doc > 0: 
            self.lbl_state_doc.setText(f"DoC: {doc:.1f}m")
            self.lbl_state_doc.setStyleSheet("color: #10B981; font-size: 9pt; font-weight: bold;")
        if sed: 
            self.lbl_state_sed.setText("Mangrove/Sed: Aktif")
            self.lbl_state_sed.setStyleSheet("color: #10B981; font-size: 9pt; font-weight: bold;")
        if tide: 
            self.lbl_state_tide.setText("Tide Bnd: Astronomic")
            self.lbl_state_tide.setStyleSheet("color: #10B981; font-size: 9pt; font-weight: bold;")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ApexHydroStudioApp()
    window.show()
    sys.exit(app.exec())
