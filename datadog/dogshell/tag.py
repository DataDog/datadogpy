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


class TagClient(object):

    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('tag', help="View and modify host tags.")
        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        add_parser = verb_parsers.add_parser('add', help="Add a host to one or more tags.",
                                             description='Hosts can be specified by name or id.')
        add_parser.add_argument('host', help="host to add")
        add_parser.add_argument('tag', help="tag to add host to (one or more, space separated)",
                                nargs='+')
        add_parser.set_defaults(func=cls._add)

        replace_parser = verb_parsers.add_parser(
            'replace', help="Replace all tags with one or more new tags.",
            description='Hosts can be specified by name or id.')
        replace_parser.add_argument('host', help="host to modify")
        replace_parser.add_argument('tag', help="list of tags to add host to", nargs='+')
        replace_parser.set_defaults(func=cls._replace)

        show_parser = verb_parsers.add_parser('show', help="Show host tags.",
                                              description='Hosts can be specified by name or id.')
        show_parser.add_argument('host', help="host to show (or 'all' to show all tags)")
        show_parser.set_defaults(func=cls._show)

        detach_parser = verb_parsers.add_parser('detach', help="Remove a host from all tags.",
                                                description='Hosts can be specified by name or id.')
        detach_parser.add_argument('host', help="host to detach")
        detach_parser.set_defaults(func=cls._detach)

    @classmethod
    def _add(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Tag.create(args.host, tags=args.tag)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print("Tags for '%s':" % res['host'])
            for c in res['tags']:
                print('  ' + c)
        elif format == 'raw':
            print(json.dumps(res))
        else:
            for c in res['tags']:
                print(c)

    @classmethod
    def _replace(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Tag.update(args.host, tags=args.tag)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print("Tags for '%s':" % res['host'])
            for c in res['tags']:
                print('  ' + c)
        elif format == 'raw':
            print(json.dumps(res))
        else:
            for c in res['tags']:
                print(c)

    @classmethod
    def _show(cls, args):
        api._timeout = args.timeout
        format = args.format
        if args.host == 'all':
            res = api.Tag.get_all()
        else:
            res = api.Tag.get(args.host)
        report_warnings(res)
        report_errors(res)
        if args.host == 'all':
            if format == 'pretty':
                for tag, hosts in list(res['tags'].items()):
                    for host in hosts:
                        print(tag)
                        print('  ' + host)
                    print()
            elif format == 'raw':
                print(json.dumps(res))
            else:
                for tag, hosts in list(res['tags'].items()):
                    for host in hosts:
                        print(tag + '\t' + host)
        else:
            if format == 'pretty':
                for tag in res['tags']:
                    print(tag)
            elif format == 'raw':
                print(json.dumps(res))
            else:
                for tag in res['tags']:
                    print(tag)

    @classmethod
    def _detach(cls, args):
        api._timeout = args.timeout
        res = api.Tag.delete(args.host)
        if res is not None:
            report_warnings(res)
            report_errors(res)
