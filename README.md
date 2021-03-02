# Conbench: Language-independent Continuous Benchmarking (CB) Framework

### Create workspace
    $ cd
    $ mkdir envs
    $ mkdir workspace


### Create a virualenv
    $ cd ~/envs
    $ python3 -m venv conbench
    $ source conbench/bin/activate


### Clone the app
    (conbench) $ cd ~/workspace/
    (conbench) $ git clone https://github.com/ursa-labs/conbench.git


### Install the dependencies
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ pip install -r requirements-test.txt
    (conbench) $ pip install -r requirements-build.txt
    (conbench) $ pip install -r requirements-cli.txt
    (conbench) $ python setup.py develop


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
        modified:   conbench/runner.py
    (conbench) $ black conbench/runner.py
        reformatted conbench/runner.py
    (conbench) $ git add conbench/runner.py


### Generating a coverage report
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ coverage run --source conbench -m pytest conbench/tests/
    (conbench) $ coverage report -m
