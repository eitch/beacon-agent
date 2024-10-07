from setuptools import setup, find_packages

setup(
    name="beacon_agent",
    version="0.1.0",
    author="Robert von Burg",
    author_email="eitch@eitchnet.ch",
    description="This is the python agent for UptimeBeacon",
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.6',
    install_requires=[
        "requests",
        "urllib3"
    ],
    extras_require={
        "dev": ["pypa"],
    },
    entry_points={
        "console_scripts": [
            "agent=beacon_agent.agent:main",
        ],
    },
)