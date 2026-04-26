# ==============================================================================
# APEX NEXUS TIER-0: MODUL 2 - SPATIAL SEDIMENT & MANGROVE (FLUID UI)
# ==============================================================================
import os
import gc
import shutil
import logging
import traceback
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QComboBox, QCheckBox, QLabel, QTextEdit, 
                             QFileDialog, QSplitter, QTabWidget, QFrame, 
                             QMessageBox, QSpinBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

# Integrasi Enterprise Flexbox
from ui.components.core_widgets import FlexScrollArea, CardWidget, ModernButton
from workers.sediment_worker import SedimentWorker
from core.state_manager import app_state

logger = logging.getLogger(__name__)

class Modul2Sediment(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_data = {
            'sediment': {'df': None, 'file': None, 'boundary_file': None},
            'mangrove': {'df': None, 'file': None, 'boundary_file': None},
            'submerged': {'df': None, 'file': None, 'boundary_file': None}
        }
        self.current_plot_path = None
        self.setup_ui()

    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # --- HEADER ---
        head = QVBoxLayout()
        title_container = QFrame()
        title_container.setStyleSheet("background-color: #1E2128; border: 1px solid #3A3F4A; border-radius: 8px;")
        tc_layout = QVBoxLayout(title_container)
        tc_layout.setContentsMargins(16, 12, 16, 12)
        tc_layout.setSpacing(4)
        
        t = QLabel("Spatial Sediments & Coastal Friction")
        t.setStyleSheet("font-size: 20px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px; border: none;")
        
        d = QLabel(
            "<div style='text-align: justify; line-height: 1.4;'>"
            "Sistem pemetaan tingkat lanjut untuk distribusi densitas spasial Trachytope pada vegetasi Mangrove, Lamun, "
            "dan Terumbu Karang. Mendukung Kriging, Filled Contours HD, dan <b>Land Boundary Masking</b> untuk memotong "
            "data spasial agar menyesuaikan garis daratan secara otomatis."
            "</div>"
        )
        d.setStyleSheet("color: #9CA3AF; font-size: 12px; border: none;")
        d.setWordWrap(True)
        
        tc_layout.addWidget(t)
        tc_layout.addWidget(d)
        head.addWidget(title_container)
        main_layout.addLayout(head)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setStyleSheet("QSplitter::handle { background-color: transparent; width: 12px; }")

        # ==============================================================================
        # KIRI: KONTROL TABS (DENGAN FLEX SCROLL AREA)
        # ==============================================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3A3F4A; border-radius: 12px; background: transparent; }
            QTabBar::tab { background: #1F2227; color: #9CA3AF; padding: 12px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; font-weight: 800; }
            QTabBar::tab:selected { background: #2D3139; color: #8FC9DC; border-bottom: 3px solid #8FC9DC; }
        """)
        
        self.tab_sediment = FlexScrollArea()
        self.build_tab_ui(self.tab_sediment, 'sediment', "📂 Load Survei Sedimen (.csv/.xlsx)", True)
        self.tabs.addTab(self.tab_sediment, "1. Sedimen (Nikuradse)")

        self.tab_mangrove = FlexScrollArea()
        self.build_tab_ui(self.tab_mangrove, 'mangrove', "🌲 Load Vegetasi Mangrove", False)
        self.tabs.addTab(self.tab_mangrove, "2. Mangrove")

        self.tab_submerged = FlexScrollArea()
        self.build_tab_ui(self.tab_submerged, 'submerged', "🪸 Load Submerged (.csv)", False)
        self.tabs.addTab(self.tab_submerged, "3. Ekosistem Bawah Air")

        left_layout.addWidget(self.tabs)
        main_splitter.addWidget(left_widget)

        # ==============================================================================
        # KANAN: VISUALISASI & LOG TERMINAL (VERTICAL SPLITTER)
        # ==============================================================================
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setChildrenCollapsible(False)
        right_splitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 12px; }")
        
        top_wrap = QWidget()
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_sed_viz = QLabel("Plot Spasial (Filled Contours) akan di-render di sini.")
        self.lbl_sed_viz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sed_viz.setStyleSheet("border: 2px dashed #3A3F4A; background-color:#1E2128; border-radius: 12px; color: #6B7280; font-weight: bold; font-size: 16px;")
        
        self.btn_export_png = ModernButton("💾 Export HD Image (.png)", "outline")
        self.btn_export_png.setEnabled(False)
        self.btn_export_png.clicked.connect(self.export_current_plot)
        
        tl.addWidget(self.lbl_sed_viz, stretch=1)
        tl.addWidget(self.btn_export_png)
        right_splitter.addWidget(top_wrap)

        bot_wrap = QWidget()
        bl = QVBoxLayout(bot_wrap)
        bl.setContentsMargins(0, 0, 0, 0)
        
        term_lbl = QLabel("Terminal Spasial (System Log):")
        term_lbl.setStyleSheet("font-weight:900; color:#8FC9DC; font-size: 14px;")
        bl.addWidget(term_lbl)
        
        self.log_sed = QTextEdit()
        self.log_sed.setReadOnly(True)
        self.log_sed.setObjectName("TerminalOutput")
        self.log_sed.setMinimumHeight(150)
        bl.addWidget(self.log_sed)
        
        right_splitter.addWidget(bot_wrap)
        right_splitter.setSizes([600, 200]) 
        
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([450, 650])
        main_layout.addWidget(main_splitter)

    def build_tab_ui(self, scroll_area: FlexScrollArea, mode_type: str, btn_text: str, show_ks: bool) -> None:
        # 1. Dataset Loader Card
        grp1 = CardWidget("A. Dataset Survei Lapangan")
        
        btn_load = ModernButton(btn_text, "outline")
        btn_load.clicked.connect(lambda checked, m=mode_type: self.load_file(m))
        grp1.add_widget(btn_load)
        
        lbl_info = QLabel("<div style='text-align: justify; line-height: 1.5;'>Format Input: Kolom X (Longitude), Y (Latitude), dan Target (Z/D50).</div>")
        lbl_info.setStyleSheet("color: #9CA3AF; font-size: 12px; border: none;")
        lbl_info.setWordWrap(True)
        grp1.add_widget(lbl_info)
        scroll_area.add_widget(grp1)
        
        # 2. Boundary / Masking Card (NEW)
        grp3 = CardWidget("B. Land Boundary / Masking (Opsional)")
        btn_load_bnd = ModernButton("🗺️ Load AOI Poligon (.shp / .geojson)", "outline")
        btn_load_bnd.clicked.connect(lambda checked, m=mode_type: self.load_boundary_file(m))
        grp3.add_widget(btn_load_bnd)
        
        lbl_bnd = QLabel("Gunakan file SHP Polygon area lautan (AOI) Anda untuk memotong kontur agar tidak masuk ke daratan.")
        lbl_bnd.setStyleSheet("color: #9CA3AF; font-size: 11px; border: none;")
        lbl_bnd.setWordWrap(True)
        grp3.add_widget(lbl_bnd)
        scroll_area.add_widget(grp3)
        
        # 3. Mapper Configuration Card
        grp2 = CardWidget("C. Konfigurasi Interpolasi (Kriging)")
        g2 = QFormLayout()
        g2.setHorizontalSpacing(15); g2.setVerticalSpacing(12)   
        
        label_style = "QLabel { color: #CBD5E1; font-weight: bold; font-size: 12px; border: none; }"
        
        cmb_method = QComboBox()
        cmb_method.addItems([
            "Ordinary Kriging (Spherical)",
            "Ordinary Kriging (Exponential)",
            "Ordinary Kriging (Gaussian)",
            "Delaunay Triangulation (Fast Linear)"
        ])
        
        cmb_sheet = QComboBox()
        cmb_sheet.setEnabled(False)
        cmb_sheet.addItem("File Excel...")
        
        spn_header = QSpinBox()
        spn_header.setRange(0, 50)
        
        cmb_x = QComboBox(); cmb_y = QComboBox(); cmb_val = QComboBox()
        
        g2.addRow(QLabel("Pilih Sheet:", styleSheet=label_style), cmb_sheet)
        g2.addRow(QLabel("Baris Header:", styleSheet=label_style), spn_header)
        
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setStyleSheet("background-color: #3A3F4A;")
        g2.addRow(line)
        
        g2.addRow(QLabel("Kolom X (Lon):", styleSheet=label_style), cmb_x)
        g2.addRow(QLabel("Kolom Y (Lat):", styleSheet=label_style), cmb_y)
        g2.addRow(QLabel("Kolom Target:", styleSheet=label_style), cmb_val)
        
        line2 = QFrame(); line2.setFrameShape(QFrame.Shape.HLine); line2.setStyleSheet("background-color: #3A3F4A;")
        g2.addRow(line2)
        g2.addRow(QLabel("Metode:", styleSheet="color:#F7C159; font-weight:bold; font-size:12px; border:none;"), cmb_method)
        
        chk_ks = QCheckBox("Ubah Otomatis D50 -> ks (2.5D)")
        chk_ks.setStyleSheet("color: #E2E8F0; font-weight: 600;")
        if show_ks:
            chk_ks.setChecked(True)
            g2.addRow("", chk_ks)
        else:
            chk_ks.setVisible(False)
            
        grp2.add_layout(g2)
        scroll_area.add_widget(grp2)
        
        # 4. Execution Button
        btn_run = ModernButton("⚡ Eksekusi Matriks & Generate Contours", "primary")
        btn_run.clicked.connect(lambda checked, m=mode_type: self.run_interpolation(m))
        scroll_area.add_widget(btn_run)
        
        scroll_area.add_stretch()
        
        setattr(self, f"cmb_sheet_{mode_type}", cmb_sheet)
        setattr(self, f"spn_header_{mode_type}", spn_header)
        setattr(self, f"cmb_x_{mode_type}", cmb_x)
        setattr(self, f"cmb_y_{mode_type}", cmb_y)
        setattr(self, f"cmb_v_{mode_type}", cmb_val)
        setattr(self, f"cmb_method_{mode_type}", cmb_method)
        setattr(self, f"chk_ks_{mode_type}", chk_ks)
        setattr(self, f"btn_run_{mode_type}", btn_run)
        setattr(self, f"btn_bnd_{mode_type}", btn_load_bnd)
        
        cmb_sheet.currentTextChanged.connect(lambda t, m=mode_type: self.on_sheet_or_header_changed(m))
        spn_header.valueChanged.connect(lambda v, m=mode_type: self.on_sheet_or_header_changed(m))

    def load_boundary_file(self, mode_type: str) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Buka Poligon Batas (AOI)", "", "Shapefile/GeoJSON (*.shp *.geojson *.json)")
        if not p: return
        
        self.tab_data[mode_type]['boundary_file'] = p
        self.log_sed.append(f"🗺️ [BOUNDARY] File masker (clipping) diaktifkan: {os.path.basename(p)}")
        btn = getattr(self, f"btn_bnd_{mode_type}")
        btn.setText(f"✅ Terisi: {os.path.basename(p)}")
        btn.setStyleSheet("color: #42E695; border: 1px solid #42E695;")

    def load_file(self, mode_type: str) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Buka Data Spasial (Survei Lapangan)", "", "Data Spreadsheet (*.csv *.xlsx)")
        if not p: return
        
        self.tab_data[mode_type]['file'] = p
        cmb_sheet = getattr(self, f"cmb_sheet_{mode_type}")
        spn_header = getattr(self, f"spn_header_{mode_type}")
        
        spn_header.blockSignals(True)
        spn_header.setValue(0)
        spn_header.blockSignals(False)
        
        try:
            if p.endswith('.xlsx'):
                with pd.ExcelFile(p) as xl:
                    sheet_names = xl.sheet_names
                
                cmb_sheet.blockSignals(True)
                cmb_sheet.clear()
                cmb_sheet.addItems(sheet_names)
                cmb_sheet.setEnabled(True)
                cmb_sheet.blockSignals(False)
                
                self.load_sheet_data(mode_type, sheet_names[0], 0)
            else:
                cmb_sheet.blockSignals(True)
                cmb_sheet.clear()
                cmb_sheet.addItem("CSV File Aktif")
                cmb_sheet.setEnabled(False)
                cmb_sheet.blockSignals(False)
                
                self.load_sheet_data(mode_type, None, 0)
                
        except Exception as e:
            self.log_sed.append(f"❌ Gagal memuat file untuk {mode_type}: {str(e)}")

    def on_sheet_or_header_changed(self, mode_type: str) -> None:
        cmb_sheet = getattr(self, f"cmb_sheet_{mode_type}")
        spn_header = getattr(self, f"spn_header_{mode_type}")
        self.load_sheet_data(mode_type, cmb_sheet.currentText(), spn_header.value())

    def load_sheet_data(self, mode_type: str, sheet_name: str, header_row: int) -> None:
        p = self.tab_data[mode_type].get('file')
        if not p: return
        
        if self.tab_data[mode_type]['df'] is not None:
            del self.tab_data[mode_type]['df']
            gc.collect()
        
        try:
            if p.endswith('.xlsx') and sheet_name and sheet_name != "CSV File Aktif":
                df = pd.read_excel(p, sheet_name=sheet_name, header=header_row)
            else:
                df = pd.read_csv(p, header=header_row)
                
            self.tab_data[mode_type]['df'] = df
            cols = [str(c) for c in df.columns]
            
            cmb_x = getattr(self, f"cmb_x_{mode_type}")
            cmb_y = getattr(self, f"cmb_y_{mode_type}")
            cmb_v = getattr(self, f"cmb_v_{mode_type}")
            
            cmb_x.blockSignals(True); cmb_y.blockSignals(True); cmb_v.blockSignals(True)
            cmb_x.clear(); cmb_y.clear(); cmb_v.clear()
            cmb_x.addItems(cols); cmb_y.addItems(cols); cmb_v.addItems(cols)
            cmb_x.blockSignals(False); cmb_y.blockSignals(False); cmb_v.blockSignals(False)
            
            for c in cols:
                cl = str(c).lower()
                if 'lon' in cl or 'x' in cl or 'easting' in cl: cmb_x.setCurrentText(c)
                if 'lat' in cl or 'y' in cl or 'northing' in cl: cmb_y.setCurrentText(c)
                if any(k in cl for k in ['d50', 'sedimen', 'val', 'friction', 'dens', 'z', 'target']): 
                    cmb_v.setCurrentText(c)
                
            sht_log = f"Sheet '{sheet_name}'" if sheet_name else "CSV"
            self.log_sed.append(f"[SYSTEM] {sht_log} ter-load. Baris Data: {len(df)}")
            
        except Exception as e:
            logger.warning(f"Gagal memuat subset data: {e}")

    def run_interpolation(self, mode_type: str) -> None:
        if hasattr(self, 'sed_w') and self.sed_w.isRunning():
            QMessageBox.warning(self, "Konflik", "Proses interpolasi sedang berjalan.")
            return

        df = self.tab_data[mode_type]['df']
        boundary_file = self.tab_data[mode_type].get('boundary_file')
        
        if df is None:
            QMessageBox.warning(self, "Validasi Gagal", f"Harap muat dataset (.csv/.xlsx) untuk mode '{mode_type}'.")
            return
            
        cmb_x = getattr(self, f"cmb_x_{mode_type}"); col_x = cmb_x.currentText()
        cmb_y = getattr(self, f"cmb_y_{mode_type}"); col_y = cmb_y.currentText()
        cmb_v = getattr(self, f"cmb_v_{mode_type}"); col_val = cmb_v.currentText()
        cmb_method = getattr(self, f"cmb_method_{mode_type}"); interp_method = cmb_method.currentText()
        chk_ks = getattr(self, f"chk_ks_{mode_type}")
        btn_run = getattr(self, f"btn_run_{mode_type}")
        
        if not col_x or not col_y or not col_val:
            QMessageBox.critical(self, "Validasi Gagal", "Konfigurasi kolom tidak lengkap.")
            return
        
        btn_run.setEnabled(False)
        btn_run.setText("⏳ Sedang Mengekstrak Matriks Spasial...")
        
        epsg_code = app_state.get('EPSG', '32749')
        
        self.sed_w = SedimentWorker(
            df=df,
            col_x=col_x,
            col_y=col_y,
            col_val=col_val,
            convert_ks=chk_ks.isChecked() if chk_ks.isVisible() else False,
            mode_type=mode_type,
            epsg=epsg_code,
            interp_method=interp_method,
            boundary_file=boundary_file
        )
        
        self.sed_w.log_signal.connect(self.log_sed.append)
        
        def update_img(img_path: str):
            if img_path and os.path.exists(img_path):
                self.current_plot_path = img_path
                self.btn_export_png.setEnabled(True)
                pixmap = QPixmap(img_path).scaled(self.lbl_sed_viz.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_sed_viz.setPixmap(pixmap)
                
        self.sed_w.plot_signal.connect(update_img)
        
        def on_finished(xyz_path: str):
            btn_run.setEnabled(True)
            btn_run.setText("⚡ Eksekusi Matriks & Generate Contours")
            
            if xyz_path and os.path.exists(xyz_path):
                app_state.update('sediment_xyz', xyz_path)
                self.log_sed.append(f"[STATE] File forcing `{os.path.basename(xyz_path)}` dikunci ke Memori Global.")
            self.sed_w.deleteLater()
            
        self.sed_w.finished_signal.connect(on_finished)
        self.sed_w.start()

    def export_current_plot(self) -> None:
        """Menyimpan gambar HD (PNG) ke direktori pilihan pengguna untuk lampiran Skripsi/Jurnal."""
        if not self.current_plot_path or not os.path.exists(self.current_plot_path):
            QMessageBox.warning(self, "Export Gagal", "Gambar belum di-generate.")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "Simpan Gambar HD", "Spatial_Contours.png", "PNG Images (*.png)")
        if save_path:
            try:
                shutil.copy2(self.current_plot_path, save_path)
                QMessageBox.information(self, "Berhasil", f"Gambar HD berhasil disimpan di:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "I/O Error", f"Gagal menyimpan gambar:\n{e}")
