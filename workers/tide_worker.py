# ==============================================================================
# APEX NEXUS TIER-0: TIDE LEAST SQUARES HARMONIC ANALYSIS (LSHA) ENGINE
# ==============================================================================
import logging
import traceback
import pandas as pd
import numpy as np
from utils.math_accel import solve_lsha

logger = logging.getLogger(__name__)

class TideAnalyzerEngine:
    """
    Tier-0 Execution Engine for Tidal Harmonic Constituent Extraction.
    Upgraded with:
    1. Rayleigh Criterion Guard (Dynamic Constituent Rejection).
    2. Corrected Astronomical Frequencies (SA & SSA).
    3. C-Contiguous Array Enforcement (Prevents C++/Numba memory segfaults).
    4. Strict Date/Time Parsing for messy sensor data.
    """
    
    @staticmethod
    def extract_harmonics(df: pd.DataFrame, col_time: str, col_z: str) -> tuple:
        try:
            logger.info("[LSHA] Memulai analisis harmonik pasang surut tingkat lanjut...")
            
            # 1. Strict Validation, De-duplication, & Pre-processing
            df_clean = df.dropna(subset=[col_time, col_z]).copy()
            
            # [ENTERPRISE FIX]: Robust Datetime Parsing
            # Mencoba mengurai waktu, menggunakan format mixed/dayfirst agar data sensor lokal tidak kacau.
            try:
                df_clean['parsed_time'] = pd.to_datetime(df_clean[col_time], format='mixed', dayfirst=True)
            except Exception:
                df_clean['parsed_time'] = pd.to_datetime(df_clean[col_time], errors='coerce')
                
            df_clean['parsed_z'] = pd.to_numeric(df_clean[col_z], errors='coerce')
            
            df_clean = df_clean.dropna(subset=['parsed_time', 'parsed_z']).sort_values('parsed_time')
            df_clean = df_clean.drop_duplicates(subset=['parsed_time'])
            
            # Z-Score Outlier Rejection
            z_mean_raw = df_clean['parsed_z'].mean()
            z_std_raw = df_clean['parsed_z'].std()
            if z_std_raw > 0:
                df_clean = df_clean[np.abs(df_clean['parsed_z'] - z_mean_raw) <= (4 * z_std_raw)]

            if len(df_clean) < 24:
                raise ValueError(f"Data observasi tidak memadai (Tersedia: {len(df_clean)} jam, Syarat: >= 24 jam).")
                
            # Konversi waktu ke jam relatif
            t_hours_raw = (df_clean['parsed_time'] - df_clean['parsed_time'].iloc[0]).dt.total_seconds().values / 3600.0
            z_raw = df_clean['parsed_z'].values
            
            data_duration_hours = t_hours_raw[-1] - t_hours_raw[0]
            
            # 2. Konstanta Frekuensi Sudut
            ALL_FREQS = {
                'M2': 0.505868,  'S2': 0.523599,  'N2': 0.496367,
                'K1': 0.262516,  'O1': 0.243352,  'P1': 0.261083,
                'SA': 0.000717,  'SSA': 0.001434 
            }
            
            # 3. Kriteria Rayleigh
            target_freqs = {}
            for name, freq in ALL_FREQS.items():
                if name in ['SA', 'SSA'] and data_duration_hours < 4000:
                    logger.warning(f"[LSHA] Kriteria Rayleigh Triggered: Durasi ({data_duration_hours:.1f}j) terlalu pendek untuk '{name}'.")
                    continue
                target_freqs[name] = freq
                
            # 4. Matrix Pre-Centering
            z_mean_stable = np.mean(z_raw)
            z_centered_raw = z_raw - z_mean_stable
            
            # [CRITICAL C++ BINDING FIX]: Ensure arrays are contiguous in memory
            # Jika Pandas mengembalikan slice/view memori yang terfragmentasi, modul C++/Numba
            # solve_lsha akan memicu Fatal Segmentation Fault / App Crash.
            t_hours = np.ascontiguousarray(t_hours_raw, dtype=np.float64)
            z_centered = np.ascontiguousarray(z_centered_raw, dtype=np.float64)
            omegas_array = np.ascontiguousarray(list(target_freqs.values()), dtype=np.float64)
            
            # 5. Eksekusi Numba-Accelerated LSHA Solver
            res = solve_lsha(t_hours, z_centered, omegas_array)
            
            if res is None or len(res) == 0:
                raise RuntimeError("LSHA Solver C++ mengembalikan hasil yang kosong/gagal (Matrix Deficient).")

            # 6. Rekonstruksi Amplitudo dan Fase
            msl = res[0] + z_mean_stable
            
            constituents = {name: {'amp': 0.0, 'pha': 0.0} for name in ALL_FREQS.keys()}
            
            for i, name in enumerate(target_freqs.keys()):
                A_c = res[1 + 2*i]
                A_s = res[2 + 2*i]
                
                amp = np.sqrt(A_c**2 + A_s**2)
                phase = np.degrees(np.arctan2(A_s, A_c)) % 360
                
                constituents[name] = {'amp': float(amp), 'pha': float(phase)}
                
            logger.info(f"[LSHA] Ekstraksi sukses. MSL: {msl:.3f} m, Active Constituents: {list(target_freqs.keys())}")
            return msl, constituents
            
        except Exception as e:
            error_msg = f"[FATAL] Ekstraksi LSHA gagal: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Gagal melakukan analisis harmonik: {str(e)}") from e
