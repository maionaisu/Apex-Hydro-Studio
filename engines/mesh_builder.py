# ==============================================================================
# APEX NEXUS TIER-0: DELFT3D-FM DIMR ORCHESTRATOR & MESH BUILDER
# ==============================================================================
import os
import re
import math
import logging
import traceback
from datetime import datetime
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
import matplotlib
import matplotlib.pyplot as plt
from pyproj import Transformer

# Strictly enforce non-interactive backend to prevent GUI Thread locking
matplotlib.use('Agg')
logger = logging.getLogger(__name__)

try:
    import dfm_tools as dfmt
    from hydrolib.core.dflowfm.mdu.models import FMModel
    from hydrolib.core.dflowfm.ext.models import ExtModel, Boundary
    from meshkernel import MeshKernel, MakeGridParameters, GeometryList, MeshRefinementParameters
    HAS_DELTARES = True
except ImportError:
    HAS_DELTARES = False


class DepthProfileEngine:
    @staticmethod
    def calculate_doc_profile(bathy_file: str, transect_pts: list, doc_depth: float, epsg: str) -> str:
        """
        Kalkulasi 2D cross-section Depth of Closure menggunakan transek.
        [ENTERPRISE FIX]: Dual-Panel Academic White Theme (Bird's Eye Map + 2D Profile).
        """
        if not os.path.exists(bathy_file):
            raise FileNotFoundError(f"Berkas batimetri tidak ditemukan: {bathy_file}")
            
        if len(transect_pts) < 2:
            raise ValueError("Kalkulasi profil kedalaman mensyaratkan setidaknya 2 titik transek (Garis awal ke akhir).")

        fig = None
        try:
            # 1. Parsing and coordinate transformation
            df = pd.read_csv(bathy_file, delim_whitespace=True, header=None, names=['x','y','z'], dtype=np.float64)
            tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            
            px, py = tr.transform([p[0] for p in transect_pts], [p[1] for p in transect_pts])
            
            max_x = df['x'].abs().max()
            max_y = df['y'].abs().max()
            if max_x <= 180 and max_y <= 90:
                logger.info("[DOC ENGINE] Batimetri terdeteksi WGS84. Melakukan transformasi ke UTM otomatis...")
                df['x'], df['y'] = tr.transform(df['x'].values, df['y'].values)
            else:
                logger.info("[DOC ENGINE] Batimetri terdeteksi berformat UTM. Lanjut ke interpolasi.")

            # 2. Distance calculation along the transect path
            dists = [0.0]
            for i in range(1, len(px)): 
                dists.append(dists[-1] + math.hypot(px[i]-px[i-1], py[i]-py[i-1]))
                
            num_pts = 300
            x_line = np.interp(np.linspace(0, dists[-1], num_pts), dists, px)
            y_line = np.interp(np.linspace(0, dists[-1], num_pts), dists, py)
            
            # 3. Spatial Interpolation onto transect line
            zl = griddata((df['x'], df['y']), df['z'], (x_line, y_line), method='linear')
            if np.isnan(zl).any(): 
                nan_mask = np.isnan(zl)
                zl[nan_mask] = griddata((df['x'], df['y']), df['z'], (x_line[nan_mask], y_line[nan_mask]), method='nearest')
                
            d_line = np.linspace(0, dists[-1], num_pts)
            
            idx_doc = np.where(zl <= doc_depth)[0]
            doc_found = len(idx_doc) > 0
            if doc_found:
                doc_x_pt, doc_y_pt = x_line[idx_doc[0]], y_line[idx_doc[0]]
                doc_dist = d_line[idx_doc[0]]
            
            # 4. Rendering Visualization (ACADEMIC WHITE THEME - DUAL PANEL)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))
            fig.patch.set_facecolor('white')
            
            # ==========================================
            # PANEL 1: BIRD'S EYE VIEW (SPATIAL MAP)
            # ==========================================
            ax1.set_facecolor('white')
            
            # Agar RAM tidak meledak saat triangulasi matriks jutaan titik
            plot_df = df if len(df) < 20000 else df.sample(20000)
            
            try:
                # Menggunakan tricontourf agar peta batimetri tampak bersambung (solid map)
                levels = np.linspace(plot_df['z'].min(), plot_df['z'].max(), 20)
                cf1 = ax1.tricontourf(plot_df['x'], plot_df['y'], plot_df['z'], levels=levels, cmap='terrain', alpha=0.85)
                # Garis pinggir kontur tipis
                ax1.tricontour(plot_df['x'], plot_df['y'], plot_df['z'], levels=levels, colors='black', linewidths=0.2, alpha=0.5)
                
                cb = plt.colorbar(cf1, ax=ax1, pad=0.02)
                cb.set_label('Elevasi Dasar Laut (m)', color='black', fontweight='bold')
                cb.ax.yaxis.set_tick_params(color='black')
                plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color='black')
            except Exception as e:
                logger.warning(f"Triangulasi Batimetri gagal, fallback ke scatter: {e}")
                sc = ax1.scatter(plot_df['x'], plot_df['y'], c=plot_df['z'], cmap='terrain', s=5, alpha=0.7)
                cb = plt.colorbar(sc, ax=ax1, pad=0.02)
                cb.set_label('Elevasi Dasar Laut (m)', color='black', fontweight='bold')

            # Plot Line & Points
            ax1.plot(px, py, color='red', linewidth=3.5, linestyle='-', label='Jalur Transek', zorder=3)
            ax1.scatter(px[0], py[0], color='green', marker='o', s=150, edgecolor='black', zorder=4, label='Pesisir (Start)')
            
            if doc_found:
                ax1.scatter(doc_x_pt, doc_y_pt, color='orange', marker='*', s=550, edgecolor='black', linewidth=1.5, zorder=5, label=f'Titik DoC Aktual ({doc_depth:.2f}m)')
                
            ax1.set_title("Bird's Eye View: Peta Batimetri & Posisi DoC", color='black', fontweight='bold', pad=15, fontsize=14)
            ax1.set_xlabel("Easting (m)", color='black')
            ax1.set_ylabel("Northing (m)", color='black')
            ax1.tick_params(colors='black')
            ax1.grid(True, color='gray', linestyle=':', alpha=0.5)
            ax1.legend(facecolor='white', edgecolor='black', labelcolor='black', loc='lower right')

            # ==========================================
            # PANEL 2: 2D CROSS-SECTION PROFILE
            # ==========================================
            ax2.set_facecolor('white')
            
            ax2.plot(d_line, zl, color='blue', linewidth=2.5, label='Profil Batimetri Transek')
            ax2.axhline(doc_depth, color='red', linestyle='--', linewidth=2, label=f'Limit DoC ({doc_depth:.2f} m)')
            ax2.axhline(0, color='green', linestyle='-', linewidth=1.5, label='Rata-Rata Muka Air (0.0 m)')
            
            if doc_found:
                ax2.scatter(doc_dist, doc_depth, color='orange', marker='*', s=450, edgecolor='black', zorder=5)
                ax2.axvline(doc_dist, color='orange', linestyle=':', linewidth=1.5, alpha=0.8, label=f'Jarak Potong: {doc_dist:.1f} m')
            
            ax2.fill_between(d_line, zl, -max(np.abs(zl))*1.5, color='blue', alpha=0.1)
            ax2.fill_between(d_line, zl, doc_depth, where=(zl >= doc_depth) & (zl <= 0), color='red', alpha=0.2, label='Zona Transport Sedimen Aktif')
            
            ax2.set_title("2D Cross-Section: Profil Kedalaman vs Jarak", color='black', fontweight='bold', pad=15, fontsize=14)
            ax2.set_xlabel("Jarak Sepanjang Transek dari Pesisir (m)", color='black')
            ax2.set_ylabel("Elevasi Dasar Laut (m)", color='black')
            ax2.tick_params(colors='black')
            ax2.grid(True, color='gray', linestyle=':', alpha=0.5)
            ax2.legend(facecolor='white', edgecolor='black', labelcolor='black', loc='lower left')
            
            # --- Export ---
            out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))
            os.makedirs(out_dir, exist_ok=True)
            plot_path = os.path.join(out_dir, "doc_panorama_analysis.png")
            
            plt.tight_layout()
            plt.savefig(plot_path, dpi=300) # Resolusi Tinggi Jurnal (300 DPI)
            
            return plot_path
            
        except Exception as e:
            logger.error(f"[FATAL] Gagal kalkulasi profil DoC: {str(e)}\n{traceback.format_exc()}")
            raise RuntimeError(f"Profil DoC Gagal: {str(e)}") from e
        finally:
            if fig is not None:
                fig.clf()
                plt.close(fig)


