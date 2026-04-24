## 2024-06-25 - Dask Sequential `.values` I/O Bottleneck
**Learning:** In `xarray`, reading a scalar output variable using `.values` implicitly triggers `.compute()`. In an out-of-core workflow (e.g. `ERA5Extractor`), executing multiple sequential `.values` calls triggers multiple full passes over the NetCDF data chunks, dramatically increasing I/O time.
**Action:** Always batch aggregate operations on Dask-backed datasets using `dask.compute(*ops)` to build a single computation graph, allowing a single data pass and substantially reducing disk reads.
