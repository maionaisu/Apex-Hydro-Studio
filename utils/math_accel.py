import numpy as np

# Numba is optional depending on environment, we implement graceful fallback
try:
    from numba import jit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

@jit(nopython=True)
def _solve_lstsq_numba(A, z):
    """
    Solves linear least squares A * x = z for LSHA using Numba.
    This replaces numpy.linalg.lstsq inside heavy loops to bypass Python GIL
    and compile down to LLVM machine code.
    """
    # A is (N, M), z is (N,)
    # Solving (A^T A) x = A^T z -> x = inv(A^T A) A^T z
    AtA = A.T @ A
    Atz = A.T @ z
    x = np.linalg.solve(AtA, Atz)
    return x

def calculate_lsha(t_hours, z, freqs):
    """
    Constructs the design matrix given frequencies and solves the Least Squares 
    Harmonic Analysis for given time series and elevations.
    """
    N = len(t_hours)
    M = 1 + 2 * len(freqs)
    A = np.ones((N, M))
    
    # Values of frequencies
    w_values = list(freqs.values())
    
    for i, w in enumerate(w_values):
        A[:, 1 + 2*i] = np.cos(w * t_hours)
        A[:, 2 + 2*i] = np.sin(w * t_hours)
        
    res = _solve_lstsq_numba(A, z)
    return res

@jit(nopython=True)
def calculate_distances(px, py):
    """ Fast hypothetical distance along a polyline """
    N = len(px)
    dists = np.zeros(N)
    for i in range(1, N):
        dx = px[i] - px[i-1]
        dy = py[i] - py[i-1]
        dists[i] = dists[i-1] + np.sqrt(dx**2 + dy**2)
    return dists
