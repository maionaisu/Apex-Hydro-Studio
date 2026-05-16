## 2024-05-24 - [cKDTree Optimization]
**Learning:** For single-point nearest neighbor queries on large unstructured meshes, avoid building a `scipy.spatial.cKDTree`. Its O(N log N) construction overhead makes it significantly slower than calculating the squared distance directly and using `np.argmin` (O(N)).
**Action:** Replace `cKDTree` with vectorized squared distance and `np.argmin` for single point lookups in `engines/postproc_engine.py`.
