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

from datadog.api.resources import GetableAPIResource, UpdatableAPIResource


class Metadata(GetableAPIResource, UpdatableAPIResource):
    """
    A wrapper around Metric Metadata HTTP API
    """
    _resource_name = 'metrics'

    @classmethod
    def get(cls, metric_name):
        """
        Get metadata information on an existing Datadog metric

        param metric_name: metric name (ex. system.cpu.idle)

        :returns: Dictionary representing the API's JSON response
        """
        if not metric_name:
            raise KeyError("'metric_name' parameter is required")

        return super(Metadata, cls).get(metric_name)

    @classmethod
    def update(cls, metric_name, **params):
        """
        Update metadata fields for an existing Datadog metric.
        If the metadata does not exist for the metric it is created by
        the update.

        :param type: type of metric (ex. "gauge", "rate", etc.)
                            see http://docs.datadoghq.com/metrictypes/
        :type type: string

        :param description: description of the metric
        :type description: string

        :param short_name: short name of the metric
        :type short_name: string

        :param unit: unit type associated with the metric (ex. "byte", "operation")
                     see http://docs.datadoghq.com/units/ for full list
        :type unit: string

        :param per_unit: per unit type (ex. "second" as in "queries per second")
                         see http://docs.datadoghq.com/units/ for full list
        :type per_unit: string

        :param statsd_interval: statsd flush interval for metric in seconds (if applicable)
        :type statsd_interval: integer

        :returns: Dictionary representing the API's JSON response

        >>> api.Metadata.update(metric_name='api.requests.served', metric_type="counter")
        """
        if not metric_name:
            raise KeyError("'metric_name' parameter is required")

        return super(Metadata, cls).update(id=metric_name, **params)
