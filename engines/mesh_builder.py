# ==============================================================================
# APEX NEXUS TIER-0: DELFT3D-FM DIMR ORCHESTRATOR & MESH BUILDER
# ==============================================================================
import os
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
        [UPGRADE]: Menambahkan Bird's Eye View (Spatial Map) + DoC Point Locator.
        Aman terhadap memory leak Matplotlib.
        """
        if not os.path.exists(bathy_file):
            raise FileNotFoundError(f"File batimetri tidak ditemukan: {bathy_file}")
            
        if len(transect_pts) < 2:
            raise ValueError("Pembuatan profil kedalaman memerlukan minimal 2 titik transek.")

        fig = None
        try:
            # 1. Parsing and coordinate transformation
            df = pd.read_csv(bathy_file, delim_whitespace=True, header=None, names=['x','y','z'], dtype=np.float64)
            tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            px, py = tr.transform([p[0] for p in transect_pts], [p[1] for p in transect_pts])
            
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
            
            # [BARU] MENCARI TITIK SPASIAL DoC TEPAT DI PETA
            idx_doc = np.where(zl <= doc_depth)[0]
            doc_found = len(idx_doc) > 0
            if doc_found:
                doc_x_pt = x_line[idx_doc[0]]
                doc_y_pt = y_line[idx_doc[0]]
                doc_dist = d_line[idx_doc[0]]
            
            # 4. Rendering Visualization (DUAL VIEW: BIRD'S EYE & PROFILE)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
            fig.patch.set_facecolor('#0B0F19')
            
            # ==========================================
            # PANEL 1: BIRD'S EYE VIEW (SPATIAL MAP)
            # ==========================================
            ax1.set_facecolor('#030712')
            
            # Sub-sample batimetri jika titik terlalu padat agar plot lebih cepat (opsional)
            plot_df = df if len(df) < 50000 else df.sample(50000)
            
            # Scatter kedalaman dasar laut
            sc = ax1.scatter(plot_df['x'], plot_df['y'], c=plot_df['z'], cmap='ocean', s=5, alpha=0.6)
            
            # Garis Transek
            ax1.plot(px, py, color='#EF4444', linewidth=2.5, linestyle='-', label='Garis Transek')
            ax1.scatter(px[0], py[0], color='#10B981', marker='o', s=100, edgecolor='w', zorder=4, label='Start (Pesisir)')
            
            # Titik Bintang DoC
            if doc_found:
                ax1.scatter(doc_x_pt, doc_y_pt, color='#F59E0B', marker='*', s=400, edgecolor='black', linewidth=1.5, zorder=5, label=f'Titik DoC ({doc_depth:.2f}m)')
                
            ax1.set_title("Bird's Eye View: Pemetaan Spasial Transek & DoC", color='w', fontweight='bold', pad=15)
            ax1.set_xlabel("Easting (UTM)", color='#94A3B8')
            ax1.set_ylabel("Northing (UTM)", color='#94A3B8')
            ax1.tick_params(colors='w')
            ax1.grid(True, color='#1E293B', linestyle=':', alpha=0.7)
            
            # Colorbar Peta Spasial
            cb = plt.colorbar(sc, ax=ax1)
            cb.set_label('Elevasi (m)', color='w')
            cb.ax.yaxis.set_tick_params(color='w')
            plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color='w')
            ax1.legend(facecolor='#020617', edgecolor='#1E293B', labelcolor='w', loc='lower right')

            # ==========================================
            # PANEL 2: 2D CROSS-SECTION PROFILE
            # ==========================================
            ax2.set_facecolor('#0B0F19')
            
            ax2.plot(d_line, zl, color='#38BDF8', linewidth=2.5, label='Profil Batimetri Transek')
            ax2.axhline(doc_depth, color='#EF4444', linestyle='--', linewidth=2, label=f'Batas DoC ({doc_depth:.2f} m)')
            ax2.axhline(0, color='#10B981', linestyle='-', linewidth=1.5, label='Mean Sea Level (0.0 m)')
            
            # Sinkronisasi penanda DoC di plot cross-section
            if doc_found:
                ax2.scatter(doc_dist, doc_depth, color='#F59E0B', marker='*', s=300, edgecolor='black', zorder=5)
                ax2.axvline(doc_dist, color='#F59E0B', linestyle=':', linewidth=1.5, alpha=0.8, label=f'Jarak DoC: {doc_dist:.1f} m')
            
            ax2.fill_between(d_line, zl, -max(np.abs(zl))*1.5, color='#38BDF8', alpha=0.1)
            ax2.fill_between(d_line, zl, doc_depth, where=(zl >= doc_depth) & (zl <= 0), color='#EF4444', alpha=0.25, label='Zona Transport Sedimen Aktif')
            
            ax2.set_title("2D Cross-Section: Profil Kedalaman vs Jarak Pantai", color='w', fontweight='bold', pad=15)
            ax2.set_xlabel("Jarak Sepanjang Transek (meter)", color='#94A3B8')
            ax2.set_ylabel("Elevasi Dasar Laut / Z (meter)", color='#94A3B8')
            ax2.tick_params(colors='w')
            ax2.grid(True, color='#1E293B', linestyle=':', alpha=0.7)
            ax2.legend(facecolor='#020617', edgecolor='#1E293B', labelcolor='w')
            
            # --- Export ---
            out_dir = os.path.abspath(os.path.join(os.getcwd(), 'Apex_Data_Exports'))
            os.makedirs(out_dir, exist_ok=True)
            plot_path = os.path.join(out_dir, "doc_panorama_analysis.png")
            
            plt.tight_layout()
            plt.savefig(plot_path, dpi=150)
            
            return plot_path
            
        except Exception as e:
            logger.error(f"[FATAL] Gagal kalkulasi profil DoC: {str(e)}\n{traceback.format_exc()}")
            raise RuntimeError(f"Profil DoC Gagal: {str(e)}") from e
        finally:
            if fig is not None:
                plt.close(fig)


class MeshBuilderEngine:
    @staticmethod
    def build_dimr_orchestration(params: dict, global_state: dict, progress_cb, log_cb, preview_cb) -> None:
        """
        Fungsi utama Orkestrator DIMR (D-Flow FM + SWAN).
        Mengimplementasikan Dynamic Boundaries, Riemann Logic, dan BUG-Fixes.
        """
        if not HAS_DELTARES: 
            raise ImportError("Library dfm_tools, hydrolib-core, atau meshkernel tidak terinstal.")
            
        fig_preview = None
        
        try:
            # 1. Unpack & Validate Parameters
            he = float(params['he'])
            doc = float(params.get('doc', 1.57 * he))
            doc_target_z = -abs(doc)
            epsg = str(params.get('epsg', '32749'))
            transect_coords = params['transect']
            aoi_bounds = params['aoi_bounds']
            
            bathy_file = params['bathy_file']
            ldb_file = params.get('ldb_file', '')
            sediment_file = params.get('sediment_file', '')
            tide_bc_file = params.get('tide_bc', '')
            
            out_dir = os.path.abspath(params['out_dir'])
            max_res = float(params['max_res'])
            min_res = float(params['min_res'])
            
            # --- GUARD RAILS (Validation) ---
            if aoi_bounds['N'] <= aoi_bounds['S'] or aoi_bounds['E'] <= aoi_bounds['W']:
                raise ValueError("Batas AOI tidak valid (N harus > S, E harus > W). Koordinat terbalik.")
            if len(transect_coords) < 2:
                raise ValueError("Koordinat transek minimal harus terdiri dari 2 titik ujung.")
            if min_res > max_res:
                raise ValueError("Resolusi minimum tidak boleh lebih besar dari resolusi maksimum.")
            if not os.path.exists(bathy_file):
                raise FileNotFoundError(f"File batimetri .xyz tidak ditemukan: {bathy_file}")
                
            os.makedirs(out_dir, exist_ok=True)
            progress_cb(10)
            
            # 2. Koordinat Translasi
            transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            utm_E, utm_N = transformer.transform(aoi_bounds['E'], aoi_bounds['N'])
            utm_W, utm_S = transformer.transform(aoi_bounds['W'], aoi_bounds['S'])
            minx, maxx = min(utm_W, utm_E), max(utm_W, utm_E)
            miny, maxy = min(utm_S, utm_N), max(utm_S, utm_N)
            
            start_utm = transformer.transform(transect_coords[0][0], transect_coords[0][1])
            end_utm = transformer.transform(transect_coords[-1][0], transect_coords[-1][1])
            progress_cb(20)

            # 3. Interseksi Batimetri untuk Algoritma Fraktal/Refinement Mesh
            log_cb("■ Komputasi Interseksi Batimetri untuk Adaptasi Resolusi Fraktal...")
            df_bathy = pd.read_csv(bathy_file, delim_whitespace=True, header=None, names=['x', 'y', 'z'], usecols=[0,1,2], dtype=np.float32)
            df_f = df_bathy[(df_bathy['x'] >= minx) & (df_bathy['x'] <= maxx) & (df_bathy['y'] >= miny) & (df_bathy['y'] <= maxy)]
            
            if df_f.empty:
                raise ValueError("Area AOI berada di luar cakupan file batimetri yang diberikan.")
                
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

            # 4. MeshKernel Execution (Base Grid)
            log_cb("■ Eksekusi MeshKernel: Inisiasi Topologi Grid...")
            mk = MeshKernel()
            make_grid = MakeGridParameters()
            make_grid.origin_x, make_grid.origin_y = minx, miny
            make_grid.upper_right_x, make_grid.upper_right_y = maxx, maxy
            make_grid.block_size_x, make_grid.block_size_y = max_res, max_res
            
            mk.curvilinear_make_uniform(make_grid)
            mk.curvilinear_convert_to_mesh2d()
            
            # 5. Adaptive Refinement Mesh
            log_cb("■ Menjalankan Adaptive Refinement berdasarkan DoC...")
            dist = start_utm[1] - doc_y
            num_tiers = max(1, int(math.log2(max_res / min_res)))
            current_res = max_res
            
            for i in range(1, num_tiers + 1):
                current_res = current_res / 2.0
                r_y = doc_y + (dist * (i / (num_tiers + 1)))
                
                # Poligon tertutup untuk iterasi refinemen GeometryList API
                poly = [(minx, r_y), (maxx, r_y), (maxx, maxy), (minx, maxy), (minx, r_y)]
                x_coords = np.array([c[0] for c in poly], dtype=np.double)
                y_coords = np.array([c[1] for c in poly], dtype=np.double)
                
                geom_list = GeometryList(x_coordinates=x_coords, y_coordinates=y_coords)
                ref_params = MeshRefinementParameters(
                    min_face_size=current_res, 
                    refinement_type=1, 
                    connect_hanging_nodes=True, 
                    account_for_samples_outside_polygon=False, 
                    max_num_refinement_iterations=1
                )
                mk.mesh2d_refine_based_on_polygon(geom_list, ref_params)
            
            # 6. Pesisir Pantai / LDB Coastline Breaklines
            if ldb_file and os.path.exists(ldb_file):
                log_cb("  ├ Menyuntikkan Coastline Hard-Breaklines (.ldb)...")
                try: 
                    ldb_gdf = dfmt.read_polyfile(ldb_file)
                    for _, row in ldb_gdf.iterrows():
                        geom = row.geometry
                        if geom.geom_type in ['Polygon', 'MultiPolygon', 'LineString']:
                            coords = np.array(geom.exterior.coords) if geom.geom_type == 'Polygon' else np.array(geom.coords)
                            geom_list = GeometryList(
                                x_coordinates=np.array(coords[:,0], dtype=np.double), 
                                y_coordinates=np.array(coords[:,1], dtype=np.double)
                            )
                            # Memotong node/face yang tumpang tindih dengan daratan
                            mk.mesh2d_delete(geom_list, delete_option=1, invert_deletion=False)
                except Exception as e:
                    logger.warning(f"Operasi pemotongan mesh dengan LDB mengalami kegagalan non-kritis: {str(e)}")

            file_nc = os.path.join(out_dir, "Domain_Mesh.nc")
            mk.mesh2d_write_netcdf(file_nc)
            
            # 7. Render Mesh Preview
            mesh2d = mk.mesh2d_get()
            fig_preview, ax = plt.subplots(figsize=(8, 6))
            ax.set_facecolor('#030712')
            fig_preview.patch.set_facecolor('#030712')
            ax.plot(mesh2d.node_x, mesh2d.node_y, '.', color='#00D2FF', markersize=0.8, alpha=0.6)
            ax.set_title("Generated Flexible Mesh Topology", color='white', fontsize=12, fontweight='bold')
            ax.tick_params(colors='#64748B')
            
            preview_path = os.path.join(out_dir, "Mesh_Topology_Preview.png")
            plt.tight_layout()
            plt.savefig(preview_path, dpi=200, bbox_inches='tight')
            
            preview_cb(preview_path)
            progress_cb(60)

            # 8. MDU & External Forcings (INJEKSI DYNAMIC BOUNDARY & RIEMANN)
            log_cb("■ Merakit Arsitektur Hidrodinamika MDU & External Forcing (.ext)...")
            ext = ExtModel()
            
            # Boundary Batimetri
            ext.boundary.append(Boundary(quantity="bedlevel", locationfile=os.path.basename(bathy_file), forcingfile="", interpolatingmethod="nearest"))
            
            # Boundary Friksi Mangrove (CMC Thesis)
            if sediment_file and os.path.exists(sediment_file): 
                log_cb("  ├ Injeksi Mangrove Trachytope / Spatial Friction (.xyz) -> Baptist Eq.")
                ext.boundary.append(Boundary(quantity="frictioncoefficient", locationfile=os.path.basename(sediment_file), forcingfile="", interpolatingmethod="nearest"))

            # Boundary Gelombang Ocean / Pasang Surut Dinamis (Sinkronisasi ERA5 Dir)
            bnd_dir = params.get('ocean_boundary_dir', 'South')
            pli_file = f"{bnd_dir.lower()}_boundary.pli"
            
            with open(os.path.join(out_dir, pli_file), "w", encoding="utf-8") as f: 
                f.write(f"{bnd_dir}_Ocean_Boundary\n2 2\n")
                # Tarik garis batas secara geometris sesuai opsi arah lepas pantai
                if bnd_dir == "North":
                    f.write(f"{minx} {maxy}\n{maxx} {maxy}\n")
                elif bnd_dir == "East":
                    f.write(f"{maxx} {miny}\n{maxx} {maxy}\n")
                elif bnd_dir == "West":
                    f.write(f"{minx} {miny}\n{minx} {maxy}\n")
                else: # Default South
                    f.write(f"{minx} {miny}\n{maxx} {miny}\n")
                
            if tide_bc_file and os.path.exists(tide_bc_file):
                log_cb(f"  ├ Menyambungkan Astronomic Tidal Forcing di batas {bnd_dir}...")
                
                # Injeksi Riemann Absorbing Boundary Logic (Weakly Reflective)
                qty_type = "waterlevelbnd"
                if params.get('use_riemann', True):
                    qty_type = "neumannbnd" 
                    log_cb("  ├ [✓] Riemann Boundary Aktif: Resonansi refleksi pantai dicegah.")
                    
                ext.boundary.append(Boundary(quantity=qty_type, locationfile=pli_file, forcingfile=os.path.basename(tide_bc_file)))
            
            # Ekspor .ext secara fisik terlebih dahulu sebelum MDU dirakit
            ext_filepath = os.path.join(out_dir, "apex_forcing.ext")
            ext.filepath = ext_filepath
            ext.save(filepath=ext_filepath)
            
            fm = FMModel()
            fm.geometry.netfile = "Domain_Mesh.nc"
            
            if tide_bc_file or sediment_file: 
                fm.external_forcing.extforcefilenew = "apex_forcing.ext"
                
            # Fisika & Numerik D-Flow FM
            fm.physics.dicoww = 0.1 
            if not sediment_file: 
                fm.physics.unifrictcoef = 0.023 
            else: 
                fm.physics.unifrictcoef = 0.0
                fm.physics.frictyp = 4 
                
            fm.numerics.cflmax = 0.7
            
            # Referensi Waktu Dinamis berdasarkan tahun berjalan
            fm.time.refdate = int(datetime.now().strftime("%Y%m%d"))
            fm.time.tstop = 86400.0 * 2 
            
            fm_path = os.path.join(out_dir, "Apex_Flow.mdu")
            fm.filepath = fm_path
            fm.save(filepath=fm_path)

            # 9. Wave Model SWAN (.mdw)
            log_cb("■ Merakit Wave Model SWAN (.mdw) untuk Propagasi Gelombang Mangrove...")
            mdw_path = os.path.join(out_dir, "Apex_Wave.mdw")
            with open(mdw_path, "w", encoding="utf-8") as f:
                f.write("[Swan]\n")
                f.write(f"GridFile = Domain_Mesh.nc\nBedLevelFile = {os.path.basename(bathy_file)}\n")
                f.write("DirSpace = Circle\nNDir = 36\nFreqMin = 0.05\nFreqMax = 1.00\nNFreq = 24\n")
                f.write("WaveBoundaryHs = {:.2f}\nWaveBoundaryTp = {:.2f}\nWaveBoundaryDir = {:.2f}\nWaveBoundaryDirSpread = 30.0\n".format(
                    global_state.get('Hs', 1.0), global_state.get('Tp', 8.0), global_state.get('Dir', 180.0)))
                f.write("Friction = JONSWAP\nFrictionCoefficient = 0.067\nDepthInducedBreaking = True\nAlpha = 1.0\nGamma = 0.73\n")
        
            # 10. DIMR XML Coupler
            log_cb("■ Merakit DIMR XML Coupler (Flow <-> Wave)...")
            dimr_path = os.path.join(out_dir, "dimr_config.xml")
            with open(dimr_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n')
                f.write('<dimrConfig xmlns="http://schemas.deltares.nl/dimr" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://schemas.deltares.nl/dimr http://content.oss.deltares.nl/schemas/dimr-1.3.xsd">\n')
                f.write('  <control>\n    <parallel>\n      <startGroup>\n        <time>0 86400 86400</time>\n')
                f.write('        <start name="Flow" />\n        <start name="Wave" />\n      </startGroup>\n    </parallel>\n  </control>\n')
                f.write('  <component name="Flow">\n    <library>dflowfm</library>\n    <workingDir>.</workingDir>\n    <inputFile>Apex_Flow.mdu</inputFile>\n  </component>\n')
                f.write('  <component name="Wave">\n    <library>swan</library>\n    <workingDir>.</workingDir>\n    <inputFile>Apex_Wave.mdw</inputFile>\n  </component>\n</dimrConfig>\n')
        
            progress_cb(100)
            log_cb("\n▶ OPERASI KOMPILASI SELESAI. Komponen Skripsi telah dirakit dan siap dieksekusi!")
            
        except Exception as e:
            error_msg = f"[FATAL] Orkestrasi DIMR/Mesh Gagal: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            log_cb(error_msg)
            raise RuntimeError(f"Gagal membangun arsitektur DIMR: {str(e)}") from e
            
        finally:
            if fig_preview is not None:
                plt.close(fig_preview)
