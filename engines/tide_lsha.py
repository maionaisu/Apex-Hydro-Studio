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
    Leverages O(N) optimized Numba matrix solving and robust Pandas >= 2.x parsing.
    """
    
    @staticmethod
    def extract_harmonics(df: pd.DataFrame, col_time: str, col_z: str) -> tuple:
        """
        Parses time-series water elevation and runs LSHA.
        Returns a tuple of (msl, constituents_dictionary).
        """
        try:
            logger.info("[LSHA] Memulai analisis harmonik pasang surut...")
            
            # 1. Strict Validation & Pre-processing
            df_clean = df.dropna(subset=[col_time, col_z]).copy()
            
            # BUG-04 FIX: infer_datetime_format=True dihapus (Deprecated di Pandas >= 2.0)
            df_clean['parsed_time'] = pd.to_datetime(df_clean[col_time], errors='coerce')
            
            # Coerce water levels ke numeric dan drop baris yang rusak (NaN)
            df_clean['parsed_z'] = pd.to_numeric(df_clean[col_z], errors='coerce')
            df_clean = df_clean.dropna(subset=['parsed_time', 'parsed_z']).sort_values('parsed_time')
            
            # Validasi panjang data minimal untuk LSHA yang akurat
            if len(df_clean) < 24:
                raise ValueError(f"Data elevasi pasang surut tidak memadai (Tersedia: {len(df_clean)} jam, Syarat: >= 24 jam).")
                
            # Konversi waktu ke jam relatif terhadap baris pertama
            t_hours = (df_clean['parsed_time'] - df_clean['parsed_time'].iloc[0]).dt.total_seconds().values / 3600.0
            z = df_clean['parsed_z'].values
            
            # 2. Konstanta Frekuensi Sudut Pasang Surut (Rad/Jam)
            freqs = {
                'M2': 0.505868, 'S2': 0.523599, 'N2': 0.496367, 
                'K1': 0.262516, 'O1': 0.243352, 'P1': 0.261083, 
                'SA': 0.000114, 'SSA': 0.000228
            }
            
            # Numba membutuhkan array NumPy murni, bukan dictionary keys/values
            omegas_array = np.array(list(freqs.values()), dtype=np.float64)
            
            # 3. Eksekusi Numba-Accelerated LSHA Solver
            # Aman terhadap Matriks Singular (Memanfaatkan BUG-05 FIX SVD Fallback)
            res = solve_lsha(t_hours, z, omegas_array)
            
            if res is None or len(res) == 0:
                raise RuntimeError("LSHA Solver mengembalikan hasil yang kosong/gagal.")

            # 4. Rekonstruksi Amplitudo dan Fase
            msl = res[0]
            constituents = {}
            
            for i, name in enumerate(freqs.keys()):
                A_c = res[1 + 2*i]
                A_s = res[2 + 2*i]
                
                # Menghitung amplitudo mutlak
                amp = np.sqrt(A_c**2 + A_s**2)
                # Menghitung fase dan mengunci pada domain 0-360 derajat
                phase = np.degrees(np.arctan2(A_s, A_c)) % 360
                
                constituents[name] = {'amp': amp, 'pha': phase}
                
            logger.info(f"[LSHA] Ekstraksi sukses. MSL: {msl:.3f} m, Constituents: {list(constituents.keys())}")
            return msl, constituents
            
        except Exception as e:
            error_msg = f"[FATAL] Ekstraksi LSHA gagal: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            # Exception Chaining untuk debugging yang lebih presisi di QThread Worker
            raise RuntimeError(f"Gagal melakukan analisis harmonik: {str(e)}") from e
