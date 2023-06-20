Conbench analyzed the 2 benchmark runs on commit `abc`.

## Benchmarks with errors

These are errors that were caught while running the benchmarks. You can click each link to go to the Conbench entry for that benchmark, which might have more information about what the error was.

- Some Run Reason Run on `some-machine-name` at [2021-02-04 17:22:05.225583](http://localhost/runs/some_contender)
  - [file-write](http://localhost/benchmark-results/some-benchmark-uuid-2)
  - [file-write](http://localhost/benchmark-results/some-benchmark-uuid-2)

## Benchmarks with performance regressions

There weren't enough matching historic runs in Conbench to make a call on whether there were regressions or not.

To use the lookback z-score method of determining regressions, there need to be at least two historic runs on the default branch which, when compared to one of the runs on the contender commit, are on the same hardware, and have at least one of the same benchmark case and context pairs.

This message was generated from pytest.
