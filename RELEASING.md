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
* Build the package locally (e.g. `python3 setup.py sdist`), install it into a fresh virtualenv and test the changes that have been made since the last release.

## Release Process
Our team will trigger the release pipeline.

### Prerequisite 
- Install [datadog_checks_dev](https://datadog-checks-base.readthedocs.io/en/latest/datadog_checks_dev.cli.html#installation) using Python 3.
- Setup PyPI, see the internal documentation for more details

### Update Changelog and version

1. See changes ready for release by running `ddev release show changes .` at the root of this project. Add any missing labels to PRs if needed.
1. Run `ddev release changelog . <NEW_VERSION>` to update the `CHANGELOG.md` file at the root of this repository
1. Commit the changes to the repository in a release branch and open a PR. Do not merge yet.
1. Bump the version in [`datadog/version.py`](datadog/version.py) and push it to your changelog PR. [Example](https://github.com/DataDog/datadogpy/pull/495/files#diff-2eeaed663bd0d25b7e608891384b7298)
1. Merge the PR to master.

### Release
1. Create the release on GitHub. [Example](https://github.com/DataDog/datadogpy/releases/tag/0.40.0)
1. A github action will kick off that builds and publishes this tag to PyPI. Confirm the [release is available](https://pypi.org/project/datadog/#history)