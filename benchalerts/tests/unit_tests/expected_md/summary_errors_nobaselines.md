## Benchmarks with errors

These are errors that were caught while running the benchmarks. You can click each link to go to the Conbench entry for that benchmark, which might have more information about what the error was.

- Some Run Reason Run at [2021-02-04 17:22:05.225583](http://localhost/runs/some_contender)
  - [file-write](http://localhost/benchmarks/some-benchmark-uuid-2)
  - [file-write](http://localhost/benchmarks/some-benchmark-uuid-2)

## Benchmarks with performance regressions

There weren't enough matching historic runs in Conbench to make a call on whether there were regressions or not.

To use the lookback z-score method of determining regressions, there needs to be at least one historic run on the default branch which, when compared to one of the runs on the contender commit, is in the same repository, on the same hardware, and has at least one of the same benchmark case and context pairs.
