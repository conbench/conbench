import pathlib

import setuptools

repo_root = pathlib.Path(__file__).parent

with open(repo_root / "README.md", "r") as readme:
    long_description = readme.read()

__version__ = ""
with open(repo_root / "benchadapt" / "_version.py", "r") as f:
    exec(f.read())  # only overwrites the __version__ variable

install_requires = [
    line.strip()
    for line in pathlib.Path(__file__)
    .parent.joinpath("requirements.txt")
    .read_text()
    .splitlines()
]

setuptools.setup(
    name="benchadapt",
    version=__version__,
    description="Adapters for Running and Tracking Benchmarks",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: Apache Software License",
    ],
    python_requires=">=3.8",
    maintainer="Voltron Data",
    maintainer_email="conbench@voltrondata.com",
    url="https://github.com/conbench/conbench/tree/main/benchadapt",
    install_requires=install_requires,
)
