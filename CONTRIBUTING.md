# Contributing

We love pull requests. Here's a quick guide.

Fork, then clone the repo:

    git clone git@github.com:your-username/datadogpy.git

Make sure the tests pass:

    python setup.py test

Make your change. Add tests for your change. Make the tests pass again.

You can also install this project locally in editable mode to make changes and run any manual tests. This can be done by installing using the following pip command:

```
pip install -e <path_to_cloned_project_dir>
```

Push to your fork and [submit a pull request][pr].

[pr]: https://github.com/your-username/datadogpy/compare/DataDog:master...master

At this point you're waiting on us. We may suggest some changes or
improvements or alternatives.

# Adding new API endpoints
This section outlines the process for adding a new endpoint to this API client.

Lets use the example of creating an endpoint for `Hosts`. For this example endpoint, we will accept a GET and DELETE request at the `/hosts` endpoint as well as a GET resquest at the `hosts/totals` endpoint. **NOTE:** This endpoint is just an exmaple and doesn't describe the existing `hosts` resource.

First start by adding a new file to the `datadog -> api` folder for our new endpoint `hosts.py`. We'll use the following simple class structure:

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

* A `_resource_name` - Indicates the uri of the api.
* A set of classes to inherit from. This is where the get/post/put/delete request code is defined for you. Available options are:
  * CreateableAPIResource - Wrapper class for providing a `POST` request for your class, implementing a `create` method.
  * SendableAPIResource - Fork of CreateableAPIResource class with a `send` method.
  * UpdatableAPIResource - Wrapper class for providing a `PUT` request for your class, implementing an `update` method.
  * DeletableAPIResource - Wrapper class for providing a `DELETE` request for your class, implementing an `delete` method.
  * GetableAPIResource - Wrapper class for providing a `GET` request for your class, implementing an `get` method.
  * ListableAPIResource - Wrapper class for providing a `GET` request for your class, implementing an `get_all` method.
  * SearchableAPIResource - Fork of ListableAPIResource class with a `_search` method.
  * ActionAPIResource - Generic wrapper to trigger any type of HTTP request.

Looking back at our simple class, we defined the URI this class will access, `hosts`, and that we can call the `delete` and `get` functions since we are inheriting `GetableAPIResource` and `DeletableAPIResource`.

The remaining piece is to add support for our `GET` request to the `hosts/totals` URI. To do this, we can update our code to include:

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

Notice the addition of the new class we're inheriting `ActionAPIResource` in addition to the new function `totals`. This new `totals` function utilizes the `_trigger_class_action` method from that class and appends `totals` to our URI.

Now we can use our new SDK and call the following methods with varioud params and request bodies:
* Hosts.totals()
* Hosts.get()
* Hosts.delete()
