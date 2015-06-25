from setuptools import setup
import sys

install_reqs = [
    "decorator>=3.3.2",
    "requests>=2.6.0",
]
if sys.version_info[0] == 2:
    # simplejson is not python3 compatible
    install_reqs.append("simplejson>=2.0.9")

if [sys.version_info[0], sys.version_info[1]] < [2, 7]:
    install_reqs.append("argparse>=1.2")

setup(
    name="datadog",
    version="0.7.0",
    install_requires=install_reqs,
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
