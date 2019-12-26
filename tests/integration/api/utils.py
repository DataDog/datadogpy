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
