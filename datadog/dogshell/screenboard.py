# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import argparse
import json
import platform
import sys
import webbrowser

# 3p
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings, print_err
from datetime import datetime


class ScreenboardClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("screenboard", help="Create, edit, and delete screenboards.")
        parser.add_argument(
            "--string_ids",
            action="store_true",
            dest="string_ids",
            help="Represent screenboard IDs as strings instead of ints in JSON",
        )

        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser("post", help="Create screenboards.")
        post_parser.add_argument("title", help="title for the new screenboard")
        post_parser.add_argument("description", help="short description of the screenboard")
        post_parser.add_argument(
            "graphs", help="graph definitions as a JSON string." " if unset, reads from stdin.", nargs="?"
        )
        post_parser.add_argument(
            "--template_variables",
            type=_template_variables,
            default=[],
            help="a json list of template variable dicts, e.g. "
            "[{'name': 'host', 'prefix': 'host', 'default': 'host:my-host'}]",
        )
        post_parser.add_argument("--width", type=int, default=None, help="screenboard width in pixels")
        post_parser.add_argument("--height", type=int, default=None, help="screenboard height in pixels")
        post_parser.set_defaults(func=cls._post)

        update_parser = verb_parsers.add_parser("update", help="Update existing screenboards.")
        update_parser.add_argument("screenboard_id", help="screenboard to replace " " with the new definition")
        update_parser.add_argument("title", help="title for the new screenboard")
        update_parser.add_argument("description", help="short description of the screenboard")
        update_parser.add_argument(
            "graphs", help="graph definitions as a JSON string." " if unset, reads from stdin.", nargs="?"
        )
        update_parser.add_argument(
            "--template_variables",
            type=_template_variables,
            default=[],
            help="a json list of template variable dicts, e.g. "
            "[{'name': 'host', 'prefix': 'host', 'default': "
            "'host:my-host'}]",
        )
        update_parser.add_argument("--width", type=int, default=None, help="screenboard width in pixels")
        update_parser.add_argument("--height", type=int, default=None, help="screenboard height in pixels")
        update_parser.set_defaults(func=cls._update)

        show_parser = verb_parsers.add_parser("show", help="Show a screenboard definition.")
        show_parser.add_argument("screenboard_id", help="screenboard to show")
        show_parser.set_defaults(func=cls._show)

        delete_parser = verb_parsers.add_parser("delete", help="Delete a screenboard.")
        delete_parser.add_argument("screenboard_id", help="screenboard to delete")
        delete_parser.set_defaults(func=cls._delete)

        share_parser = verb_parsers.add_parser("share", help="Share an existing screenboard's" " with a public URL.")
        share_parser.add_argument("screenboard_id", help="screenboard to share")
        share_parser.set_defaults(func=cls._share)

        revoke_parser = verb_parsers.add_parser("revoke", help="Revoke an existing screenboard's" " with a public URL.")
        revoke_parser.add_argument("screenboard_id", help="screenboard to revoke")
        revoke_parser.set_defaults(func=cls._revoke)

        pull_parser = verb_parsers.add_parser("pull", help="Pull a screenboard on the server" " into a local file")
        pull_parser.add_argument("screenboard_id", help="ID of screenboard to pull")
        pull_parser.add_argument("filename", help="file to pull screenboard into")
        pull_parser.set_defaults(func=cls._pull)

        push_parser = verb_parsers.add_parser(
            "push", help="Push updates to screenboards" " from local files to the server"
        )
        push_parser.add_argument(
            "--append_auto_text",
            action="store_true",
            dest="append_auto_text",
            help="When pushing to the server, appends filename and"
            " timestamp to the end of the screenboard description",
        )
        push_parser.add_argument(
            "file", help="screenboard files to push to the server", nargs="+", type=argparse.FileType("r")
        )
        push_parser.set_defaults(func=cls._push)

        new_file_parser = verb_parsers.add_parser(
            "new_file", help="Create a new screenboard" " and put its contents in a file"
        )
        new_file_parser.add_argument("filename", help="name of file to create with" " empty screenboard")
        new_file_parser.add_argument(
            "graphs", help="graph definitions as a JSON string." " if unset, reads from stdin.", nargs="?"
        )
        new_file_parser.set_defaults(func=cls._new_file)

    @classmethod
    def _pull(cls, args):
        cls._write_screen_to_file(args.screenboard_id, args.filename, args.timeout, args.format, args.string_ids)

    # TODO Is there a test for this one ?
    @classmethod
    def _push(cls, args):
        api._timeout = args.timeout
        for f in args.file:
            screen_obj = json.load(f)

            if args.append_auto_text:
                datetime_str = datetime.now().strftime("%x %X")
                auto_text = "<br/>\nUpdated at {0} from {1} ({2}) on {3}".format(
                    datetime_str, f.name, screen_obj["id"], platform.node()
                )
                screen_obj["description"] += auto_text

            if "id" in screen_obj:
                # Always convert to int, in case it was originally a string.
                screen_obj["id"] = int(screen_obj["id"])
                res = api.Screenboard.update(**screen_obj)
            else:
                res = api.Screenboard.create(**screen_obj)

            if "errors" in res:
                print_err("Upload of screenboard {0} from file {1} failed.".format(screen_obj["id"], f.name))

            report_warnings(res)
            report_errors(res)

            if format == "pretty":
                print(pretty_json(res))
            else:
                print(json.dumps(res))

            if args.format == "pretty":
                print("Uploaded file {0} (screenboard {1})".format(f.name, screen_obj["id"]))

    @classmethod
    def _write_screen_to_file(cls, screenboard_id, filename, timeout, format="raw", string_ids=False):
        with open(filename, "w") as f:
            res = api.Screenboard.get(screenboard_id)
            report_warnings(res)
            report_errors(res)

            screen_obj = res
            if "resource" in screen_obj:
                del screen_obj["resource"]
            if "url" in screen_obj:
                del screen_obj["url"]

            if string_ids:
                screen_obj["id"] = str(screen_obj["id"])

            json.dump(screen_obj, f, indent=2)

            if format == "pretty":
                print("Downloaded screenboard {0} to file {1}".format(screenboard_id, filename))
            else:
                print("{0} {1}".format(screenboard_id, filename))

    @classmethod
    def _post(cls, args):
        graphs = sys.stdin.read()
        api._timeout = args.timeout
        format = args.format
        graphs = args.graphs
        if args.graphs is None:
            graphs = sys.stdin.read()
        graphs = json.loads(graphs)
        res = api.Screenboard.create(
            title=args.title,
            description=args.description,
            graphs=[graphs],
            template_variables=args.template_variables,
            width=args.width,
            height=args.height,
        )
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _update(cls, args):
        api._timeout = args.timeout
        format = args.format
        graphs = args.graphs
        if args.graphs is None:
            graphs = sys.stdin.read()
        graphs = json.loads(graphs)

        res = api.Screenboard.update(
            args.screenboard_id,
            board_title=args.title,
            description=args.description,
            widgets=graphs,
            template_variables=args.template_variables,
            width=args.width,
            height=args.height,
        )
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _web_view(cls, args):
        dash_id = json.load(args.file)["id"]
        url = api._api_host + "/dash/dash/{0}".format(dash_id)
        webbrowser.open(url)

    @classmethod
    def _show(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Screenboard.get(args.screenboard_id)
        report_warnings(res)
        report_errors(res)

        if args.string_ids:
            res["id"] = str(res["id"])

        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _delete(cls, args):
        api._timeout = args.timeout
        # TODO CHECK
        res = api.Screenboard.delete(args.screenboard_id)
        if res is not None:
            report_warnings(res)
            report_errors(res)

    @classmethod
    def _share(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Screenboard.share(args.screenboard_id)

        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _revoke(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Screenboard.revoke(args.screenboard_id)

        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _new_file(cls, args):
        api._timeout = args.timeout
        format = args.format
        graphs = args.graphs
        if args.graphs is None:
            graphs = sys.stdin.read()
        graphs = json.loads(graphs)
        res = api.Screenboard.create(
            board_title=args.filename, description="Description for {0}".format(args.filename), widgets=[graphs]
        )
        report_warnings(res)
        report_errors(res)

        cls._write_screen_to_file(res["id"], args.filename, args.timeout, format, args.string_ids)

        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))


def _template_variables(tpl_var_input):
    if "[" not in tpl_var_input:
        return [v.strip() for v in tpl_var_input.split(",")]
    else:
        try:
            return json.loads(tpl_var_input)
        except Exception:
            raise argparse.ArgumentTypeError("bad template_variable json parameter")
