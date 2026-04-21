import os
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QCheckBox, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QSplitter, QTabWidget, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from workers.sediment_worker import SedimentWorker
from core.state_manager import app_state

class Modul2Sediment(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        head = QVBoxLayout()
        t = QLabel("Spatial Sediments & Coastal Friction")
        t.setStyleSheet("font-size: 24px; font-weight: 900; color: white;")
        d = QLabel("Pemetaan densitas Trachytope untuk Mangrove, Lamun, Karang, dan perhitungan kekasaran dasar laut.")
        d.setStyleSheet("color: #94A3B8; font-size: 13px;")
        head.addWidget(t)
        head.addWidget(d)
        main_layout.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # 1. Top Widget (Visualization)
        self.lbl_sed_viz = QLabel("Plot Spasial (Heatmap) akan muncul di sini.")
        self.lbl_sed_viz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sed_viz.setStyleSheet("border: 1px dashed #334155; background-color:#020617; border-radius: 8px;")
        
        top_wrap = QFrame()
        top_wrap.setStyleSheet("border: 1px solid #1E293B; border-radius: 8px; background: #000;")
        tl = QVBoxLayout(top_wrap)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(self.lbl_sed_viz)
        splitter.addWidget(top_wrap)

        # 2. Middle Widget (Controls via QTabWidget for modular split)
        self.tabs = QTabWidget()
        self.tabs.setMaximumHeight(350)
        
        # Panel 1: Sediment Dasar
        self.tab_sediment = QWidget()
        self.build_tab_ui(self.tab_sediment, 'sediment', "Load Spasial Sedimen Dasar Laut (.csv/.xlsx)", True)
        self.tabs.addTab(self.tab_sediment, "1. Sedimen Dasar (Manning/Nikuradse)")

        # Panel 2: Mangrove (Baptist)
        self.tab_mangrove = QWidget()
        self.build_tab_ui(self.tab_mangrove, 'mangrove', "Load Node Vegetasi Mangrove Emergent (.csv/.xlsx)", False)
        self.tabs.addTab(self.tab_mangrove, "2. Mangrove (Trachytope Baptist)")

        # Panel 3: Submerged Vegetation
        self.tab_submerged = QWidget()
        self.build_tab_ui(self.tab_submerged, 'submerged', "Load Survei Terumbu Karang & Lamun (.csv/.xlsx)", False)
        self.tabs.addTab(self.tab_submerged, "3. Submerged Vegetation (Karang/Lamun)")

        splitter.addWidget(self.tabs)

        # 3. Bottom Widget (Log)
        bot_wrap = QWidget()
        bl = QVBoxLayout(bot_wrap)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(QLabel("Interpolation Console Log:", styleSheet="font-weight:bold; color:#F59E0B;"))
        self.log_sed = QTextEdit()
        self.log_sed.setReadOnly(True)
        bl.addWidget(self.log_sed)
        splitter.addWidget(bot_wrap)

        splitter.setSizes([400, 300, 200])
        main_layout.addWidget(splitter)
        
        # Dictionary to store per-tab state
        self.tab_data = {
            'sediment': {'df': None, 'x': None, 'y': None, 'v': None, 'chk_ks': None},
            'mangrove': {'df': None, 'x': None, 'y': None, 'v': None, 'chk_ks': None},
            'submerged': {'df': None, 'x': None, 'y': None, 'v': None, 'chk_ks': None}
        }

    def build_tab_ui(self, parent_widget, mode_type, btn_text, show_ks):
        layout = QHBoxLayout(parent_widget)
        
        # Col 1: Dataset
        c1 = QVBoxLayout()
        grp1 = QGroupBox("Dataset Input")
        g1 = QVBoxLayout(grp1)
        
        btn_load = QPushButton(btn_text)
        if mode_type == 'mangrove':
            btn_load.setObjectName("GreenBtn")
        elif mode_type == 'submerged':
            btn_load.setObjectName("PurpleBtn")
        else:
            btn_load.setObjectName("OutlineBtn")
            
        btn_load.clicked.connect(lambda: self.load_file(mode_type))
        g1.addWidget(btn_load)
        c1.addWidget(grp1)
        layout.addLayout(c1)
        
        # Col 2: Mapper Logic
        c2 = QVBoxLayout()
        grp2 = QGroupBox("Mapper & Interpolasi Target")
        g2 = QFormLayout(grp2)
        
        cmb_x = QComboBox()
        cmb_y = QComboBox()
        cmb_val = QComboBox()
        
        g2.addRow("Lon/X:", cmb_x)
        g2.addRow("Lat/Y:", cmb_y)
        g2.addRow("Kolom Nilai:", cmb_val)
        
        chk_ks = QCheckBox("Transformasi D50 ke Nikuradse (ks = 2.5D)")
        if show_ks:
            chk_ks.setChecked(True)
            g2.addRow("", chk_ks)
        else:
            chk_ks.setVisible(False)
            
        btn_run = QPushButton("Eksekusi Delaunay XYZ & Heatmap")
        btn_run.setObjectName("ExecuteBtn")
        btn_run.clicked.connect(lambda: self.run_interpolation(mode_type))
        g2.addRow(btn_run)
        
        c2.addWidget(grp2)
        layout.addLayout(c2)
        
        # Bind dynamically reference to state
        # In setup phase, state dictionaries are prepared globally 
        # so we will store references via setattr for easy UI retrieval during run
        setattr(self, f"cmb_x_{mode_type}", cmb_x)
        setattr(self, f"cmb_y_{mode_type}", cmb_y)
        setattr(self, f"cmb_v_{mode_type}", cmb_val)
        setattr(self, f"chk_ks_{mode_type}", chk_ks)
        
        # Store global references for Tour Guide precision mapping
        setattr(self, f"btn_load_{mode_type}", btn_load)
        setattr(self, f"btn_run_{mode_type}", btn_run)

    def load_file(self, mode_type):
        p, _ = QFileDialog.getOpenFileName(self, "Buka Data Spasial", "", "Data (*.csv *.xlsx)")
        if not p: return
        
        try:
            df = pd.read_excel(p) if p.endswith('.xlsx') else pd.read_csv(p)
            self.tab_data[mode_type]['df'] = df
            cols = list(df.columns)
            
            cmb_x = getattr(self, f"cmb_x_{mode_type}")
            cmb_y = getattr(self, f"cmb_y_{mode_type}")
            cmb_v = getattr(self, f"cmb_v_{mode_type}")
            
            cmb_x.clear(); cmb_y.clear(); cmb_v.clear()
            cmb_x.addItems(cols); cmb_y.addItems(cols); cmb_v.addItems(cols)
            
            for c in cols:
                cl = str(c).lower()
                if 'lon' in cl or 'x' in cl: cmb_x.setCurrentText(c)
                if 'lat' in cl or 'y' in cl: cmb_y.setCurrentText(c)
                if 'd50' in cl or 'sedimen' in cl or 'val' in cl or 'friction' in cl or 'dens' in cl: cmb_v.setCurrentText(c)
                
            self.log_sed.append(f"▶ File {os.path.basename(p)} aktif untuk panel {mode_type}.")
        except Exception as e:
            self.log_sed.append(f"❌ Gagal load {mode_type}: {e}")

    def run_interpolation(self, mode_type):
        df = self.tab_data[mode_type]['df']
        if df is None:
            self.log_sed.append(f"❌ Data belum di-load untuk {mode_type}")
            return
            
        cmb_x = getattr(self, f"cmb_x_{mode_type}")
        cmb_y = getattr(self, f"cmb_y_{mode_type}")
        cmb_v = getattr(self, f"cmb_v_{mode_type}")
        chk_ks = getattr(self, f"chk_ks_{mode_type}")
        btn_run = getattr(self, f"btn_run_{mode_type}")
        
        self.sed_w = SedimentWorker(
            df=df,
            col_x=cmb_x.currentText(),
            col_y=cmb_y.currentText(),
            col_val=cmb_v.currentText(),
            convert_ks=chk_ks.isChecked() if chk_ks.isVisible() else False,
            mode_type=mode_type,
            epsg=app_state.get('EPSG', '32749')
        )
        
        self.sed_w.log_signal.connect(self.log_sed.append)
        
        def update_img(p):
            if os.path.exists(p):
                self.lbl_sed_viz.setPixmap(QPixmap(p).scaled(self.lbl_sed_viz.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.lbl_sed_viz.setText("")
        self.sed_w.plot_signal.connect(update_img)
        
        def on_finished(xyz_path):
            btn_run.setEnabled(True)
            btn_run.setText("Eksekusi Delaunay XYZ & Heatmap")
            if xyz_path and os.path.exists(xyz_path):
                # Lock target friction layer inside global memory state based on the latest interpolation
                app_state.update('sediment_xyz', xyz_path)
            self.sed_w.deleteLater()
                
        self.sed_w.finished_signal.connect(on_finished)
        
        # Lock UI
        btn_run.setEnabled(False)
        btn_run.setText("⏳ Sedang Mengekstrak Interpolasi Spasial...")
        self.sed_w.start()
