# Development

## Basics

We love pull requests. Here's a quick guide.

Fork, then clone the repo:

    git clone git@github.com:your-username/datadogpy.git


## Adding new API endpoints
This section outlines the process for adding a new endpoint to this API client.

Let's use the example of creating an endpoint for `Hosts`. This example endpoint accepts either a GET or DELETE request at the `/hosts` endpoint as well as a GET request at the `hosts/totals` endpoint.

**NOTE:** This endpoint is just an example and doesn't describe the existing `hosts` resource.

Start by adding a new file `hosts.py` to the `datadog/api` folder for the new endpoint. Use the following simple class structure:

```
from datadog.api.resources import (
    GetableAPIResource,
    DeletableAPIResource
)

class Hosts(GetableAPIResource, DeletableAPIResource):
    """
    A wrapper around Hosts HTTP API.
    """
    _resource_name = 'hosts'
```

Each class has the above simple structure, most importantly the following two pieces:

* A `_resource_name` - Indicates the URI of the api.
* A set of classes to inherit from. This is where the get/post/put/delete request code is defined for you. Available options are:

| Class Name         | Description                                                                                     |
| --------------------- | ----------------------------------------------------------------------------------------------- |
| CreateableAPIResource | Wrapper class for providing a `POST` request for your class, implementing a `create` method.    |
| SendableAPIResource   | Fork of CreateableAPIResource class with a `send` method.                                       |
| UpdatableAPIResource  | Wrapper class for providing a `PUT` request for your class, implementing an `update` method.    |
| DeletableAPIResource  | Wrapper class for providing a `DELETE` request for your class, implementing an `delete` method. |
| GetableAPIResource    | Wrapper class for providing a `GET` request for your class, implementing an `get` method.       |
| ListableAPIResource   | Wrapper class for providing a `GET` request for your class, implementing an `get_all` method.   |
| SearchableAPIResource | Fork of ListableAPIResource class with a `_search` method.                                      |
| ActionAPIResource     | Generic wrapper to trigger any type of HTTP request.                                            |

More information about the available classes to inherit from can be found in the [`resources.py`](https://github.com/DataDog/datadogpy/blob/master/datadog/api/resources.py) file.

Looking back at the class above:

* The URI this class can access is defined: `hosts`.
* The `delete` and `get` methods can be called by inheriting `GetableAPIResource` and `DeletableAPIResource`.

The remaining piece is to add support for the `GET` request to the `hosts/totals` URI. To do this, update your code to include:

```
from datadog.api.resources import (
    GetableAPIResource,
    DeletableAPIResource,
    ActionAPIResource
)

class Hosts(GetableAPIResource, DeletableAPIResource, ActionAPIResource):
    """
    A wrapper around Hosts HTTP API.
    """
    _resource_name = 'hosts'
    @classmethod
    def totals(cls):
        """
        Get total number of hosts active and up.

        :returns: Dictionary representing the API's JSON response
        """
        return super(Hosts, cls)._trigger_class_action('GET', 'totals')
```

Notice the addition of the new inherited class `ActionAPIResource`, and the new function `totals`. This new `totals` function calls the `_trigger_class_action` method from that class and appends `totals` to our URI, making the full path: `baseAPI/hosts/totals`.

Now you can use your new SDK and call the following methods with various params and request bodies:
* `Hosts.totals()`
* `Hosts.get()`
* `Hosts.delete()`

### Tests

This project contains:
- [Datadog API Client](/datadog/api)
- [Dogshell](/datadog/dogshell)
- [DogStatsD](/datadog/dogstatsd)
- [Threadstats](/datadog/threadstats)


We have [unit](/tests/unit), [integration](/tests/integration) and [performance](/tests/performamce) tests.
Integration tests need an _API_ and _APP Keys_ to run against a Datadog account.
- __WARNING__: Never use keys for an organization that contains anything important.

We use `tox` to run tests. You can find the [tox.ini](/tox.ini) config in the root directory.
We create 2 environments:
- Default environments: they will run all Unit, Performance and Integration tests not marked as `admin_needed`.
  - Execute this with the `tox` command.
- The explicit `integration-admin` environment: It will only run integration tests marked with the `admin_needed` marker.
  - Tests marked as `admin-needed` need an API and APP Key with admin permissions.
  - __!!!WARNING!!!__ These tests will use these keys to do destructive changes on your Datadog account.
    - __Never use keys for an organization that contains anything important!__.

#### Setup Integration Tests

To setup integration tests you will need to export the following environment variables.

```
# !!!WARNING!!! The integration tests will use these keys to do destructive changes.
# Never use keys for an organization that contains anything important.
export DD_TEST_CLIENT_API_KEY=<api_key_for_a_testing_org>
export DD_TEST_CLIENT_APP_KEY=<app_key_for_a_testing_org>
export DD_TEST_CLIENT_USER=<user_handle_for_testing_comments_api>
```

#### Run tests

By default, when invoking `tox`, [unit](#unit-tests), [style](#style-checks) and [integration](#integration-tests) that don't require admin credentials will all be run.

##### Unit tests

Unit tests are run with all the `pyXX` environments.

For example, run the unit tests with Python 3.7 with:
```
tox -e py37
```

##### Style checks

Run flake8 validation with:
```
tox -e flake8
```

##### Integration tests

Integration tests run against an actual Datadog account. You need to [provide credentials](#setup-integration-tests) for them to run.
For this reason, it is **highly recommended** to avoid providing credentials for a production account.

There are two kinds of integration tests:
  - [Regular integration tests](#regular-integration-tests)
  - [Admin integration tests](#admin-integration-tests)

###### Regular integration tests

Regular integration tests are tests that can work with credentials from a standard Datadog user, without admin privileges.
They will create resources in Datadog such as dashboards or monitors, and clean up after themselves.

Run them with
```
tox -e integration
```

###### Admin integration tests

Admin integration tests are tests that either need admin privileges to run (e.g. manage users) or can destructive changes to your org (e.g. muting/unmuting of all monitors).
They are not run by default when invoking `tox`, you have to run them explicitely with:
```
tox -e integration-admin
```

##### Run specific tests methods/classes/folders

`tox` invokes `pytest` to run the tests. You can pass `pytest` arguments in the `tox` command line for further filtering of the tests you want to run.

For example, to exclude all integrations tests using the `--ignore-glob` argument.

```
tox -- --ignore-glob=tests/integration/*
```

Another example below shows how to run test classes or test methods matching a given string by using the `-k` argument from `pytest`.
With this command, only run classes and methods matching `dogstatsd` are run.

```
tox -- -k dogstatsd
```

To run the entire `dogstatsd` folder, use:

```
tox -- tests/unit/dogstatsd
```

## Submit Your Changes

Make your change. Add tests for your change. Make the tests pass again.

You can also install this project locally in editable mode to make changes and run any manual tests.
This can be done by installing using the following pip command:

```
pip install -e <path_to_cloned_project_dir>
```

Push to your fork and submit a [pull request](/CONTRIBUTING.md).

At this point you're waiting on us. We may suggest some changes or
improvements or alternatives.
