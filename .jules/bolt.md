## 2024-05-24 - GeoDataFrame Iteration Overhead
**Learning:** Iterating over GeoDataFrames using `iterrows()` when only the geometry is needed introduces a massive overhead due to row-by-row Pandas Series object instantiation.
**Action:** Always iterate directly over `gdf.geometry` (e.g., `for geom in gdf.geometry:`) when geometry is the only required property, achieving ~93% overhead reduction.
