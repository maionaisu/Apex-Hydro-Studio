import os
import math
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
import matplotlib
import matplotlib.pyplot as plt
from pyproj import Transformer

matplotlib.use('Agg')

try:
    import dfm_tools as dfmt
    from hydrolib.core.dflowfm.mdu.models import FMModel
    from hydrolib.core.dflowfm.ext.models import ExtModel, Boundary
    from meshkernel import MeshKernel, MakeGridParameters
    HAS_DELTARES = True
except ImportError:
    HAS_DELTARES = False

class DepthProfileEngine:
    @staticmethod
    def calculate_doc_profile(bathy_file, transect_pts, doc_depth, epsg):
        df = pd.read_csv(bathy_file, delim_whitespace=True, header=None, names=['x','y','z'])
        tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        px, py = tr.transform([p[0] for p in transect_pts], [p[1] for p in transect_pts])
        
        dists = [0.0]
        for i in range(1, len(px)): 
            dists.append(dists[-1] + math.hypot(px[i]-px[i-1], py[i]-py[i-1]))
            
        num_pts = 300
        x_line = np.interp(np.linspace(0, dists[-1], num_pts), dists, px)
        y_line = np.interp(np.linspace(0, dists[-1], num_pts), dists, py)
        
        zl = griddata((df['x'], df['y']), df['z'], (x_line, y_line), method='linear')
        if np.isnan(zl).any(): 
            zl[np.isnan(zl)] = griddata((df['x'], df['y']), df['z'], (x_line[np.isnan(zl)], y_line[np.isnan(zl)]), method='nearest')
            
        d_line = np.linspace(0, dists[-1], num_pts)
        
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor('#0B0F19')
        ax.set_facecolor('#0B0F19')
        
        ax.plot(d_line, zl, color='#38BDF8', linewidth=2.5, label='Profil Batimetri Dasar Laut')
        ax.axhline(doc_depth, color='#EF4444', linestyle='--', linewidth=2, label=f'DoC Limit ({doc_depth:.2f} m)')
        ax.axhline(0, color='#10B981', linestyle='-', linewidth=1.5, label='MSL (0.0 m)')
        
        ax.fill_between(d_line, zl, -max(np.abs(zl))*1.5, color='#38BDF8', alpha=0.1)
        ax.fill_between(d_line, zl, doc_depth, where=(zl >= doc_depth) & (zl <= 0), color='#EF4444', alpha=0.25, label='Zona Transport Sedimen Aktif')
        
        ax.set_title("2D Cross-Section: Profil Kedalaman vs Jarak Transek", color='w', fontweight='bold', pad=15)
        ax.set_xlabel("Jarak Sepanjang Transek (meter)", color='#94A3B8')
        ax.set_ylabel("Elevasi Dasar Laut / Z (meter)", color='#94A3B8')
        ax.tick_params(colors='w')
        ax.grid(True, color='#1E293B', linestyle=':', alpha=0.7)
        ax.legend(facecolor='#020617', edgecolor='#1E293B', labelcolor='w')
        
        out_dir = os.path.join(os.getcwd(), 'Apex_Data_Exports')
        os.makedirs(out_dir, exist_ok=True)
        plot_path = os.path.join(out_dir, "doc_2d_cross_section.png")
        
        plt.tight_layout()
        plt.savefig(plot_path, dpi=150)
        plt.close(fig)
        
        return plot_path


