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


class ServiceCheckClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('service_check', help="Perform service checks")
        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        check_parser = verb_parsers.add_parser('check', help="text for the message")
        check_parser.add_argument('check', help="text for the message")
        check_parser.add_argument('host_name', help="name of the host submitting the check")
        check_parser.add_argument('status', help="integer for the status of the check."
                                  " i.e: '0': OK, '1': WARNING, '2': CRITICAL, '3': UNKNOWN")
        check_parser.add_argument('--timestamp', help="POSIX timestamp of the event", default=None)
        check_parser.add_argument('--message', help="description of why this status occurred",
                                  default=None)
        check_parser.add_argument('--tags', help="comma separated list of tags", default=None)
        check_parser.set_defaults(func=cls._check)

    @classmethod
    def _check(cls, args):
        api._timeout = args.timeout
        format = args.format
        if args.tags:
            tags = sorted(set([t.strip() for t in args.tags.split(',') if t.strip()]))
        else:
            tags = None
        res = api.ServiceCheck.check(
            check=args.check, host_name=args.host_name, status=int(args.status),
            timestamp=args.timestamp, message=args.message, tags=tags)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))
