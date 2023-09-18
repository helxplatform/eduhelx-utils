from setuptools import setup, find_packages

setup(
    name="eduhelx-utils",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "httpx>=0,<1",
        "PyJWT>=2.8.0,<2.9.0"
    ],
)