class MeshBuilderEngine:
    @staticmethod
    def build_dimr_orchestration(params, global_state, progress_cb, log_cb, preview_cb):
        if not HAS_DELTARES: 
            raise ImportError("Library dfm_tools atau meshkernel tidak terinstal.")
            
        plt.close('all')
        
        # Unpack params
        he = float(params['he'])
        doc = float(params.get('doc', 1.57 * he))
        doc_target_z = -abs(doc)
        epsg = params.get('epsg', '32749')
        transect_coords = params['transect']
        aoi_bounds = params['aoi_bounds']
        bathy_file = params['bathy_file']
        ldb_file = params.get('ldb_file', '')
        sediment_file = params.get('sediment_file', '')
        tide_bc_file = params.get('tide_bc', '')
        out_dir = params['out_dir']
        max_res = float(params['max_res'])
        min_res = float(params['min_res'])
        
        if not os.path.exists(out_dir): os.makedirs(out_dir)
        progress_cb(10)
        
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        utm_E, utm_N = transformer.transform(aoi_bounds['E'], aoi_bounds['N'])
        utm_W, utm_S = transformer.transform(aoi_bounds['W'], aoi_bounds['S'])
        minx, maxx = min(utm_W, utm_E), max(utm_W, utm_E)
        miny, maxy = min(utm_S, utm_N), max(utm_S, utm_N)
        
        start_utm = transformer.transform(transect_coords[0][0], transect_coords[0][1])
        end_utm = transformer.transform(transect_coords[-1][0], transect_coords[-1][1])
        progress_cb(20)

        log_cb("■ Komputasi Interseksi Batimetri untuk Adaptasi Resolusi Fraktal...")
        df_bathy = pd.read_csv(bathy_file, delim_whitespace=True, header=None, names=['x', 'y', 'z'], usecols=[0,1,2], dtype=np.float32)
        df_f = df_bathy[(df_bathy['x'] >= minx) & (df_bathy['x'] <= maxx) & (df_bathy['y'] >= miny) & (df_bathy['y'] <= maxy)]
        
        num_samples = 500
        transect_x = np.linspace(start_utm[0], end_utm[0], num_samples)
        transect_y = np.linspace(start_utm[1], end_utm[1], num_samples)
        transect_z = griddata((df_f['x'].values, df_f['y'].values), df_f['z'].values, (transect_x, transect_y), method='linear')
        
        if np.isnan(transect_z).any(): 
            nan_mask = np.isnan(transect_z)
            transect_z[nan_mask] = griddata((df_f['x'].values, df_f['y'].values), df_f['z'].values, (transect_x[nan_mask], transect_y[nan_mask]), method='nearest')
            
        idx_doc = np.where(transect_z <= doc_target_z)[0]
        doc_y = transect_y[idx_doc[0]] if len(idx_doc) > 0 else end_utm[1]
        progress_cb(40)

        log_cb("■ Eksekusi MeshKernel: Refinement Polygon berdasarkan DoC...")
        mk = MeshKernel()
        make_grid = MakeGridParameters()
        make_grid.origin_x, make_grid.origin_y = minx, miny
        make_grid.upper_right_x, make_grid.upper_right_y = maxx, maxy
        make_grid.block_size_x, make_grid.block_size_y = max_res, max_res
        
        mk.curvilinear_make_uniform(make_grid)
        mk.curvilinear_convert_to_mesh2d()
        
        # Adaptive Refinement
        dist = start_utm[1] - doc_y
        num_tiers = max(1, int(math.log2(max_res / min_res)))
        current_res = max_res
        
        for i in range(1, num_tiers + 1):
            current_res = current_res / 2.0
            r_y = doc_y + (dist * (i / (num_tiers + 1)))
            poly = [(minx, r_y), (maxx, r_y), (maxx, maxy), (minx, maxy)]
            mk.mesh2d_refine_based_on_polygon(np.array([c[0] for c in poly], dtype=np.double), np.array([c[1] for c in poly], dtype=np.double))
        
        if ldb_file and os.path.exists(ldb_file):
            try: 
                log_cb("  ├ Menyuntikkan Coastline Hard-Breaklines (.ldb)...")
                dfmt.ext_pointslines_to_xy(ldb_file)
            except: 
                pass

        file_nc = os.path.join(out_dir, "Domain_Mesh.nc")
        mk.mesh2d_write_netcdf(file_nc)
        
        mesh2d = mk.mesh2d_get()
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.set_facecolor('#030712')
        fig.patch.set_facecolor('#030712')
        ax.plot(mesh2d.node_x, mesh2d.node_y, '.', color='#00D2FF', markersize=0.8, alpha=0.6)
        ax.set_title("Generated Flexible Mesh Topology", color='white', fontsize=12, fontweight='bold')
        ax.tick_params(colors='#64748B')
        
        preview_path = os.path.join(out_dir, "Mesh_Topology_Preview.png")
        plt.tight_layout()
        plt.savefig(preview_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        
        preview_cb(preview_path)
        progress_cb(60)

        # MDU
        log_cb("■ Merakit Arsitektur Hidrodinamika MDU & External Forcing (.ext)...")
        ext = ExtModel()
        ext.boundary.append(Boundary(quantity="bedlevel", locationfile=os.path.basename(bathy_file), forcingfile="", interpolatingmethod="nearest"))
        
        if sediment_file and os.path.exists(sediment_file): 
            log_cb("  ├ Injeksi Mangrove Trachytope / Spatial Friction.")
            ext.boundary.append(Boundary(quantity="frictioncoefficient", locationfile=os.path.basename(sediment_file), forcingfile="", interpolatingmethod="nearest"))

        pli_file = "south_boundary.pli"
        with open(os.path.join(out_dir, pli_file), "w") as f: 
            f.write("South_Ocean_Boundary\n2 2\n")
            f.write(f"{minx} {miny}\n{maxx} {miny}\n")
            
        if tide_bc_file and os.path.exists(tide_bc_file):
            log_cb("  ├ Menyambungkan Astronomic Tidal Forcing (.bc)...")
            ext.boundary.append(Boundary(quantity="waterlevelbnd", locationfile=pli_file, forcingfile=os.path.basename(tide_bc_file)))
        
        fm = FMModel()
        fm.geometry.netfile = "Domain_Mesh.nc"
        fm.geometry.bathymetryfile = ext.filepath
        
        if tide_bc_file or sediment_file: 
            fm.external_forcing.extforcefilenew = "apex_forcing.ext"
            fm.external_forcing.extmodel = ext
            
        fm.physics.dicoww = 0.1 
        if not sediment_file: 
            fm.physics.unifrictcoef = 0.023 
        else: 
            fm.physics.unifrictcoef = 0.0
            fm.physics.frictyp = 4 
            
        fm.numerics.cflmax = 0.7
        fm.time.refdate = 20260411
        fm.time.tstop = 86400.0 * 2 
        fm.filepath = os.path.join(out_dir, "Apex_Flow.mdu")
        fm.save()

        # MDW
        log_cb("■ Merakit Wave Model SWAN (.mdw) untuk Propagasi Gelombang Mangrove...")
        mdw_path = os.path.join(out_dir, "Apex_Wave.mdw")
        with open(mdw_path, "w") as f:
            f.write("[Swan]\n")
            f.write(f"GridFile = Domain_Mesh.nc\nBedLevelFile = {os.path.basename(bathy_file)}\n")
            f.write("DirSpace = Circle\nNDir = 36\nFreqMin = 0.05\nFreqMax = 1.00\nNFreq = 24\n")
            f.write("WaveBoundaryHs = {:.2f}\nWaveBoundaryTp = {:.2f}\nWaveBoundaryDir = {:.2f}\nWaveBoundaryDirSpread = 30.0\n".format(
                global_state.get('Hs', 1.0), global_state.get('Tp', 8.0), global_state.get('Dir', 180.0)))
            f.write("Friction = JONSWAP\nFrictionCoefficient = 0.067\nDepthInducedBreaking = True\nAlpha = 1.0\nGamma = 0.73\n")
        
        # DIMR XML Coupler
        log_cb("■ Merakit DIMR XML Coupler (Flow <-> Wave)...")
        dimr_path = os.path.join(out_dir, "dimr_config.xml")
        with open(dimr_path, "w") as f:
            f.write('<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n')
            f.write('<dimrConfig xmlns="http://schemas.deltares.nl/dimr" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://schemas.deltares.nl/dimr http://content.oss.deltares.nl/schemas/dimr-1.3.xsd">\n')
            f.write('  <control>\n    <parallel>\n      <startGroup>\n        <time>0 86400 86400</time>\n')
            f.write('        <start name="Flow" />\n        <start name="Wave" />\n      </startGroup>\n    </parallel>\n  </control>\n')
            f.write('  <component name="Flow">\n    <library>dflowfm</library>\n    <workingDir>.</workingDir>\n    <inputFile>Apex_Flow.mdu</inputFile>\n  </component>\n')
            f.write('  <component name="Wave">\n    <library>swan</library>\n    <workingDir>.</workingDir>\n    <inputFile>Apex_Wave.mdw</inputFile>\n  </component>\n</dimrConfig>\n')
        
        progress_cb(100)
        log_cb("\n▶ OPERASI KOMPILASI SELESAI. Komponen Skripsi telah dirakit dan siap dieksekusi!")
