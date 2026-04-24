# ==============================================================================
# APEX NEXUS TIER-0: ENTERPRISE COMPILER (PYINSTALLER)
# TARGET: ApexHydroStudio/main.py
# CAPABILITY: --onedir Enterprise, Numba LLVM, & QtWebEngine Auto-Discovery
# ==============================================================================
import os
import sys
import shutil
import PyInstaller.__main__
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# [CRITICAL GUARD]: Aplikasi hidro-saintifik (Xarray, Numba, Pandas) memiliki
# pohon dependensi (Abstract Syntax Tree) yang sangat dalam. 
# Meningkatkan limit rekursi mencegah PyInstaller Crash (RecursionError) saat kompilasi.
sys.setrecursionlimit(7000)

print(f"[BUILD] Python aktif: {sys.version}")
print(f"[BUILD] Executable  : {sys.executable}")
if sys.version_info < (3, 10):
    print("[FATAL] Diperlukan Python >= 3.10.")
    sys.exit(1)

print("=====================================================")
print(" ⚡ APEX HYDRO-STUDIO — ENTERPRISE COMPILER v18.0 ⚡ ")
print("=====================================================")

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
# Asumsi script ini berada sejajar dengan folder ApexHydroStudio/
APEX_DIR  = os.path.join(REPO_ROOT, 'ApexHydroStudio')

# Jika script ini berada di DALAM ApexHydroStudio, gunakan REPO_ROOT langsung
if not os.path.exists(APEX_DIR):
    APEX_DIR = REPO_ROOT

SCRIPT = os.path.join(APEX_DIR, 'main.py')

if not os.path.exists(SCRIPT):
    print(f"[FATAL] Entry point tidak ditemukan di: {SCRIPT}")
    sys.exit(1)

logo_ico = os.path.join(APEX_DIR, 'assets', 'Apex Wave Studio.ico')
logo_png = os.path.join(APEX_DIR, 'assets', 'Apex Wave Studio.png')

# ── 1. CLEANUP SISA KOMPILASI LAMA ────────────────────────────────────────────
for folder in ['build', 'dist', 'build_temp', '__pycache__']:
    fp = os.path.join(REPO_ROOT, folder)
    if os.path.exists(fp):
        print(f"[*] Membersihkan folder temp: '{folder}'...")
        shutil.rmtree(fp, ignore_errors=True)

