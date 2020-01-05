from setuptools import setup

from io import open


def get_readme_md_contents():
    """read the contents of your README file"""
    with open("README.md", encoding='utf-8') as f:
        long_description = f.read()
        return long_description


install_reqs = ["decorator>=4.4.0", "requests>=2.22.0"]

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
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python',
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
