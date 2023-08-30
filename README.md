<p align="right">
<a href="https://github.com/conbench/conbench/blob/main/.github/workflows/actions.yml"><img alt="Build Status" src="https://github.com/conbench/conbench/actions/workflows/actions.yml/badge.svg?branch=main"></a>
</p>

# Conbench

Check out the docs at https://conbench.github.io/conbench.

<img src="https://raw.githubusercontent.com/conbench/conbench/main/conbench.png" alt="Language-independent Continuous Benchmarking (CB) Framework">


Conbench allows you to write benchmarks in any language, publish the
results as JSON via an API, and persist them for comparison while
iterating on performance improvements or to guard against regressions.

Conbench includes a runner which can be used as a stand-alone library
for traditional macro benchmark authoring. The runner will time a unit of
work (or measure throughput), collect machine information that may be relevant
for hardware specific optimizations, and return JSON formatted results.

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
execute their external C++/R/Java/JavaScript benchmarks and record those results
too. Those benchmarks can be found in the
[ursacomputing/benchmarks](https://github.com/ursacomputing/benchmarks)
repository, and the results are hosted on the
[Arrow Conbench Server](https://conbench.ursa.dev/).


- May 2021: https://ursalabs.org/blog/announcing-conbench/


<br>


## Installation

Most packages in this repo can be installed from PyPI. Each package uses
[CalVer](https://calver.org/) for versioning. No stability is guaranteed between PyPI
versions, so consider pinning packages to a specific version in your code.

```bash
pip install benchadapt
pip install benchalerts
pip install benchclients
pip install benchconnect
pip install benchrun
# deprecated; install the webapp or conbenchlegacy from git instead
# pip install conbench
```

We typically publish to PyPI often, when new features or bugfixes are needed by users,
but not on every merge to `main`. To install the latest development version, install
from git like so:

```bash
pip install 'benchadapt@git+https://github.com/conbench/conbench.git@main#subdirectory=benchadapt/python'
pip install 'benchalerts@git+https://github.com/conbench/conbench.git@main#subdirectory=benchalerts'
pip install 'benchclients@git+https://github.com/conbench/conbench.git@main#subdirectory=benchclients/python'
pip install 'benchconnect@git+https://github.com/conbench/conbench.git@main#subdirectory=benchconnect'
pip install 'benchrun@git+https://github.com/conbench/conbench.git@main#subdirectory=benchrun/python'
pip install 'conbenchlegacy@git+https://github.com/conbench/conbench.git@main#subdirectory=legacy'
pip install 'conbench@git+https://github.com/conbench/conbench.git@main'    # webapp
```


## Developer environment

### Dependencies

- [`make`](https://www.gnu.org/software/make/), [`docker compose`](https://docs.docker.com/compose/install/): common developer tasks depend on these tools. They need to be set up on your system.
- `GITHUB_API_TOKEN` environment variable: set up a GitHub API token using [GitHub's instructions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token). It's recommended to only give the token read-only permissions to public repositories (which is the default for fine-grained personal access tokens). Run `export GITHUB_API_TOKEN="{token}"` in your current shell.

### Makefile targets

The following Makefile targets implement common developer tasks. They assume to be run in the root folder of the repository.

* `make run-app`: This command lets you experiment with Conbench locally.
It runs the stack in a containerized fashion.
It rebuilds container images from the current checkout, spawns
multiple containers (including one for the database), and then exposes Conbench's
HTTP server on the host at http://127.0.0.1:5000.
The command will stay in the foreground of your terminal, showing log output of all containers.
Once you see access log lines like `GET /api/ping/ HTTP/1.1" 200` you can point your browser to http://127.0.0.1:5000.
You can use `Ctrl+C` to terminate the containerized stack (this only stops containers, and the next invocation of `make run-app` will use previous database state -- invoke `make teardown-app` to stop and remove containers).
If you wish to clear all database tables during local development you can hit http://127.0.0.1:5000/api/wipe-db with the browser or with e.g. curl.

* `make run-app-dev`: Similar to `make run-app`, but also mounts the repository's root directory into the container.
Code changes are (should be) detected automatically and result in automatic code reload.

* `make tests`: The nobrainer command to run the test suite just like CI does.
For more fine-grained control see further below.

* `make lint`: Performs invasive code linting in your local checkout.
May modify files. Analogue to what CI requires.
It requires for some commands to be available in your current shell.
Dependencies can be installed with `pip install -r requirements-dev.txt`.

* `make alembic-new-migration`: Attempts to generate a new migration Python module in `migrations/versions/`.
Requires setting the environment variable `ALEMBIC_MIGRATION_NAME` before invocation.
Example: `export ALEMBIC_MIGRATION_NAME='repo_url_lenth'`.
After the file was created you may want to change its permissions and re-format it with `black`.

* `make conbench-on-minikube`: requires [minikube](https://minikube.sigs.k8s.io/docs/start/).
Deploys the Conbench API server to a local minikube-powered Kubernetes cluster.
This also deploys a kube-prometheus-based observability stack.
Use this target for local development in this area.

* `make docs-build`: Builds HTML docs locally so you may check that they render
  correctly with no linting problems. Dependencies can be installed with
  `pip install -r requirements-dev.txt`. Also, if you're working on the docstrings of
  any of this repo's python packages, ensure the package is installed locally before
  using this command.

  In CI, we use `make build-docs SPHINXOPTS='-W --keep-going'` to fail the build if
  there are Sphinx warnings. When using this command locally, you can just do
  `make build-docs`, but keep an eye on the warnings.

### View API documentation

Point your browser to http://127.0.0.1:5000/api/docs/.

### Python environment on the host

CI and common developer commands use containerized workflows where dependencies are defined and easy to reason about via `Dockerfile`s.

Note that the CPython version that Conbench is tested with in CI and that it is recommended to be deployed with is currently the latest 3.11.x release, as also defined in `Dockerfile` at the root of this repository.

Some developer tasks may involve running Conbench tooling straight on the host.
Here is how to install the Python dependencies for the Conbench web application:

```bash
pip install -r requirements-webapp.txt
```

Dependencies for running code analysis and tests straight on the host can be installed with

```bash
pip install -r requirements-dev.txt
```

### Fine-grained test invocation

If `make test` is too coarse-grained, then this is how to take control of the containerized `pytest` test runner:

```bash
docker compose down && docker compose build app && \
    docker compose run app \
    pytest -vv conbench/tests
```

This command attempts to stop and remove previously spawned test runner containers, and it rebuilds the `app` container image prior to running tests to pick up code changes in the local checkout.

Useful command line arguments for local development (can be combined as desired):

* `... pytest -k test_login`: run only string-matching tests
* `... pytest -x`: exit upon first error
* `... pytest -s`: do not swallow log output during run
* `... run -e CONBENCH_LOG_LEVEL_STDERR=DEBUG app ...`

### Legacy commands

The following commands are not guaranteed to work as documented, but provide valuable inspiration:

#### To autogenerate a migration

    (conbench) $ brew services start postgres
    (conbench) $ dropdb conbench_prod
    (conbench) $ createdb conbench_prod
    (conbench) $ git checkout main && git pull
    (conbench) $ alembic upgrade head
    (conbench) $ git checkout your-branch
    (conbench) $ alembic revision --autogenerate -m "new"


#### To populate local conbench with sample runs and benchmarks

1. Start conbench app in Terminal window 1:

        (conbench) $ dropdb conbench_prod && createdb conbench_prod && alembic upgrade head && flask run

2. Run `conbench.tests.populate_local_conbench` in Terminal window 2 while conbench app is running:

        (conbench) $ python -m conbench.tests.populate_local_conbench


### To upload new version of packages to PyPI

Kick off a new run of the "Build and upload a package to PyPI" workflow on the [Actions
page](https://github.com/conbench/conbench/actions).

### To add new documentation pages

To add a new page to our GitHub Pages-hosted documentation:

1. Add a Markdown file to `docs/pages/`.
2. In the toctree in the `docs/index.rst` file, add `pages/your_new_page`, where
   `your_new_page` is your new filename without the `.md` file suffix.

To test that your new pages pass our documentation linter, run the `make docs-build`
command, as described above.

## Configuring the web application

The conbench web application can be configured with various environment variables as
defined in
[config.py](https://github.com/conbench/conbench/blob/main/conbench/config.py).
Instructions are in that file.

## Creating accounts

By default, conbench has open read access, so a user account is not required to
view results or read from the API. An account is required only if the conbench
instance is private or to write data to conbench.

If you do need an account, follow the login screen's "Sign Up" link, and use the
registration key specified in the server configuration above. If you are a user
of conbench, you may need to talk to your user administrator to get the
registration key. SSO can be configured to avoid requiring the registration key.

If you have an account and need to create an additional account (say for a machine
user of the API) either repeat the process if you have the registration key, or if
you don't have the registration key (say if your account uses SSO), when logged in,
go to the gear menu / Users and use the "Add User" button to create a new account
without the registration key.
