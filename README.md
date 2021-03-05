<p align="right">
<a href="https://travis-ci.com/ursacomputing/conbench"><img alt="Build Status" src="https://travis-ci.com/ursacomputing/conbench.svg?branch=main"></a>
<a href="https://coveralls.io/github/ursacomputing/conbench?branch=main"><img src="https://coveralls.io/repos/github/ursacomputing/conbench/badge.svg?branch=main&kill_cache=1" alt="Coverage Status" /></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

# Conbench

<b>Language-independent Continuous Benchmarking (CB) Framework</b>
<br/>
<br/>


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
