## 2024-05-04 - Fast GeoDataFrame Iteration
**Learning:** `iterrows()` on GeoDataFrames introduces significant overhead (~93%) due to row-by-row Series object instantiation.
**Action:** When only geometry data is needed, iterate directly over the `.geometry` attribute instead of using `iterrows()`.
