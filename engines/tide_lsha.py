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
    3. Z-Score Outlier Rejection & Matrix Pre-Centering for numerical stability.
    """
    
    @staticmethod
    def extract_harmonics(df: pd.DataFrame, col_time: str, col_z: str) -> tuple:
        """
        Parses time-series water elevation and runs LSHA.
        Returns a tuple of (msl, constituents_dictionary).
        """
        try:
            logger.info("[LSHA] Memulai analisis harmonik pasang surut tingkat lanjut...")
            
            # 1. Strict Validation, De-duplication, & Pre-processing
            df_clean = df.dropna(subset=[col_time, col_z]).copy()
            df_clean['parsed_time'] = pd.to_datetime(df_clean[col_time], errors='coerce')
            df_clean['parsed_z'] = pd.to_numeric(df_clean[col_z], errors='coerce')
            
            # Hapus data kosong, urutkan, dan pastikan tidak ada timestamp duplikat (Sensor Glitch)
            df_clean = df_clean.dropna(subset=['parsed_time', 'parsed_z']).sort_values('parsed_time')
            df_clean = df_clean.drop_duplicates(subset=['parsed_time'])
            
            # Z-Score Outlier Rejection (Menghapus paku/spike ekstrim > 4 Standar Deviasi)
            z_mean_raw = df_clean['parsed_z'].mean()
            z_std_raw = df_clean['parsed_z'].std()
            if z_std_raw > 0:
                df_clean = df_clean[np.abs(df_clean['parsed_z'] - z_mean_raw) <= (4 * z_std_raw)]

            if len(df_clean) < 24:
                raise ValueError(f"Data observasi tidak memadai (Tersedia: {len(df_clean)} jam, Syarat: >= 24 jam).")
                
            # Konversi waktu ke jam relatif (T=0 pada data pertama)
            # Catatan: Math_accel engine (C++) mengasumsikan satuan waktu (T) dan 
            # kecepatan sudut (Omega) sinkron. Jika T dalam jam, Omega wajib rad/jam.
            t_hours = (df_clean['parsed_time'] - df_clean['parsed_time'].iloc[0]).dt.total_seconds().values / 3600.0
            z = df_clean['parsed_z'].values
            
            data_duration_hours = t_hours[-1] - t_hours[0]
            
            # 2. Konstanta Frekuensi Sudut Pasang Surut yang BENAR (Rad/Jam)
            # [BUG-FIX] SA & SSA frekuensi pada kode lama salah. 
            # Nilai dikoreksi sesuai konstanta astronomis (2*pi / Period in Hours).
            ALL_FREQS = {
                'M2': 0.505868,  # Principal lunar semidiurnal (12.42 jam)
                'S2': 0.523599,  # Principal solar semidiurnal (12.00 jam)
                'N2': 0.496367,  # Larger lunar elliptic semidiurnal (12.66 jam)
                'K1': 0.262516,  # Lunar diurnal (23.93 jam)
                'O1': 0.243352,  # Lunar diurnal (25.82 jam)
                'P1': 0.261083,  # Solar diurnal (24.07 jam)
                'SA': 0.000717,  # Solar annual (~8766 jam) -> Sblmnya salah ketik 0.000114
                'SSA': 0.001434  # Solar semiannual (~4383 jam) -> Sblmnya salah ketik 0.000228
            }
            
            # 3. Kriteria Rayleigh (Dynamic Parameter Allocation)
            # Mencegah matriks Singular. Jika data < 6 bulan (~4000 jam), SA dan SSA 
            # MUSTAHIL diekstrak secara matematis dan akan merusak kalkulasi.
            target_freqs = {}
            for name, freq in ALL_FREQS.items():
                if name in ['SA', 'SSA'] and data_duration_hours < 4000:
                    logger.warning(f"[LSHA] Kriteria Rayleigh Triggered: Durasi data ({data_duration_hours:.1f}j) terlalu pendek untuk mengekstrak '{name}'. Komponen diabaikan/di-nol-kan.")
                    continue
                target_freqs[name] = freq
                
            omegas_array = np.array(list(target_freqs.values()), dtype=np.float64)
            
            # 4. Matrix Pre-Centering (Numerical Stability Guard)
            # Memudahkan Least Square untuk menemukan titik potong (intercept) Z0.
            z_mean_stable = np.mean(z)
            z_centered = z - z_mean_stable
            
            # 5. Eksekusi Numba-Accelerated LSHA Solver
            res = solve_lsha(t_hours, z_centered, omegas_array)
            
            if res is None or len(res) == 0:
                raise RuntimeError("LSHA Solver C++ mengembalikan hasil yang kosong/gagal (Matrix Deficient).")

            # 6. Rekonstruksi Amplitudo dan Fase (Un-centering)
            msl = res[0] + z_mean_stable
            
            # Pre-fill seluruh dictionary dengan 0 (Termasuk SA/SSA yang mungkin dibuang)
            # agar Modul 3 UI dan Modul 4 tidak error akibat KeyNotFound
            constituents = {name: {'amp': 0.0, 'pha': 0.0} for name in ALL_FREQS.keys()}
            
            for i, name in enumerate(target_freqs.keys()):
                A_c = res[1 + 2*i]
                A_s = res[2 + 2*i]
                
                # Pythagoras untuk Amplitudo absolut
                amp = np.sqrt(A_c**2 + A_s**2)
                # Trigonometri Fase (Dikunci pada domain melingkar 0-360 derajat)
                phase = np.degrees(np.arctan2(A_s, A_c)) % 360
                
                constituents[name] = {'amp': float(amp), 'pha': float(phase)}
                
            logger.info(f"[LSHA] Ekstraksi sukses. MSL: {msl:.3f} m, Active Constituents: {list(target_freqs.keys())}")
            return msl, constituents
            
        except Exception as e:
            error_msg = f"[FATAL] Ekstraksi LSHA gagal: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            # Exception Chaining untuk debugging yang lebih presisi di QThread Worker
            raise RuntimeError(f"Gagal melakukan analisis harmonik: {str(e)}") from e
