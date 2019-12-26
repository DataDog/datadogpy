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

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


# TODO IS there a test ?
class SearchClient(object):

    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('search', help="search datadog")
        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        query_parser = verb_parsers.add_parser('query', help="Search datadog.")
        query_parser.add_argument('query', help="optionally faceted search query")
        query_parser.set_defaults(func=cls._query)

    @classmethod
    def _query(cls, args):
        api._timeout = args.timeout
        res = api.Infrastructure.search(q=args.query)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            for facet, results in list(res['results'].items()):
                for idx, result in enumerate(results):
                    if idx == 0:
                        print('\n')
                        print("%s\t%s" % (facet, result))
                    else:
                        print("%s\t%s" % (' ' * len(facet), result))
        elif format == 'raw':
            print(json.dumps(res))
        else:
            for facet, results in list(res['results'].items()):
                for result in results:
                    print("%s\t%s" % (facet, result))