# ── 2. TIER-0 RUNTIME HOOK (QtWebEngine Process Locator) ──────────────────────
# FIX ABSOLUT: Memaksa QtWebEngine mencari lokasinya di folder sistem bawaan
hook_path = os.path.join(REPO_ROOT, '_rthook_apex.py')
with open(hook_path, 'w') as hf:
    hf.write("""import os, sys
if hasattr(sys, '_MEIPASS'):
    # Matikan sandbox Chromium agar tidak berkonflik dengan permission OS
    os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'
    
    # Deteksi lokasi QtWebEngineProcess.exe di ekstrak / folder _internal PyInstaller
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
print(f"[*] Runtime hook QtWebEngine diinjeksi → {hook_path}")

# ── 3. SAFE DEPENDENCY COLLECTION ────────────────────────────────────────────
print("[*] Mengekstrak metadata, DLL, dan data biner ekosistem...")

def safe_collect_data(pkg):
    try: return collect_data_files(pkg)
    except Exception: return []

def safe_collect_libs(pkg):
    try: return collect_dynamic_libs(pkg)
    except Exception: return []

def safe_collect_mods(pkg):
    try: return collect_submodules(pkg)
    except Exception: return []

# Kumpulkan semua file pendukung fisika & spasial
mk_datas        = safe_collect_data('meshkernel')
mk_binaries     = safe_collect_libs('meshkernel')
dfm_datas       = safe_collect_data('dfm_tools')
hydrolib_datas  = safe_collect_data('hydrolib.core')
xugrid_datas    = safe_collect_data('xugrid')
pooch_datas     = safe_collect_data('pooch')
ddlpy_datas     = safe_collect_data('ddlpy')
pyproj_datas    = safe_collect_data('pyproj')
geopandas_datas = safe_collect_data('geopandas')
fiona_datas     = safe_collect_data('fiona')
fiona_binaries  = safe_collect_libs('fiona')
shapely_binaries= safe_collect_libs('shapely')
xarray_datas    = safe_collect_data('xarray')
netcdf_binaries = safe_collect_libs('netCDF4')

fiona_hidden    = safe_collect_mods('fiona')
gpd_hidden      = safe_collect_mods('geopandas')
xarray_hidden   = safe_collect_mods('xarray')

# ── 4. BUILD ARGUMENTS (--ONEDIR ENTERPRISE) ─────────────────────────────────
SEP = os.pathsep

pyinstaller_args = [
    SCRIPT,
    '--onedir',          # [UBAH UTAMA]: Mode Folder untuk Loading App secara INSTAN (0 detik)
    '--windowed',        # Hilangkan console hitam (CMD) di belakang GUI
    '--name=ApexHydroStudio',
    f'--runtime-hook={hook_path}',
    '--noupx',           # [KRUSIAL]: UPX Compression merusak DLL Numba & PyQt6, JANGAN GUNAKAN.

    # ── CORE HIDDEN IMPORTS ──────────────────────────────────────────────────
    '--hidden-import=pandas',
    '--hidden-import=numpy',
    '--hidden-import=scipy',
    '--hidden-import=pyproj',
    '--hidden-import=netCDF4',
    '--hidden-import=cdsapi',
    '--hidden-import=h5py',
    '--hidden-import=h5netcdf',
    '--hidden-import=numba',
    '--hidden-import=numba.core',
    '--hidden-import=llvmlite',

    # ── FIONA / GIS ───────────────────────────────────────────────────────────
    '--hidden-import=fiona._shim',
    '--hidden-import=fiona.schema',

    # ── DELTARES ECOSYSTEM ────────────────────────────────────────────────────
    '--hidden-import=xugrid',
    '--hidden-import=pooch',
    '--hidden-import=ddlpy',
    '--hidden-import=meshkernel',
    '--hidden-import=dfm_tools',
    '--hidden-import=hydrolib.core.dflowfm.mdu.models',
    '--hidden-import=hydrolib.core.dflowfm.ext.models',

    # ── PYQT6 WEBENGINE ──────────────────────────────────────────────────────
    '--hidden-import=PyQt6.QtCore',
    '--hidden-import=PyQt6.QtGui',
    '--hidden-import=PyQt6.QtWidgets',
    '--hidden-import=PyQt6.QtWebEngineWidgets',
    '--hidden-import=PyQt6.QtWebEngineCore',
    '--hidden-import=PyQt6.QtWebChannel',

    # ── INTERNAL APP MODULES ─────────────────────────────────────────────────
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

    # [NEW]: Memasukkan pustaka GPU CUDA
    '--hidden-import=cupy',
    '--hidden-import=cupyx',

    '--clean',
    '--workpath=./build_temp',
    '--distpath=./dist',

    # ── DATA INJECTION ────────────────────────────────────────────────────────
    f'--add-data={os.path.join(APEX_DIR, "assets")}{SEP}assets',
]

for mod in fiona_hidden + gpd_hidden + xarray_hidden:
    pyinstaller_args.append(f'--hidden-import={mod}')

all_binaries = mk_binaries + fiona_binaries + shapely_binaries + netcdf_binaries
for binary in all_binaries:
    pyinstaller_args.append(f'--add-binary={binary[0]}{SEP}{binary[1]}')

all_datas = (mk_datas + dfm_datas + hydrolib_datas + xugrid_datas +
             pooch_datas + ddlpy_datas + pyproj_datas +
             geopandas_datas + fiona_datas + xarray_datas)

seen_datas = set()
for data in all_datas:
    key = (data[0], data[1])
    if key not in seen_datas:
        seen_datas.add(key)
        pyinstaller_args.append(f'--add-data={data[0]}{SEP}{data[1]}')

if os.path.exists(logo_ico):
    print(f"[*] Menambahkan icon: {logo_ico}")
    pyinstaller_args.append(f'--icon={logo_ico}')

# ── 5. EXECUTE BUILD ─────────────────────────────────────────────────────────
print("\n[*] Mengeksekusi PyInstaller --onedir (Mode Folder)... (Estimasi: 5-15 menit)\n")
try:
    PyInstaller.__main__.run(pyinstaller_args)
    print("\n" + "="*55)
    print(" ✅ KOMPILASI ENTERPRISE SELESAI!")
    print(" -> Folder aplikasi : dist/ApexHydroStudio/")
    print(" -> File Eksekusi   : dist/ApexHydroStudio/ApexHydroStudio.exe")
    print(" -> CATATAN: Aplikasi menggunakan mode Folder (--onedir).")
    print("    Saat diklik ganda, aplikasi akan terbuka secara INSTAN (0 detik)")
    print("    tanpa perlu melakukan ekstraksi memori. Bawa folder ini (atau di-zip)")
    print("    saat presentasi dosen!")
    print("="*55)
except Exception as e:
    print(f"\n❌ [FATAL] Kompilasi gagal: {e}")
finally:
    if os.path.exists(hook_path):
        os.remove(hook_path)
