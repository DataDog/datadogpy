"""
List all users returns "OK" response
"""

from os import environ
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.users_api import UsersApi

# there is a valid "user" in the system
USER_DATA_ATTRIBUTES_EMAIL = environ["USER_DATA_ATTRIBUTES_EMAIL"]

configuration = Configuration()
with ApiClient(configuration) as api_client:
    api_instance = UsersApi(api_client)
    response = api_instance.list_users(
        filter=USER_DATA_ATTRIBUTES_EMAIL,
    )

    print(response)