class MeshBuilderEngine:
    @staticmethod
    def build_dimr_orchestration(params: dict, global_state: dict, progress_cb, log_cb, preview_cb) -> None:
        """
        Fungsi utama Orkestrator DIMR. 
        [ENTERPRISE FIX]: Memory leak guard & Time Isoformat Fallback.
        """
        if not HAS_DELTARES: 
            raise ImportError("Library dfm_tools, hydrolib-core, atau meshkernel tidak terinstal.")
            
        fig_preview = None
        mesh2d = None
        mk_f = None
        mk_w = None
        
        try:
            b_mode = params.get('build_mode', 'coupled')
            epsg = str(params.get('epsg', '32749'))
            aoi_bounds = params['aoi_bounds']
            inner_bounds = params['inner_bbox']
            bathy_file = params['bathy_file']
            ldb_file = params.get('ldb_file', '')
            out_dir = os.path.abspath(params['out_dir'])
            
            # [ENTERPRISE TIME FIX]: Fallback Parsing Waktu ISO
            t_start_iso = global_state.get('sim_start_time')
            t_end_iso = global_state.get('sim_end_time')
            if not t_start_iso or not t_end_iso:
                raise ValueError("Waktu simulasi (sim_start_time / sim_end_time) belum diset dari Modul 1. DIMR akan Gagal.")
            
            try:
                # Menangani format '2025-09-01T00:00:00' atau sejenisnya
                t_start = datetime.fromisoformat(t_start_iso.replace("Z", "+00:00"))
                t_end = datetime.fromisoformat(t_end_iso.replace("Z", "+00:00"))
            except Exception:
                raise ValueError(f"Format waktu ISO tidak valid: {t_start_iso} atau {t_end_iso}")
                
            sim_duration_sec = (t_end - t_start).total_seconds()
            
            os.makedirs(out_dir, exist_ok=True)
            progress_cb(10)
            
            transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            
            utm_E, utm_N = transformer.transform(aoi_bounds['E'], aoi_bounds['N'])
            utm_W, utm_S = transformer.transform(aoi_bounds['W'], aoi_bounds['S'])
            minx, maxx = min(utm_W, utm_E), max(utm_W, utm_E)
            miny, maxy = min(utm_S, utm_N), max(utm_S, utm_N)
            
            in_E, in_N = transformer.transform(inner_bounds['E'], inner_bounds['N'])
            in_W, in_S = transformer.transform(inner_bounds['W'], inner_bounds['S'])
            i_minx, i_maxx = min(in_W, in_E), max(in_W, in_E)
            i_miny, i_maxy = min(in_S, in_N), max(in_S, in_N)
            
            progress_cb(20)

            # =====================================================================
            # TAHAP 1: D-FLOW FLEXIBLE MESH
            # =====================================================================
            if b_mode in ['dflow_only', 'coupled']:
                log_cb("■ [D-FLOW] Merakit Flexible Mesh (Unstructured)...")
                
                max_res = float(params['max_res'])
                min_res = float(params['min_res'])
                
                mk_f = MeshKernel()
                make_grid_f = MakeGridParameters()
                make_grid_f.origin_x, make_grid_f.origin_y = minx, miny
                make_grid_f.upper_right_x, make_grid_f.upper_right_y = maxx, maxy
                make_grid_f.block_size_x, make_grid_f.block_size_y = max_res, max_res
                
                mk_f.curvilinear_make_uniform(make_grid_f)
                mk_f.curvilinear_convert_to_mesh2d()
                
                poly_f = [(i_minx, i_miny), (i_maxx, i_miny), (i_maxx, i_maxy), (i_minx, i_maxy), (i_minx, i_miny)]
                geom_f = GeometryList(
                    x_coordinates=np.array([c[0] for c in poly_f], dtype=np.double), 
                    y_coordinates=np.array([c[1] for c in poly_f], dtype=np.double)
                )
                
                num_tiers_f = max(1, int(math.log2(max_res / min_res)))
                curr_res_f = max_res
                
                for _ in range(num_tiers_f):
                    curr_res_f = curr_res_f / 2.0
                    ref_f = MeshRefinementParameters(
                        min_face_size=curr_res_f, refinement_type=1, connect_hanging_nodes=True, 
                        account_for_samples_outside_polygon=False, max_num_refinement_iterations=1
                    )
                    mk_f.mesh2d_refine_based_on_polygon(geom_f, ref_f)
                
                if params.get('clip_landward', True) and ldb_file and os.path.exists(ldb_file):
                    log_cb("  ├ Menyuntikkan Land Boundary Clipping (.ldb)...")
                    try:
                        ldb_gdf = dfmt.read_polyfile(ldb_file)
                        for _, row in ldb_gdf.iterrows():
                            geom = row.geometry
                            if geom.geom_type in ['Polygon', 'MultiPolygon']:
                                coords = np.array(geom.exterior.coords) if geom.geom_type == 'Polygon' else np.array(geom.coords)
                                geom_list = GeometryList(
                                    x_coordinates=np.array(coords[:,0], dtype=np.double), 
                                    y_coordinates=np.array(coords[:,1], dtype=np.double)
                                )
                                mk_f.mesh2d_delete(geom_list, delete_option=1, invert_deletion=False)
                    except Exception as e:
                        logger.warning(f"Clipping LDB gagal: {str(e)}")
                
                file_nc_f = os.path.join(out_dir, "Flow_Mesh.nc")
                mk_f.mesh2d_write_netcdf(file_nc_f)
                
                ext = ExtModel()
                ext.boundary.append(Boundary(quantity="bedlevel", locationfile=os.path.basename(bathy_file), forcingfile="", interpolatingmethod="nearest"))
                
                sediment_file = params.get('sediment_file', '')
                if sediment_file and os.path.exists(sediment_file): 
                    log_cb("  ├ Injeksi Mangrove Trachytope / Spatial Friction (.xyz) -> Baptist Eq.")
                    ext.boundary.append(Boundary(quantity="frictioncoefficient", locationfile=os.path.basename(sediment_file), forcingfile="", interpolatingmethod="nearest"))

                bnd_dir = params.get('ocean_boundary_dir', 'South')
                pli_file = f"{bnd_dir.lower()}_boundary.pli"
                
                with open(os.path.join(out_dir, pli_file), "w", encoding="utf-8") as f: 
                    f.write(f"{bnd_dir}_Ocean_Boundary\n2 2\n")
                    if bnd_dir == "North": f.write(f"{minx} {maxy}\n{maxx} {maxy}\n")
                    elif bnd_dir == "East": f.write(f"{maxx} {miny}\n{maxx} {maxy}\n")
                    elif bnd_dir == "West": f.write(f"{minx} {miny}\n{minx} {maxy}\n")
                    else: f.write(f"{minx} {miny}\n{maxx} {miny}\n")
                    
                tide_bc_file = params.get('tide_bc', '')
                if tide_bc_file and os.path.exists(tide_bc_file):
                    target_bnd_name = f"{bnd_dir}_Ocean_Boundary"
                    try:
                        with open(tide_bc_file, 'r', encoding='utf-8') as f:
                            bc_data = f.read()
                        bc_data = re.sub(r"Name\s*=\s*\w+_Ocean_Boundary", f"Name                            = {target_bnd_name}", bc_data)
                        with open(tide_bc_file, 'w', encoding='utf-8') as f:
                            f.write(bc_data)
                        log_cb(f"  ├ [✓] Sinkronisasi nama Boundary (.bc) ke: {target_bnd_name}")
                    except Exception as e:
                        logger.warning(f"Gagal menyinkronkan nama boundary .bc: {e}")

                qty_type = "neumannbnd" if params.get('use_riemann', True) else "waterlevelbnd"
                if qty_type == "neumannbnd": log_cb("  ├ [✓] Riemann Boundary Aktif (Anti-Reflection).")
                
                ext.boundary.append(Boundary(quantity=qty_type, locationfile=pli_file, forcingfile=os.path.basename(tide_bc_file)))
                
                ext_filepath = os.path.join(out_dir, "apex_forcing.ext")
                ext.filepath = ext_filepath
                ext.save(filepath=ext_filepath)
                
                fm = FMModel()
                fm.geometry.netfile = "Flow_Mesh.nc"
                if tide_bc_file or sediment_file: fm.external_forcing.extforcefilenew = "apex_forcing.ext"
                
                fm.physics.dicoww = 0.1 
                if not sediment_file: 
                    fm.physics.unifrictcoef = 0.023 
                else: 
                    fm.physics.unifrictcoef = 0.0
                    fm.physics.frictyp = 3  
                    log_cb("  ├ [✓] Memaksa Physics `frictyp=3` (Nikuradse) untuk Mangrove Drag Force.")
                    
                fm.numerics.cflmax = 0.7
                fm.time.refdate = int(t_start.strftime("%Y%m%d"))
                fm.time.tstop = sim_duration_sec 
                
                fm_path = os.path.join(out_dir, "Apex_Flow.mdu")
                fm.filepath = fm_path
                fm.save(filepath=fm_path)
                
                mesh2d = mk_f.mesh2d_get()

            progress_cb(50)

            # =====================================================================
            # TAHAP 2: D-WAVES RECTILINEAR GRID
            # =====================================================================
            if b_mode in ['dwaves_only', 'coupled']:
                log_cb("■ [D-WAVES] Merakit Rectilinear Nested Grid (SWAN Structured)...")
                
                w_max_res = float(params['w_max_res'])
                w_min_res = float(params['w_min_res'])
                w_level = float(params.get('w_level', 0.0))
                
                mk_w = MeshKernel()
                make_grid_w = MakeGridParameters()
                make_grid_w.origin_x, make_grid_w.origin_y = minx, miny
                make_grid_w.upper_right_x, make_grid_w.upper_right_y = maxx, maxy
                make_grid_w.block_size_x, make_grid_w.block_size_y = w_max_res, w_max_res
                
                mk_w.curvilinear_make_uniform(make_grid_w)
                mk_w.curvilinear_convert_to_mesh2d()
                
                poly_w = [(i_minx, i_miny), (i_maxx, i_miny), (i_maxx, i_maxy), (i_minx, i_maxy), (i_minx, i_miny)]
                geom_w = GeometryList(
                    x_coordinates=np.array([c[0] for c in poly_w], dtype=np.double), 
                    y_coordinates=np.array([c[1] for c in poly_w], dtype=np.double)
                )
                
                num_tiers_w = max(1, int(math.log2(w_max_res / w_min_res)))
                curr_res_w = w_max_res
                
                for _ in range(num_tiers_w):
                    curr_res_w = curr_res_w / 2.0
                    ref_w = MeshRefinementParameters(
                        min_face_size=curr_res_w, refinement_type=1, connect_hanging_nodes=True, 
                        account_for_samples_outside_polygon=False, max_num_refinement_iterations=1
                    )
                    mk_w.mesh2d_refine_based_on_polygon(geom_w, ref_w)
                
                file_nc_w = os.path.join(out_dir, "Wave_Mesh.nc")
                mk_w.mesh2d_write_netcdf(file_nc_w)
                
                mdw_path = os.path.join(out_dir, "Apex_Wave.mdw")
                with open(mdw_path, "w", encoding="utf-8") as f:
                    f.write("[Swan]\n")
                    f.write(f"GridFile = Wave_Mesh.nc\nBedLevelFile = {os.path.basename(bathy_file)}\n")
                    
                    if b_mode == 'dwaves_only':
                        f.write(f"WaterLevel = {w_level:.2f}\n")
                        
                    f.write("DirSpace = Circle\nNDir = 36\nFreqMin = 0.05\nFreqMax = 1.00\nNFreq = 24\n")
                    f.write("WaveBoundaryHs = {:.2f}\nWaveBoundaryTp = {:.2f}\nWaveBoundaryDir = {:.2f}\nWaveBoundaryDirSpread = 30.0\n".format(
                        global_state.get('Hs', 1.0), global_state.get('Tp', 8.0), global_state.get('Dir', 180.0)))
                    f.write(f"Friction = {params.get('w_fric_type', 'JONSWAP')}\nFrictionCoefficient = 0.067\nDepthInducedBreaking = True\nAlpha = 1.0\nGamma = {params.get('w_gamma', 0.73)}\n")
                
                if b_mode == 'dwaves_only':
                    mesh2d = mk_w.mesh2d_get()

            progress_cb(80)

            # =====================================================================
            # TAHAP 3: DIMR XML COUPLER
            # =====================================================================
            if b_mode == 'coupled':
                log_cb("■ [COUPLING] Merakit DIMR XML Coupler Dua-Arah (Flow <-> Wave)...")
                dimr_path = os.path.join(out_dir, "dimr_config.xml")
                
                xml_content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<dimrConfig xmlns="http://schemas.deltares.nl/dimr" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://schemas.deltares.nl/dimr http://content.oss.deltares.nl/schemas/dimr-1.3.xsd">
  <control>
    <parallel>
      <startGroup>
        <time>0 1800 {int(sim_duration_sec)}</time>
        <coupler name="flow2wave" />
        <coupler name="wave2flow" />
        <start name="Flow" />
        <start name="Wave" />
      </startGroup>
    </parallel>
  </control>
  <component name="Flow">
    <library>dflowfm</library>
    <workingDir>.</workingDir>
    <inputFile>Apex_Flow.mdu</inputFile>
  </component>
  <component name="Wave">
    <library>swan</library>
    <workingDir>.</workingDir>
    <inputFile>Apex_Wave.mdw</inputFile>
  </component>
  <coupler name="flow2wave">
    <sourceComponent>Flow</sourceComponent>
    <targetComponent>Wave</targetComponent>
    <item>water_level</item>
    <item>flow_velocity</item>
  </coupler>
  <coupler name="wave2flow">
    <sourceComponent>Wave</sourceComponent>
    <targetComponent>Flow</targetComponent>
    <item>wave_rms_height</item>
    <item>wave_peak_period</item>
    <item>wave_direction</item>
    <item>wave_forces</item>
  </coupler>
