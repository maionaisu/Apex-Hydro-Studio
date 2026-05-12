## 2024-05-12 - GeoDataFrame Iteration Optimization
**Learning:** When iterating over a `GeoDataFrame` and only the geometry is needed, using `.iterrows()` is highly inefficient due to the overhead of creating `Series` objects for each row. Directly iterating over the `.geometry` attribute avoids this overhead and provides significant performance gains.
**Action:** Always prefer direct iteration over `.geometry` when row attributes are not needed. Avoid `.iterrows()` whenever possible.
