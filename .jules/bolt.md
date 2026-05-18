## 2025-02-20 - [Performance] Iterating over GeoDataFrame geometries

**Learning:** When iterating over a GeoDataFrame and only the geometry column is required, avoid using `iterrows()`. Directly iterating over `gdf.geometry` provides a significant performance boost (measured at ~93% overhead reduction) by avoiding row-by-row Series object instantiation.

**Action:** Always prefer direct iteration over `gdf.geometry` for spatial iterations over `iterrows()`.
