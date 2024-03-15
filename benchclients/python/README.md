# benchclients

A simple, low-dependency Python library with clients for calling the Conbench API and
potentially other APIs in the Conbench ecosystem

## Installation

The benchclients package can be installed [from PyPI](https://pypi.org/project/benchclients/)
with

``` sh
pip install benchclients
```

or direct from GitHub with

``` sh
pip install benchclients@git+https://github.com/conbench/conbench.git@main#subdirectory=benchclients/python
```

or with your preferred environment management system. Package code should rarely change,
and the number of dependencies should remain very minimal.

## Components

The package is structured such that all users should need is client classes that it
exposes. As of writing, there is only one such useful class: `benchclients.ConbenchClient`.
However, clients for other APIs can easily be created by inheriting from the
`benchclients.BaseAdapter` class, which defines core methods for making HTTP requests
(e.g. `.get()`, `.post()`, etc.) set up to handle retries and logging and so on.

### `ConbenchClient`

#### Environment variables

Configuration and credentials for `ConbenchClient` can be handled by three environment
variables set before class instantiation:

- `CONBENCH_URL`: The URL of the Conbench server. Required.
- `CONBENCH_EMAIL`: The email to use for Conbench login. Only required for GETting if the
server is private.
- `CONBENCH_PASSWORD`: The password to use for Conbench login. Only required for GETting
if the server is private.   

Alternatively, you can instantiate the client with the `url`, `email`, and `password` keyword arguments - like:
    
``` python
conbench = ConbenchClient(url="https://conbench.ursa.dev",
                          email="test@example.com",
                          password="xxxxxx"
                          )
```

#### Usage

If environment variables are set before instantiation, or the keyword arguments are used, `ConbenchClient` will handle
auth, so users can get right to making requests:

``` python
import logging
import os

from benchclients import ConbenchClient, log


os.environ["CONBENCH_URL"] = "https://conbench.ursa.dev"
log.setLevel(logging.DEBUG)

conbench = ConbenchClient()

benchmark_result_id = "4e0e569d82724667b3e929dedb730edc"
res = conbench.get(f"/benchmarks/{benchmark_result_id}")
#> DEBUG [2023-02-10 12:56:48,492] GET https://conbench.ursa.dev/api/benchmarks/4e0e569d82724667b3e929dedb730edc

res
#> {'batch_id': '746e76a30fbf4bb0bf91bde369b76f3a-1n',
#>  'change_annotations': {},
#>  'error': None,
#>  'id': '4e0e569d82724667b3e929dedb730edc',
#>  'links': {'context': 'http://conbench.ursa.dev/api/contexts/105b127c7f624a6d908d4ec65e018fea/',
#>   'info': 'http://conbench.ursa.dev/api/info/4d8cb198342f455e90cd84e2e8356f2a/',
#>   'list': 'http://conbench.ursa.dev/api/benchmarks/',
#>   'run': 'http://conbench.ursa.dev/api/runs/746e76a30fbf4bb0bf91bde369b76f3a/',
#>   'self': 'http://conbench.ursa.dev/api/benchmarks/4e0e569d82724667b3e929dedb730edc/'},
#>  'optional_benchmark_info': {},
#>  'run_id': '746e76a30fbf4bb0bf91bde369b76f3a',
#>  'stats': {'data': [0.693055, 0.69691, 0.702238],
#>   'iqr': 0.004591,
#>   'iterations': 3,
#>   'max': 0.702238,
#>   'mean': 0.697401,
#>   'median': 0.69691,
#>   'min': 0.693055,
#>   'q1': 0.694982,
#>   'q3': 0.699574,
#>   'stdev': 0.004611,
#>   'time_unit': 's',
#>   'times': [],
#>   'unit': 's',
#>   'z_improvement': False,
#>   'z_regression': True,
#>   'z_score': -14.600706547691335},
#>  'tags': {'cpu_count': None,
#>   'engine': 'arrow',
#>   'format': 'native',
#>   'id': '4193bedfc281454f87f6e045019fedfa',
#>   'language': 'R',
#>   'memory_map': False,
#>   'name': 'tpch',
#>   'query_id': 'TPCH-13',
#>   'scale_factor': 1},
#>  'timestamp': '2023-02-10T09:17:18Z',
#>  'validation': None}
```
