# ==============================================================================
# APEX NEXUS TIER-0: NUMBA-ACCELERATED MATH ENGINE (HARDENED)
# ==============================================================================
import numpy as np
from numba import njit, prange
import logging
import traceback

logger = logging.getLogger(__name__)

# [ENTERPRISE FIX]: Menambahkan parallel=True agar prange benar-benar menggunakan Multi-Core CPU
@njit(nopython=True, cache=True, fastmath=True, parallel=True)
def build_design_matrix(t_array: np.ndarray, omegas: np.ndarray) -> np.ndarray:
    """
    O(N*K) Numba-accelerated construction of the LSHA design matrix.
    Optimized with fastmath, multi-threading (parallel), and unit-agnostic time indexing.
    """
    N = len(t_array)
    K = len(omegas)
    # Pre-allocate memory: [Intercept, Cos1, Sin1, Cos2, Sin2, ...]
    A = np.ones((N, 1 + 2 * K), dtype=np.float64)
    
    for i in range(K):
        # Pre-calculating the angular progression
        w = omegas[i]
        # prange sekarang akan mendistribusikan beban ke seluruh core/thread CPU
        for j in prange(N):
            phase = w * t_array[j]
            A[j, 1 + 2 * i] = np.cos(phase)
            A[j, 2 + 2 * i] = np.sin(phase)
            
    return A

@njit(nopython=True, cache=True, fastmath=True)
def fast_normal_equations(A: np.ndarray, h: np.ndarray):
    """
    O(N*K^2) Numba-accelerated formation of Normal Equations (AtA x = Ath).
    Leverages BLAS matrix multiplication optimization.
    """
    AtA = A.T @ A
    Ath = A.T @ h
    return AtA, Ath

def solve_lsha(t_array: np.ndarray, h: np.ndarray, omegas: np.ndarray) -> np.ndarray:
    """
    Tier-0 Robust Least Squares Harmonic Analysis solver.
    Implements BUG-05 & BUG-17 FIX: 
    - Floating point stability via time-centering.
    - Strict condition number monitoring.
    - High-precision SVD fallback.
    """
    try:
        # [HARDENING]: Pastikan input adalah Contiguous C-Array tipe Float64 
        # agar Numba tidak melemparkan TypeError pada runtime
        t_array = np.ascontiguousarray(t_array, dtype=np.float64)
        h = np.ascontiguousarray(h, dtype=np.float64)
        omegas = np.ascontiguousarray(omegas, dtype=np.float64)

        if len(t_array) != len(h):
            raise ValueError(f"Dimensi tidak selaras: t({len(t_array)}) != h({len(h)})")
        if len(t_array) == 0:
            return np.zeros(1 + 2 * len(omegas), dtype=np.float64)

        # Time-Centering
        t_offset = np.median(t_array)
        t_stable = t_array - t_offset

        # 1. Build design matrix (Accelerated)
        A = build_design_matrix(t_stable, omegas)
        
        # 2. Form Normal Equations
        AtA, Ath = fast_normal_equations(A, h)
        
        # 3. Condition Number Audit
        cond_num = np.linalg.cond(AtA)
        
        if cond_num > 1e11:
            logger.warning(f"[LSHA] Matriks Il-Conditioned (cond={cond_num:.2e}). Menggunakan SVD Robust Solver.")
            # LAPACK fallback: Singular Value Decomposition
            x, _, _, _ = np.linalg.lstsq(A, h, rcond=1e-15)
        else:
            # Jalur cepat: Pencari solusi sistem linear standar
            x = np.linalg.solve(AtA, Ath)
            
        # Fase Shifting (Koreksi fase karena t_offset)
        for i in range(len(omegas)):
            shift = omegas[i] * t_offset
            c, s = np.cos(shift), np.sin(shift)
            a_orig, b_orig = x[1 + 2*i], x[2 + 2*i]
            x[1 + 2*i] = a_orig * c + b_orig * s
            x[2 + 2*i] = -a_orig * s + b_orig * c
            
        return x

    except Exception as e:
        logger.error(f"[MATH-ACCEL] Gagal memproses LSHA: {str(e)}\n{traceback.format_exc()}")
        # Ultimate fallback tanpa normal equation (Direct SVD)
        A_raw = build_design_matrix(t_array, omegas)
        x_final, _, _, _ = np.linalg.lstsq(A_raw, h, rcond=None)
        return x_final
