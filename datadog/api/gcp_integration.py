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

from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    DeletableAPIResource, UpdatableAPIResource


class GcpIntegration(GetableAPIResource, CreateableAPIResource, DeletableAPIResource,
                     UpdatableAPIResource):
    """
    A wrapper around GCP integration API.
    """
    _resource_name = 'integration'
    _resource_id = 'gcp'

    @classmethod
    def list(cls, **params):
        """
        List all Datadog-Gcp integrations available in your Datadog organization.

        >>> api.GcpIntegration.list()
        """
        return super(GcpIntegration, cls).get(id=cls._resource_id, **params)

    @classmethod
    def delete(cls, **body):
        """
        Delete a given Datadog-GCP integration.

        >>> project_id="<GCP_CLIENT_ID>"
        >>> client_email="<GCP_CLIENT_EMAIL>"

        >>> api.GcpIntegration.delete(project_id=project_id, client_email=client_email)
        """
        return super(GcpIntegration, cls).delete(id=cls._resource_id, body=body)

    @classmethod
    def create(cls, **params):
        """
        Add a new GCP integration config.

        All of the following fields values are provided by the \
        JSON service account key file created in the GCP Console \
        for service accounts; Refer to the Datadog-Google Cloud \
        Platform integration installation instructions to see how \
        to generate one for your organization. For further references, \
        consult the Google Cloud service account documentation.

        >>> type="service_account"
        >>> project_id="<GCP_PROJECT_ID>"
        >>> private_key_id="<GCP_PRIVATE_KEY_ID>"
        >>> private_key="<GCP_PRIVATE_KEY>"
        >>> client_email="<GCP_CLIENT_EMAIL>"
        >>> client_id="<GCP_CLIENT_ID>"
        >>> auth_uri="<GCP_AUTH_URI"
        >>> token_uri="<GCP_TOKEN_URI>"
        >>> auth_provider_x509_cert_url="<GCP_AUTH_PROVIDER_X509_CERT_URL>"
        >>> client_x509_cert_url="<GCP_CLIENT_X509_CERT_URL>"
        >>> host_filters="<KEY>:<VALUE>,<KEY>:<VALUE>"

        >>> api.GcpIntegration.create(type=type, project_id=project_id, \
        private_key_id=private_key_id,private_key=private_key, \
        client_email=client_email, client_id=client_id, \
        auth_uri=auth_uri, token_uri=token_uri, \
        auth_provider_x509_cert_url=auth_provider_x509_cert_url, \
        client_x509_cert_url=client_x509_cert_url, host_filters=host_filters)
        """
        return super(GcpIntegration, cls).create(id=cls._resource_id, **params)

    @classmethod
    def update(cls, **body):
        """
        Update an existing service account partially (one or multiple fields), \
        by supplying a new value for the field(s) to be updated.

        `project_id` and `client_email` are required, in order to identify the \
        right service account to update. \
        The unspecified fields will keep their original values.

        The only use case for updating this integration is to change \
        host filtering and automute settings. Otherwise, an entirely \
        new integration config is needed.

        >>> project_id="<GCP_PROJECT_ID>"
        >>> client_email="<GCP_CLIENT_EMAIL>"
        >>> host_filters="<NEW_HOST_FILTERS>"
        >>> automute=true #boolean

        >>> api.GcpIntegration.update(project_id=project_id, \
        client_email=client_email, host_filters=host_filters, \
        automute=automute)
        """
        params = {}
        return super(GcpIntegration, cls).update(id=cls._resource_id, params=params, **body)
