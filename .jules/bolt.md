## 2024-05-15 - [Avoid cKDTree for Single-Point Queries]
**Learning:** While `scipy.spatial.cKDTree` offers O(log N) query times, building the tree itself is O(N log N). For single-point nearest neighbor queries on large unstructured meshes, the tree construction overhead completely dominates the execution time.
**Action:** Use vectorized squared Euclidean distance `(dx**2 + dy**2)` followed by `np.argmin` (O(N)) for single-point lookups. Apply `np.sqrt` only to the minimum value to save computationally expensive operations.
