import pathlib

import setuptools

repo_root = pathlib.Path(__file__).parent

with open(repo_root / "README.md", "r") as readme:
    long_description = readme.read()

__version__ = ""
with open(repo_root / "conbench" / "_version.py", "r") as f:
    exec(f.read())  # only overwrites the __version__ variable


def parse_requirements(path: str):
    return [
        line.strip()
        for line in pathlib.Path(__file__)
        .parent.joinpath(path)
        .read_text()
        .splitlines()
    ]


requirements_cli = parse_requirements(path="requirements-cli.txt")
requirements_webapp = parse_requirements(path="requirements-webapp.txt")
requirements_dev = parse_requirements(path="requirements-dev.txt")

setuptools.setup(
    name="conbench",
    version=__version__,
    description="Continuous Benchmarking (CB) Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": [
            "conbench=conbench.cli:conbench",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.8",
    maintainer="Apache Arrow Developers",
    maintainer_email="dev@arrow.apache.org",
    url="https://github.com/conbench/conbench",
    install_requires=requirements_cli,
    extras_require={
        "server": requirements_webapp,
        "dev": requirements_webapp + requirements_dev,
    },
)
