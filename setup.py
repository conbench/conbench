import setuptools

with open("README.md", "r") as readme:
    long_description = readme.read()


setuptools.setup(
    name="conbench",
    version="1.12.0",
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
    url="https://github.com/ursa-labs/conbench",
    install_requires=[
        "click",
        "psutil",
        "py-cpuinfo",
        "PyYAML",
        "requests",
    ],
)
