## 2024-05-18 - GeoDataFrame Iteration Optimization
**Learning:** Iterating over a GeoDataFrame using `iterrows()` has extreme overhead (e.g., ~600ms vs ~10ms for 10k items) because it instantiates a pandas Series for every single row. When only the geometry column is required, this is a major anti-pattern.
**Action:** Always iterate directly over the `gdf.geometry` column (`for geom in gdf.geometry:`) when geometry is the only data needed from the GeoDataFrame, achieving ~93% overhead reduction.
