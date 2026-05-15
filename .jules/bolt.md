## 2026-05-15 - [Iterrows Performance in GeoDataFrames]
**Learning:** Iterating over a GeoDataFrame with iterrows() when only the geometry column is required adds huge overhead due to row-by-row Series object instantiation.
**Action:** Use direct iteration over gdf.geometry instead.
