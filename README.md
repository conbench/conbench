<p align="right">
<a href="https://github.com/ursacomputing/conbench/blob/main/.github/workflows/actions.yml"><img alt="Build Status" src="https://github.com/ursacomputing/conbench/actions/workflows/actions.yml/badge.svg?branch=main"></a>
<a href="https://coveralls.io/github/ursacomputing/conbench?branch=main"><img src="https://coveralls.io/repos/github/ursacomputing/conbench/badge.svg?branch=main&kill_cache=06b9891a46827df564072ae831b13897599f7f3d" alt="Coverage Status" /></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

# Conbench


<img src="https://github.com/ursacomputing/conbench/blob/main/conbench.png" alt="Language-independent Continuous Benchmarking (CB) Framework">


Conbench allows you to write benchmarks in any language, publish the
results as JSON via an API, and persist them for comparison while
iterating on performance improvements or to guard against regressions.

Conbench includes a runner which can be used as a stand-alone library
for traditional benchmark authoring. The runner will time a unit of
work, collect machine information that may be relevant for hardware
specific optimizations, and return JSON formatted results.

You can optionally host a Conbench server (API & dashboard) to share
benchmark results more widely, explore the changes over time, and
compare results across varying benchmark machines, languages, and cases.

There is also a Conbench command line interface, useful for Continuous
Benchmarking (CB) orchestration alongside your development pipeline.


<p align="center">
    <img src="https://arrow.apache.org/img/arrow.png" alt="Apache Arrow" height="100">
</p>


The [Apache Arrow](https://arrow.apache.org/) project is using Conbench
for Continuous Benchmarking. They have both native Python Conbench
benchmarks, and Conbench benchmarks written in Python that know how to
execute their external C++ and R benchmarks and record those results
too. Those benchmarks can be found in the
[ursacomputing/benchmarks](https://github.com/ursacomputing/benchmarks)
repository, and the results are hosted on the
[Arrow Conbench Server](https://conbench.ursa.dev/).


<hr>


## Contributing


### Create workspace
    $ cd
    $ mkdir -p envs
    $ mkdir -p workspace


### Create a virualenv
    $ cd ~/envs
    $ python3 -m venv conbench
    $ source conbench/bin/activate


### Clone the app
    (conbench) $ cd ~/workspace/
    (conbench) $ git clone https://github.com/ursacomputing/conbench.git


### Install the dependencies
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ pip install -r requirements-test.txt
    (conbench) $ pip install -r requirements-build.txt
    (conbench) $ pip install -r requirements-cli.txt
    (conbench) $ python setup.py develop


### Create the databases

    $ psql
    # CREATE DATABASE conbench_test;
    # CREATE DATABASE conbench_prod;


### Launch the app
    (conbench) $ flask run
     * Serving Flask app "api.py" (lazy loading)
     * Environment: development
     * Debug mode: on
     * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)


### Test the app
    $ curl http://127.0.0.1:5000/api/ping/
    {
      "date": "Fri, 23 Oct 2020 03:09:58 UTC"
    }


### View the API docs

    http://localhost:5000/api/docs/


### Running tests
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ pytest -vv conbench/tests/


### Formatting code (before committing)
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ git status
        modified: foo.py
    (conbench) $ black foo.py
        reformatted foo.py
    (conbench) $ git add foo.py


### Generating a coverage report
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ coverage run --source conbench -m pytest conbench/tests/
    (conbench) $ coverage report -m
