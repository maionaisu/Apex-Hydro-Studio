## 2024-05-24 - KDTree Tree Construction Overhead
**Learning:** For single-point nearest neighbor queries on large arrays, building a `scipy.spatial.cKDTree` (O(N log N)) is significantly slower than calculating the squared distance directly and using `np.argmin` (O(N)), despite the O(log N) query time of the tree.
**Action:** Always prefer calculating squared distance `dx**2 + dy**2` and applying `np.sqrt` only to the minimum distance when doing a one-off nearest neighbor search on large unstructured mesh nodes. Avoid `np.hypot` as it evaluates square root for all points.
