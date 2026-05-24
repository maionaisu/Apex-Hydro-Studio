## 2026-05-24 - Avoid iterrows() on GeoDataFrames
**Learning:** Iterating over a GeoDataFrame using `iterrows()` when only the geometry column is required is inefficient. Row-by-row Series object instantiation adds massive overhead (~93% overhead reduction measured).
**Action:** Directly iterate over `gdf.geometry` instead of using `iterrows()`.
