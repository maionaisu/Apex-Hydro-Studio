## 2024-05-17 - [GeoDataFrame Iteration Optimization]
**Learning:** Iterating over `GeoDataFrame.geometry` directly is significantly faster than using `iterrows()` when only the geometry column is required.
**Action:** Always iterate over `gdf.geometry` instead of `gdf.iterrows()` when only the geometry column is needed.
