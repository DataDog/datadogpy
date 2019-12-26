# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from setuptools import setup

from io import open
import sys


def get_readme_md_contents():
    """read the contents of your README file"""
    with open("README.md", encoding='utf-8') as f:
        long_description = f.read()
        return long_description


install_reqs = ["decorator>=3.3.2", "requests>=2.6.0"]

if [sys.version_info[0], sys.version_info[1]] < [2, 7]:
    install_reqs.append("argparse>=1.2")

setup(
    name="datadog",
    version="0.33.0",
    install_requires=install_reqs,
    tests_require=["pytest", "mock", "freezegun"],
    packages=["datadog", "datadog.api", "datadog.dogstatsd", "datadog.threadstats", "datadog.util", "datadog.dogshell"],
    author="Datadog, Inc.",
    long_description=get_readme_md_contents(),
    long_description_content_type="text/markdown",
    author_email="dev@datadoghq.com",
    description="The Datadog Python library",
    license="BSD",
    keywords="datadog",
    url="https://www.datadoghq.com",
    project_urls={
        "Bug Tracker": "https://github.com/DataDog/datadogpy/issues",
        "Documentation": "https://datadogpy.readthedocs.io/en/latest/",
        "Source Code": "https://github.com/DataDog/datadogpy",
    },
    entry_points={"console_scripts": ["dog = datadog.dogshell:main", "dogwrap = datadog.dogshell.wrap:main"]},
    test_suite="tests",
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