</dimrConfig>
"""
                with open(dimr_path, "w", encoding="utf-8") as f:
                    f.write(xml_content)

            # --- PLOT RENDERING ---
            if mesh2d is not None:
                fig_preview, ax = plt.subplots(figsize=(8, 6))
                ax.set_facecolor('white')
                fig_preview.patch.set_facecolor('white')
                color_dot = 'blue' if b_mode != 'dwaves_only' else 'red'
                title_txt = "Generated Flexible Mesh Topology (D-FLOW)" if b_mode != 'dwaves_only' else "Generated Rectilinear Topology (D-WAVES)"
                
                ax.plot(mesh2d.node_x, mesh2d.node_y, '.', color=color_dot, markersize=0.8, alpha=0.8)
                ax.set_title(title_txt, color='black', fontsize=12, fontweight='bold')
                ax.tick_params(colors='black')
                ax.grid(True, color='gray', linestyle=':', alpha=0.3)
                
                preview_path = os.path.join(out_dir, "Mesh_Topology_Preview.png")
                plt.tight_layout()
                plt.savefig(preview_path, dpi=200, bbox_inches='tight')
                preview_cb(preview_path)

            progress_cb(100)
            log_cb(f"\n▶ OPERASI KOMPILASI '{b_mode.upper()}' SELESAI. Siap dieksekusi di Modul 5.")
            
        except Exception as e:
            error_msg = f"[FATAL] Orkestrasi DIMR/Mesh Gagal: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            log_cb(error_msg)
            raise RuntimeError(f"Gagal membangun arsitektur DIMR: {str(e)}") from e
            
        finally:
            if fig_preview is not None:
                fig_preview.clf()
                plt.close(fig_preview)
            del mk_f
            del mk_w
            import gc
            gc.collect()
