from setuptools import setup, find_packages
from eduhelx_utils._version import __version__

setup(
    name="eduhelx-utils",
    version=__version__,
    url="https://github.com/helxplatform/eduhelx-utils.git",
    packages=find_packages(),
    install_requires=[
        "httpx>=0,<1",
        "PyJWT>=2.8.0,<2.9.0",
        "loguru==0.4.1"
    ],
    python_requires='>=3.7'
)