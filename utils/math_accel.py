# ==============================================================================
# APEX NEXUS TIER-0: NUMBA-ACCELERATED MATH ENGINE
# ==============================================================================
import numpy as np
from numba import njit
import logging
import traceback

logger = logging.getLogger(__name__)

@njit(nopython=True, cache=True)
def build_design_matrix(t_sec: np.ndarray, omegas: np.ndarray) -> np.ndarray:
    """
    O(N*K) Numba-accelerated construction of the LSHA design matrix.
    t_sec: 1D array of timestamps in seconds.
    omegas: 1D array of angular frequencies of tidal constituents (rad/s).
    
    Returns:
        A: Design matrix of shape (N, 1 + 2*K) where columns are:
           [1, cos(w1*t), sin(w1*t), cos(w2*t), sin(w2*t), ...]
    """
    N = len(t_sec)
    K = len(omegas)
    # Pre-allocate memory for O(1) space footprint inside the loop
    A = np.ones((N, 1 + 2 * K), dtype=np.float64)
    
    for i in range(K):
        # Vectorized internal computation for speed
        phase = omegas[i] * t_sec
        A[:, 1 + 2 * i] = np.cos(phase)
        A[:, 2 + 2 * i] = np.sin(phase)
        
    return A

@njit(nopython=True, cache=True)
def fast_normal_equations(A: np.ndarray, h: np.ndarray):
    """
    O(N*K^2) Numba-accelerated formation of Normal Equations.
    Matrix multiplication is heavily optimized by BLAS under the hood.
    """
    AtA = A.T @ A
    Ath = A.T @ h
    return AtA, Ath

def solve_lsha(t_sec: np.ndarray, h: np.ndarray, omegas: np.ndarray) -> np.ndarray:
    """
    Robust Least Squares Harmonic Analysis solver.
    Implements BUG-05 FIX: Condition number guard with SVD fallback.
    
    Args:
        t_sec: Time in seconds relative to epoch.
        h: Water level observations.
        omegas: Angular frequencies of targeted tidal constituents.
        
    Returns:
        x: Solution vector containing [Z0, A1, B1, A2, B2, ...]
    """
    try:
        # 1. STRICT DATA VALIDATION (Pre-mitigates Numba SegFaults)
        if len(t_sec) != len(h):
            raise ValueError(f"Shape mismatch: t_sec ({len(t_sec)}) != h ({len(h)})")
        if len(t_sec) == 0:
            raise ValueError("Input observation arrays cannot be empty.")

        # 2. Build design matrix (Accelerated)
        A = build_design_matrix(t_sec, omegas)
        
        # 3. Form Normal Equations
        AtA, Ath = fast_normal_equations(A, h)
        
        # 4. BUG-05 FIX: Guard against ill-conditioned matrices
        # (e.g., severe data gaps, aliasing, or co-linear frequencies)
        cond_num = np.linalg.cond(AtA)
        if cond_num > 1e12:
            logger.warning(f"[LSHA] Ill-conditioned matrix detected (cond={cond_num:.2e} > 1e12). "
                           f"Falling back to SVD (np.linalg.lstsq).")
            # Fallback to robust Singular Value Decomposition
            x, residuals, rank, s = np.linalg.lstsq(A, h, rcond=None)
            return x
            
        # 5. Fast path: Cholesky/LU solve for well-conditioned matrices
        x = np.linalg.solve(AtA, Ath)
        return x

    except np.linalg.LinAlgError as e:
        logger.error(f"[LSHA] Fatal Linear Algebra Error: {str(e)}\n{traceback.format_exc()}")
        # Ultimate fallback: Attempt direct SVD on raw design matrix bypassing AtA
        logger.info("[LSHA] Attempting direct SVD bypass...")
        A_bypass = build_design_matrix(t_sec, omegas)
        x, _, _, _ = np.linalg.lstsq(A_bypass, h, rcond=None)
        return x
        
    except Exception as e:
        logger.error(f"[LSHA] Unexpected Error during computation: {str(e)}\n{traceback.format_exc()}")
        raise
