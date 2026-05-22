## 2026-05-22 - GeoDataFrame Iteration Overhead
**Learning:** Using `iterrows()` on a GeoDataFrame when only the geometry column is required incurs a massive overhead (~93% measured) due to row-by-row Series object instantiation.
**Action:** Always iterate directly over `gdf.geometry` when the other attributes are not needed to prevent significant performance penalties.
