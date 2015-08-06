from setuptools import setup
import sys

setup(
    name="datadog",
    version="0.8.0",
    install_requires=["argparse", "requests", "simplejson"],
    tests_require=["tox", "nose", "mock", "six", "pillow"],
    packages=[
        'datadog',
        'datadog.api',
        'datadog.dogstatsd',
        'datadog.threadstats',
        'datadog.util',
        'datadog.dogshell'
    ],
    author="Datadog, Inc.",
    author_email="dev@datadoghq.com",
    description="The Datadog Python library",
    license="BSD",
    keywords="datadog data",
    url="http://www.datadoghq.com",
    entry_points={
        'console_scripts': [
            'dog = datadog.dogshell:main',
            'dogwrap = datadog.dogshell.wrap:main',
        ],
    },
    test_suite="nose.collector",
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: PyPy"
    ]
)
