## 2024-06-25 - Avoid `iterrows` on GeoDataFrames
**Learning:** When iterating over a GeoDataFrame and only the geometry column is required, avoid using `iterrows()`. Directly iterating over `gdf.geometry` provides a significant performance boost (measured at ~93% overhead reduction) by avoiding row-by-row Series object instantiation.
**Action:** Always extract the `.geometry` attribute directly (e.g. `for geom in gdf.geometry:`) rather than unpacking row geometries from `.iterrows()`.
