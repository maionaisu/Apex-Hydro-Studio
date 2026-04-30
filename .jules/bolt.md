## 2024-04-30 - [GeoDataFrame Iteration Bottleneck]
**Learning:** Iterating over a GeoDataFrame using `iterrows()` is incredibly slow because it instantiates a pandas Series object for every single row. If only the spatial data is needed, this overhead is completely unnecessary.
**Action:** When working with GeoDataFrames, if only the spatial information is required, always iterate directly over the geometry column (e.g., `for geom in gdf.geometry:`) to bypass the row-by-row Series object instantiation, providing a huge performance boost.
