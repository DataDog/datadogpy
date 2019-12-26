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

"""
Helper(s), resolve the system's default interface.
"""
# stdlib
import socket
import struct


class UnresolvableDefaultRoute(Exception):
    """
    Unable to resolve system's default route.
    """


def get_default_route():
    """
    Return the system default interface using the proc filesystem.

    Returns:
        string: default route

    Raises:
        `NotImplementedError`: No proc filesystem is found (non-Linux systems)
        `StopIteration`: No default route found
    """
    try:
        with open('/proc/net/route') as f:
            for line in f.readlines():
                fields = line.strip().split()
                if fields[1] == '00000000':
                    return socket.inet_ntoa(struct.pack('<L', int(fields[2], 16)))
    except IOError:
        raise NotImplementedError(
            u"Unable to open `/proc/net/route`. "
            u"`use_default_route` option is available on Linux only."
        )

    raise UnresolvableDefaultRoute(u"Unable to resolve the system default's route.")
