## 2024-05-24 - [GeoDataFrame Iteration Performance]
 **Learning:** [When iterating over a GeoDataFrame and only the geometry column is required, avoid using `iterrows()`. Directly iterating over `gdf.geometry` provides a significant performance boost (measured at ~93% overhead reduction) by avoiding row-by-row Series object instantiation.]
 **Action:** [Always use `for geom in gdf.geometry` instead of `for i, row in gdf.iterrows(): geom = row.geometry` when looping over shapefiles or GeoDataFrames if only geometry is needed.]
