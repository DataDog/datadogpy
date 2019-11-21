import time
# datadog
from datadog import api as dog

WAIT_TIME = 10

def get_with_retry(
        resource_type,
        resource_id=None,
        operation="get",
        retry_limit=10,
        retry_condition=lambda r: r.get("errors"),
        **kwargs
):
    if resource_id is None:
        resource = getattr(getattr(dog, resource_type), operation)(**kwargs)
    else:
        resource = getattr(getattr(dog, resource_type), operation)(resource_id, **kwargs)
    retry_counter = 0
    while retry_condition(resource) and retry_counter < retry_limit:
        if resource_id is None:
            resource = getattr(getattr(dog, resource_type), operation)(**kwargs)
        else:
            resource = getattr(getattr(dog, resource_type), operation)(resource_id, **kwargs)
        retry_counter += 1
        time.sleep(WAIT_TIME)
    if retry_condition(resource):
        raise Exception(
            "Retry limit reached performing `{}` on resource {}, ID {}".format(operation, resource_type, resource_id)
        )
    return resource
