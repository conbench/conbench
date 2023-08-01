Conbench analyzed the 3 benchmark runs on commit `abc`.

There were 2 benchmark results indicating a performance regression:

- Some Run Reason Run on `some-machine-name` at [2021-02-04 17:22:05.225583](http://localhost/compare/runs/some_baseline...some_contender/)
  - [`file-read` (Python) with snappy, nyctaxi_sample, parquet, arrow](http://localhost/compare/benchmarks/some-benchmark-uuid-1...some-benchmark-uuid-3)
  - [`file-read` (Python) with snappy, nyctaxi_sample, parquet, arrow](http://localhost/compare/benchmarks/some-benchmark-uuid-1...some-benchmark-uuid-3)

The [full Conbench report](https://github.com/github/hello-world/runs/4) has more details.

This message was generated from pytest.
