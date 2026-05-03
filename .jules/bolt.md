## 2024-06-25 - [Single-Point Nearest Neighbor Query Optimization]
**Learning:** For a single nearest-neighbor query on unstructured mesh data, building a `scipy.spatial.cKDTree` incurs a heavy O(N log N) initialization penalty that dominates the execution time.
**Action:** Always compute direct squared Euclidean distances (using `(dx**2 + dy**2)`) followed by `np.argmin()` for O(N) single-query lookups. Only apply `np.sqrt()` on the resulting minimum distance to avoid costly mathematical operations over entire arrays.
