## 2025-03-03 - [Replace iterrows with .geometry for GeoDataFrames]
**Learning:** Iterating over GeoDataFrames using `iterrows()` instantiates a Pandas Series for every row, leading to severe performance overhead (~93% overhead). When only the geometry is needed, directly iterating over `gdf.geometry` is significantly faster.
**Action:** Always avoid `iterrows()` in GeoPandas if only the geometry column is accessed.
