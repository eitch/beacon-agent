from setuptools import setup, find_packages

setup(
    name="beacon_agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        "urllib3"
    ],
)