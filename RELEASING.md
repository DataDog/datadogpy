# Releasing

This document summarizes the process of doing a new release of this project.
Release can only be performed by Datadog maintainers of this repository.

## Schedule
This project does not have a strict release schedule. However, we would make a release at least every 2 months.
  - No release will be done if no changes got merged to the `master` branch during the above mentioned window.
  - Releases may be done more frequently than the above mentioned window.

## Make Sure Everything Works

* Check and upgrade dependencies where it applies and makes sense. [Example](https://github.com/DataDog/datadogpy/commit/f81efe8cbf6e5bc5cb4ab46da750248161d0c548#diff-2eeaed663bd0d25b7e608891384b7298)
  - Create a distinct pull request and test your changes since it may introduce regressions.
  - While using the latest versions of dependencies is advised, it may not always be possible due to potential compatibility issues.
  - Upgraded dependencies should be thoroughly considered and tested to ensure they are safe!
* Make sure tests are passing.
  - Locally and in the continuous integration system.
* Make sure documentation is up-to-date and building correctly.
* Build the package locally (e.g. `python3 setup.py sdist`), install it into a fresh virtualenv and try playing around with it for a bit.
* [Update changelog](#update-changelog)
  - Create a distinct pull request.

## Update Changelog

### Prerequisite

- Install [datadog_checks_dev](https://datadog-checks-base.readthedocs.io/en/latest/datadog_checks_dev.cli.html#installation) using Python 3

### Commands

- See changes ready for release by running `ddev release show changes .` at the root of this project. Add any missing labels to PRs if needed.
- Run `ddev release changelog . <NEW_VERSION>` to update the `CHANGELOG.md` file at the root of this repository
- Commit the changes to the repository in a release branch and get it approved/merged.

## Release Process

Our team will trigger the release pipeline.

### Prerequisite

#### Setup PyPI

In order to create a new release you will need to setup PyPI Tooling as well as `datadog_checks_dev` mentioned above.
See our internal documentation for more details.

### Release

1. Tag the release on GitHub. [Example](https://github.com/DataDog/datadogpy/releases/tag/v0.10.0)
2. Checkout the [tag release](#commands).
3. Run `ddev release build .` and `ddev release upload --sdist`.
  - Make sure that both an `sdist` and a [universal wheel](https://packaging.python.org/guides/distributing-packages-using-setuptools/#universal-wheels) have been uploaded to [PyPI](https://pypi.python.org/pypi/datadog/).
4. Set CHANGELOG release date. [Example](https://github.com/DataDog/datadogpy/commit/e89b19c0bc1e5ea2ec026e14b11d05b980062ffb)
