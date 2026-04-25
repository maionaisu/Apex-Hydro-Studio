# ==============================================================================
# APEX NEXUS TIER-0: ENTERPRISE COMPILER (PYINSTALLER) - FINAL COMPREHENSIVE
# TARGET: ApexHydroStudio/main.py
# CAPABILITY: --onedir Enterprise, Conda DLL Recovery, Dask Lazy Eval, WebEngine, & Geo-Spatial
# ==============================================================================
import os
import sys
import shutil
import PyInstaller.__main__
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

sys.setrecursionlimit(10000)

print("=====================================================")
print(" ⚡ APEX HYDRO-STUDIO — ENTERPRISE COMPILER v18.0 ⚡ ")
print("=====================================================")

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
APEX_DIR = REPO_ROOT if os.path.exists(os.path.join(REPO_ROOT, 'main.py')) else os.path.join(REPO_ROOT, 'ApexHydroStudio')
SCRIPT = os.path.join(APEX_DIR, 'main.py')

if not os.path.exists(SCRIPT):
    print(f"[FATAL] Entry point 'main.py' not found at: {SCRIPT}")
    sys.exit(1)

CONDA_PREFIX = os.environ.get('CONDA_PREFIX', '')
BIN_PATH = ""
if CONDA_PREFIX:
    BIN_PATH = os.path.join(CONDA_PREFIX, 'Library', 'bin')
    if not os.path.exists(BIN_PATH):
        BIN_PATH = os.path.join(CONDA_PREFIX, 'bin')

print(f"[*] Conda Binary Path Detected: {BIN_PATH}")

for folder in ['build', 'dist', 'build_temp', '__pycache__']:
    fp = os.path.join(REPO_ROOT, folder)
    if os.path.exists(fp):
        print(f"[*] Cleaning legacy build folder: '{folder}'...")
        shutil.rmtree(fp, ignore_errors=True)

# ── TIER-0 RUNTIME HOOK ──────────────────────────────────────────────────────
hook_path = os.path.join(REPO_ROOT, '_rthook_apex.py')
with open(hook_path, 'w') as hf:
    hf.write("""import os, sys
if hasattr(sys, '_MEIPASS'):
    os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
    
    # 1. EPSG PROJ DATABASE FIX
    proj_paths = [
        os.path.join(sys._MEIPASS, 'pyproj', 'proj_dir', 'share', 'proj'),
        os.path.join(sys._MEIPASS, 'pyproj', 'data')
    ]
    for p_lib in proj_paths:
        if os.path.exists(p_lib):
            os.environ['PROJ_LIB'] = p_lib
            break
            
    # 2. GDAL DATA FIX (FOR GEOPANDAS / SHP FILES)
    gdal_paths = [
        os.path.join(sys._MEIPASS, 'fiona', 'gdal_data'),
        os.path.join(sys._MEIPASS, 'osgeo', 'data', 'gdal')
    ]
    for g_lib in gdal_paths:
        if os.path.exists(g_lib):
            os.environ['GDAL_DATA'] = g_lib
            break

    # 3. SSL CERTIFICATES FIX (FOR COPERNICUS ERA5 DOWNLOADS)
    cert_path = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
    if os.path.exists(cert_path):
        os.environ['SSL_CERT_FILE'] = cert_path
        os.environ['REQUESTS_CA_BUNDLE'] = cert_path
            
    # 4. QT WEBENGINE BROWSER FIX
    possible_paths = [
        os.path.join(sys._MEIPASS, 'PyQt6', 'Qt6', 'bin', 'QtWebEngineProcess.exe'),
        os.path.join(sys._MEIPASS, 'PyQt6', 'QtWebEngineProcess.exe'),
        os.path.join(sys._MEIPASS, 'QtWebEngineProcess.exe')
    ]
    for p in possible_paths:
        if os.path.exists(p):
            os.environ['QTWEBENGINEPROCESS_PATH'] = p
            break
""")
print(f"[*] Runtime hook injected → {hook_path}")

