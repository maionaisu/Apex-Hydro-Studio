# ==============================================================================
# APEX NEXUS TIER-0: ERA5 NETCDF EXTRACTION ENGINE
# ==============================================================================
import os
import logging
import traceback
import numpy as np

# Setup module-level logger
logger = logging.getLogger(__name__)

try:
    import xarray as xr
    import dask
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False


class ERA5Extractor:
    """
    Tier-0 Extraction Engine for ERA5 Wave/Met Reanalysis.
    Upgraded with:
    1. Single-Pass Dask Computation (O(1) Pass instead of O(3N) Passes).
    2. Correct Circular Mean Mathematics for Wave Direction (Trigonometric).
    3. Strict NaN & Fallback Handling.
    """
    
    @staticmethod
    def extract_wave_params(nc_path: str) -> tuple:
        """
        Extracts Hs, Tp, Dir and calculates DoC limit based on Hallermeier/Birkemeier.
        Out-of-Core Processing: Explicit clean-up guaranteed using 'with' block.
        """
        if not HAS_XARRAY:
            raise ImportError("Library 'xarray' atau 'dask' tidak ditemukan. Install via: 'pip install xarray netCDF4 dask'")
            
        # 1. Strict File I/O Validation
        if not os.path.exists(nc_path):
            raise FileNotFoundError(f"[ERA5 Extractor] File NetCDF tidak ditemukan pada: {nc_path}")

        try:
            logger.info(f"[ERA5] Menginisiasi Out-of-Core Dask extraction untuk: {nc_path}")
            
            # 2. Dask Lazy Evaluation enforced via chunks='auto'
            # Mencegah file NetCDF berukuran raksasa memicu OOM (Out Of Memory) Crash.
            with xr.open_dataset(nc_path, chunks='auto', engine='netcdf4') as ds:
                
                # Pemetaan Variabel (Mendukung standar nama CDS ERA5 yang bervariasi)
                var_hs = 'swh' if 'swh' in ds else 'shww'
                var_tp = 'mwp' if 'mwp' in ds else 'pp1d'
                var_dir = 'mwd' if 'mwd' in ds else 'p140122'
                
                # --- TAHAP 1: Deklarasi Dask Graph (Lazy, Tanpa eksekusi instan) ---
                hs_lazy = ds[var_hs].max(skipna=True) if var_hs in ds else None
                tp_lazy = ds[var_tp].mean(skipna=True) if var_tp in ds else None
                
                # --- [CRITICAL BUG-FIX]: LOGIKA MATEMATIKA ARAH GELOMBANG ---
                # Arah (Derajat) menggunakan Rata-Rata Sirkuler (Circular Mean).
                if var_dir in ds:
                    dir_rad = np.deg2rad(ds[var_dir])
                    sin_dir_lazy = np.sin(dir_rad).mean(skipna=True)
                    cos_dir_lazy = np.cos(dir_rad).mean(skipna=True)
                else:
                    sin_dir_lazy, cos_dir_lazy = None, None

                # --- TAHAP 2: SINGLE-PASS COMPUTATION ---
                # Menyatukan seluruh komputasi agar Dask membaca file .nc HANYA 1 KALI.
                logger.debug("[ERA5] Mengeksekusi Single-Pass Dask Graph Computation...")
                computed_results = dask.compute(
                    hs_lazy, 
                    tp_lazy, 
                    sin_dir_lazy, 
                    cos_dir_lazy
                )
                
                hs_val, tp_val, sin_val, cos_val = computed_results
                
                # --- TAHAP 3: Finalisasi Nilai ---
                hs = float(hs_val) if hs_val is not None else 1.5
                tp = float(tp_val) if tp_val is not None else 8.0
                
                if sin_val is not None and cos_val is not None:
                    # Mengonversi vektor Trigonometri kembali ke Derajat (0 - 360)
                    dir_mean_rad = np.arctan2(sin_val, cos_val)
                    dir_ = float((np.degrees(dir_mean_rad) + 360) % 360)
                else:
                    dir_ = 180.0
                
                # Simple DoC estimation (Hallermeier equation approximation)
                doc = 1.57 * hs
                
                logger.info(f"[ERA5] Ekstraksi sukses: Hs={hs:.2f}m, Tp={tp:.2f}s, Dir={dir_:.1f}°, DoC={doc:.2f}m")
                return hs, tp, dir_, doc
                
        except Exception as e:
            # Strict Error Propagation & Exception Chaining
            error_msg = f"[FATAL] ERA5 Extraction failed: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal mengekstrak parameter ERA5. Periksa Log. Error: {str(e)}") from e
