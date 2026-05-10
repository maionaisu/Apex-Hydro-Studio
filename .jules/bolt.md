
## 2024-05-18 - Avoid cKDTree for single-point nearest neighbor queries
**Learning:** Building a `scipy.spatial.cKDTree` is an $O(N \log N)$ operation. For a single-point nearest-neighbor query, this object creation overhead makes it significantly slower than directly calculating the squared Euclidean distance ($O(N)$) and finding the minimum using `np.argmin`.
**Action:** Use `sq_dist = (ux - target_x)**2 + (uy - target_y)**2`, followed by `min_idx = np.argmin(sq_dist)` and applying `np.sqrt` only to the minimum value when searching for a single point. Reserve `cKDTree` for scenarios requiring multiple queries or when the tree can be reused.
