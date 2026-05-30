## 2026-05-30 - [Optimize Single-Point Search]
**Learning:** For single-point nearest neighbor queries on large unstructured meshes (e.g., >1GB), avoid building a `scipy.spatial.cKDTree`. Its O(N log N) construction overhead makes it significantly slower than calculating the squared distance directly.
**Action:** Compute the squared distance `(dx**2 + dy**2)` directly and apply `np.argmin` (O(N)), avoiding computationally expensive O(N) `np.hypot` calculations. Apply `np.sqrt` only to the final minimum value.