print("[*] Collecting metadata, dynamic libs, and submodules...")

def safe_collect_data(pkg):
    try: return collect_data_files(pkg)
    except Exception: return []

def safe_collect_libs(pkg):
    try: return collect_dynamic_libs(pkg)
    except Exception: return []

def safe_collect_mods(pkg):
    try: return collect_submodules(pkg)
    except Exception: return []

mk_datas         = safe_collect_data('meshkernel')
mk_binaries      = safe_collect_libs('meshkernel')
dfm_datas        = safe_collect_data('dfm_tools')
hydrolib_datas   = safe_collect_data('hydrolib.core')
xugrid_datas     = safe_collect_data('xugrid')
pooch_datas      = safe_collect_data('pooch')
ddlpy_datas      = safe_collect_data('ddlpy')
pyproj_datas     = safe_collect_data('pyproj')
geopandas_datas  = safe_collect_data('geopandas')
fiona_datas      = safe_collect_data('fiona')
fiona_binaries   = safe_collect_libs('fiona')
shapely_binaries = safe_collect_libs('shapely')
xarray_datas     = safe_collect_data('xarray')
netcdf_binaries  = safe_collect_libs('netCDF4')
qtweb_datas      = safe_collect_data('PyQt6.QtWebEngineCore')

# [ENTERPRISE FIX]: Komponen Krusial Tambahan
certifi_datas    = safe_collect_data('certifi')
matplotlib_datas = safe_collect_data('matplotlib')

fiona_hidden     = safe_collect_mods('fiona')
gpd_hidden       = safe_collect_mods('geopandas')
xarray_hidden    = safe_collect_mods('xarray')
dask_hidden      = safe_collect_mods('dask')
pyproj_hidden    = safe_collect_mods('pyproj')
matplotlib_hid   = safe_collect_mods('matplotlib')

SEP = os.pathsep

pyinstaller_args = [
    SCRIPT,
    '--onedir',          
    '--console',         
    '--noconfirm',       
    '--name=ApexHydroStudio',
    f'--runtime-hook={hook_path}',
    '--noupx',           

    f'--paths={BIN_PATH}',
    '--exclude-module=enum34',

    # ── HIDDEN IMPORTS ───────────────────────────────────────────────────────
    '--hidden-import=pandas',
    '--hidden-import=numpy',
    '--hidden-import=scipy',
    '--hidden-import=scipy.special.cython_special',
    '--hidden-import=scipy.spatial.transform',
    '--hidden-import=netCDF4',
    '--hidden-import=cdsapi',
    '--hidden-import=h5py',
    '--hidden-import=h5netcdf',
    '--hidden-import=numba',
    '--hidden-import=numba.core',
    '--hidden-import=llvmlite',
    '--hidden-import=dask',
    '--hidden-import=distributed',
    '--hidden-import=cloudpickle',
    
    # Network & SSL untuk ERA5
    '--hidden-import=certifi',
    '--hidden-import=requests',
    '--hidden-import=urllib3',
    
    # Rendering untuk Modul 6 PostProc
    '--hidden-import=matplotlib',
    '--hidden-import=matplotlib.backends.backend_agg',

    # GIS
    '--hidden-import=fiona._shim',
    '--hidden-import=fiona.schema',
    '--hidden-import=shapely',
    '--hidden-import=shapely.geometry',
    '--hidden-import=pyproj',
    '--hidden-import=geopandas',

    # Deltares
    '--hidden-import=xugrid',
    '--hidden-import=pooch',
    '--hidden-import=ddlpy',
    '--hidden-import=meshkernel',
    '--hidden-import=dfm_tools',
    '--hidden-import=hydrolib.core.dflowfm.mdu.models',
    '--hidden-import=hydrolib.core.dflowfm.ext.models',

    # PyQt
    '--hidden-import=PyQt6.QtCore',
    '--hidden-import=PyQt6.QtGui',
    '--hidden-import=PyQt6.QtWidgets',
    '--hidden-import=PyQt6.QtWebEngineWidgets',
    '--hidden-import=PyQt6.QtWebEngineCore',
    '--hidden-import=PyQt6.QtWebChannel',
    '--hidden-import=PyQt6.sip',
    
    # Modul Internal
    '--hidden-import=ui.views.modul1_era5',
    '--hidden-import=ui.views.modul2_sediment',
    '--hidden-import=ui.views.modul3_tide',
    '--hidden-import=ui.views.modul4_mesh',
    '--hidden-import=ui.views.modul5_execution',
    '--hidden-import=ui.views.modul6_postproc',
    '--hidden-import=ui.components.core_widgets',
    '--hidden-import=ui.components.web_bridge',
    '--hidden-import=workers.era5_worker',
    '--hidden-import=workers.mesh_worker',
    '--hidden-import=workers.postproc_worker',
    '--hidden-import=workers.sediment_worker',
    '--hidden-import=workers.tide_worker',
    '--hidden-import=engines.era5_extractor',
    '--hidden-import=engines.mesh_builder',
    '--hidden-import=engines.postproc_engine',
    '--hidden-import=engines.sediment_mapper',
    '--hidden-import=engines.tide_lsha',
    '--hidden-import=engines.dimr_executor',
    '--hidden-import=core.state_manager',
    '--hidden-import=utils.config',
    '--hidden-import=utils.math_accel',

    '--clean',
    '--workpath=./build_temp',
    '--distpath=./dist',
]

