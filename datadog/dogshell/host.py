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

import json

# 3p
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


class HostClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('host', help='Mute, unmute hosts')
        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        mute_parser = verb_parsers.add_parser('mute', help='Mute a host')
        mute_parser.add_argument('host_name', help='host to mute')
        mute_parser.add_argument('--end', help="POSIX timestamp, if omitted,"
                                 " host will be muted until explicitly unmuted", default=None)
        mute_parser.add_argument('--message', help="string to associate with the"
                                 " muting of this host", default=None)
        mute_parser.add_argument('--override', help="true/false, if true and the host is already"
                                 " muted, will overwrite existing end on the host",
                                 action='store_true')
        mute_parser.set_defaults(func=cls._mute)

        unmute_parser = verb_parsers.add_parser('unmute', help='Unmute a host')
        unmute_parser.add_argument('host_name', help='host to mute')
        unmute_parser.set_defaults(func=cls._unmute)

    @classmethod
    def _mute(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Host.mute(args.host_name, end=args.end, message=args.message,
                            override=args.override)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _unmute(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Host.unmute(args.host_name)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))