if BIN_PATH:
    critical_dlls = ['hdf5.dll', 'netcdf.dll', 'msvcp140.dll', 'vcruntime140.dll', 'libcurl.dll']
    for dll in critical_dlls:
        target_dll = os.path.join(BIN_PATH, dll)
        if os.path.exists(target_dll):
            pyinstaller_args.append(f'--add-binary={target_dll}{SEP}.')

for mod in fiona_hidden + gpd_hidden + xarray_hidden + dask_hidden + pyproj_hidden + matplotlib_hid:
    pyinstaller_args.append(f'--hidden-import={mod}')

all_binaries = mk_binaries + fiona_binaries + shapely_binaries + netcdf_binaries
for b in all_binaries:
    pyinstaller_args.append(f'--add-binary={b[0]}{SEP}{b[1]}')

all_datas = (mk_datas + dfm_datas + hydrolib_datas + xugrid_datas +
             pooch_datas + ddlpy_datas + pyproj_datas +
             geopandas_datas + fiona_datas + xarray_datas + qtweb_datas + 
             certifi_datas + matplotlib_datas)

seen_datas = set()
for data in all_datas:
    key = (data[0], data[1])
    if key not in seen_datas:
        seen_datas.add(key)
        pyinstaller_args.append(f'--add-data={data[0]}{SEP}{data[1]}')

assets_dir = os.path.join(APEX_DIR, "assets")
if os.path.exists(assets_dir):
    pyinstaller_args.append(f'--add-data={assets_dir}{SEP}assets')

ico_path = os.path.join(APEX_DIR, 'assets', 'Apex Wave Studio.ico')
if os.path.exists(ico_path):
    pyinstaller_args.append(f'--icon={ico_path}')

print("\n[*] Starting Enterprise Compilation... This will take 5-15 minutes.\n")
try:
    PyInstaller.__main__.run(pyinstaller_args)
    print("\n" + "="*55)
    print(" ✅ COMPILATION COMPLETE!")
    print(" -> App Folder  : dist/ApexHydroStudio/")
    print(" -> Executable  : dist/ApexHydroStudio/ApexHydroStudio.exe")
    print("="*55)
except Exception as e:
    print(f"\n❌ [FATAL] Compilation failed: {e}")
finally:
    if os.path.exists(hook_path):
        try:
            os.remove(hook_path)
        except:
            pass
