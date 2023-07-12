# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""

Wraps shell commands and sends the result to Datadog as events. Ex:

dogwrap -n test-job -k $API_KEY --submit_mode all "ls -lah"

Note that you need to enclose your command in quotes to prevent python
from thinking the command line arguments belong to the python command
instead of the wrapped command.

You can also have the script only send events if they fail:

dogwrap -n test-job -k $API_KEY --submit_mode errors "ls -lah"

And you can give the command a timeout too:

dogwrap -n test-job -k $API_KEY --timeout=1 "sleep 3"

"""
# stdlib
from __future__ import print_function

import os
from copy import copy
import optparse
import subprocess
import sys
import threading
import time
import warnings

# datadog
from datadog import initialize, api, __version__
from datadog.util.compat import is_p3k


SUCCESS = "success"
ERROR = "error"
WARNING = "warning"

MAX_EVENT_BODY_LENGTH = 3000


class Timeout(Exception):
    pass


class OutputReader(threading.Thread):
    """
    Thread collecting the output of a subprocess, optionally forwarding it to
    a given file descriptor and storing it for further retrieval.
    """

    def __init__(self, proc_out, fwd_out=None):
        """
        Instantiates an OutputReader.
        :param proc_out: the output to read
        :type proc_out: file descriptor
        :param fwd_out: the output to forward to (None to disable forwarding)
        :type fwd_out: file descriptor or None
        """
        threading.Thread.__init__(self)
        self.daemon = True
        self._out_content = b""
        self._out = proc_out
        self._fwd_out = fwd_out

    def run(self):
        """
        Thread's main loop: collects the output optionnally forwarding it to
        the file descriptor passed in the constructor.
        """
        for line in iter(self._out.readline, b""):
            if self._fwd_out is not None:
                self._fwd_out.write(line)
            self._out_content += line
        self._out.close()

    @property
    def content(self):
        """
        The content stored in out so far. (Not threadsafe, wait with .join())
        """
        return self._out_content


def poll_proc(proc, sleep_interval, timeout):
    """
    Polls the process until it returns or a given timeout has been reached
    """
    start_time = time.time()
    returncode = None
    while returncode is None:
        returncode = proc.poll()
        if time.time() - start_time > timeout:
            raise Timeout()
        else:
            time.sleep(sleep_interval)
    return returncode


def execute(cmd, cmd_timeout, sigterm_timeout, sigkill_timeout, proc_poll_interval, buffer_outs):
    """
    Launches the process and monitors its outputs
    """
    start_time = time.time()
    returncode = -1
    stdout = b""
    stderr = b""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    except Exception:
        print(u"Failed to execute %s" % (repr(cmd)), file=sys.stderr)
        raise
    try:
        # Let's that the threads collecting the output from the command in the
        # background
        stdout_buffer = sys.stdout.buffer if is_p3k() else sys.stdout
        stderr_buffer = sys.stderr.buffer if is_p3k() else sys.stderr
        out_reader = OutputReader(proc.stdout, stdout_buffer if not buffer_outs else None)
        err_reader = OutputReader(proc.stderr, stderr_buffer if not buffer_outs else None)
        out_reader.start()
        err_reader.start()

        # Let's quietly wait from the program's completion here to get the exit
        # code when it finishes
        returncode = poll_proc(proc, proc_poll_interval, cmd_timeout)
    except Timeout:
        returncode = Timeout
        sigterm_start = time.time()
        print("Command timed out after %.2fs, killing with SIGTERM" % (time.time() - start_time), file=sys.stderr)
        try:
            proc.terminate()
            try:
                poll_proc(proc, proc_poll_interval, sigterm_timeout)
            except Timeout:
                print(
                    "SIGTERM timeout failed after %.2fs, killing with SIGKILL" % (time.time() - sigterm_start),
                    file=sys.stderr,
                )
                sigkill_start = time.time()
                proc.kill()
                try:
                    poll_proc(proc, proc_poll_interval, sigkill_timeout)
                except Timeout:
                    print(
                        "SIGKILL timeout failed after %.2fs, exiting" % (time.time() - sigkill_start), file=sys.stderr
                    )
        except OSError as e:
            # Ignore OSError 3: no process found.
            if e.errno != 3:
                raise

    # Let's harvest the outputs collected by our background threads
    # after making sure they're done reading it.
    out_reader.join()
    err_reader.join()
    stdout = out_reader.content
    stderr = err_reader.content

    duration = time.time() - start_time

    return returncode, stdout, stderr, duration


def trim_text(text, max_len):
    """
    Trim input text to fit the `max_len` condition.

    If trim is needed: keep the first 1/3rd of the budget on the top,
    and the other 2 thirds on the bottom.
    """
    if len(text) <= max_len:
        return text

    trimmed_text = (
        u"{top_third}\n"
        u"```\n"
        u"*...trimmed...*\n"
        u"```\n"
        u"{bottom_two_third}\n".format(
            top_third=text[: max_len // 3], bottom_two_third=text[len(text) - (2 * max_len) // 3 :]
        )
    )

    return trimmed_text


def build_event_body(cmd, returncode, stdout, stderr, notifications):
    """
    Format and return an event body.

    Note: do not exceed MAX_EVENT_BODY_LENGTH length.
    """
    fmt_stdout = u""
    fmt_stderr = u""
    fmt_notifications = u""

    max_length = MAX_EVENT_BODY_LENGTH // 2 if stdout and stderr else MAX_EVENT_BODY_LENGTH

    if stdout:
        fmt_stdout = u"**>>>> STDOUT <<<<**\n```\n{stdout} \n```\n".format(
            stdout=trim_text(stdout.decode("utf-8", "replace"), max_length)
        )

    if stderr:
        fmt_stderr = u"**>>>> STDERR <<<<**\n```\n{stderr} \n```\n".format(
            stderr=trim_text(stderr.decode("utf-8", "replace"), max_length)
        )

    if notifications:
        notifications = notifications.decode("utf-8", "replace") if isinstance(notifications, bytes) else notifications
        fmt_notifications = u"**>>>> NOTIFICATIONS <<<<**\n\n {notifications}\n".format(notifications=notifications)

    return (
        u"%%%\n"
        u"**>>>> CMD <<<<**\n```\n{command} \n```\n"
        u"**>>>> EXIT CODE <<<<**\n\n {returncode}\n\n\n"
        u"{stdout}"
        u"{stderr}"
        u"{notifications}"
        u"%%%\n".format(
            command=cmd,
            returncode=returncode,
            stdout=fmt_stdout,
            stderr=fmt_stderr,
            notifications=fmt_notifications,
        )
    )


def generate_warning_codes(option, opt, options_warning):
    try:
        # options_warning is a string e.g.: --warning_codes 123,456,789
        # we need to create a list from it
        warning_codes = options_warning.split(",")
        return warning_codes
    except ValueError:
        raise optparse.OptionValueError("option %s: invalid warning codes value(s): %r" % (opt, options_warning))


class DogwrapOption(optparse.Option):
    # https://docs.python.org/3.7/library/optparse.html#adding-new-types
    TYPES = optparse.Option.TYPES + ("warning_codes",)
    TYPE_CHECKER = copy(optparse.Option.TYPE_CHECKER)
    TYPE_CHECKER["warning_codes"] = generate_warning_codes


def parse_options(raw_args=None):
    """
    Parse the raw command line options into an options object and the remaining command string
    """
    parser = optparse.OptionParser(
        usage='%prog -n [event_name] -k [api_key] --submit_mode \
[ all | errors | warnings] [options] "command". \n\nNote that you need to enclose your command in \
quotes to prevent python executing as soon as there is a space in your command. \n \nNOTICE: In \
normal mode, the whole stderr is printed before stdout, in flush_live mode they will be mixed but \
there is not guarantee that messages sent by the command on both stderr and stdout are printed in \
the order they were sent.',
        version="%prog {0}".format(__version__),
        option_class=DogwrapOption,
    )

    parser.add_option(
        "-n",
        "--name",
        action="store",
        type="string",
        help="the name of the event \
as it should appear on your Datadog stream",
    )
    parser.add_option(
        "-k",
        "--api_key",
        action="store",
        type="string",
        help="your DataDog API Key",
        default=os.environ.get("DD_API_KEY"),
    )
    parser.add_option(
        "-s",
        "--site",
        action="store",
        type="string",
        default="datadoghq.com",
        help="The site to send data. Accepts us (datadoghq.com), eu (datadoghq.eu), \
us3 (us3.datadoghq.com), us5 (us5.datadoghq.com), or ap1 (ap1.datadoghq.com), \
gov (ddog-gov.com), or custom url. default: us",
    )
    parser.add_option(
        "-m",
        "--submit_mode",
        action="store",
        type="choice",
        default="errors",
        choices=["errors", "warnings", "all"],
        help="[ all | errors | warnings ] if set \
to error, an event will be sent only of the command exits with a non zero exit status or if it \
times out. If set to warning, a list of exit codes need to be provided",
    )
    parser.add_option(
        "--warning_codes",
        action="store",
        type="warning_codes",
        dest="warning_codes",
        help="comma separated list of warning codes, e.g: 127,255",
    )
    parser.add_option(
        "-p",
        "--priority",
        action="store",
        type="choice",
        choices=["normal", "low"],
        help="the priority of the event (default: 'normal')",
    )
    parser.add_option(
        "-t",
        "--timeout",
        action="store",
        type="int",
        default=60 * 60 * 24,
        help="(in seconds)  a timeout after which your command must be aborted. An \
event will be sent to your DataDog stream (default: 24hours)",
    )
    parser.add_option(
        "--sigterm_timeout",
        action="store",
        type="int",
        default=60 * 2,
        help="(in seconds)  When your command times out, the \
process it triggers is sent a SIGTERM. If this sigterm_timeout is reached, it will be sent a \
SIGKILL signal. (default: 2m)",
    )
    parser.add_option(
        "--sigkill_timeout",
        action="store",
        type="int",
        default=60,
        help="(in seconds) how long to wait at most after SIGKILL \
                              has been sent (default: 60s)",
    )
    parser.add_option(
        "--proc_poll_interval",
        action="store",
        type="float",
        default=0.5,
        help="(in seconds). interval at which your command will be polled \
(default: 500ms)",
    )
    parser.add_option(
        "--notify_success",
        action="store",
        type="string",
        default="",
        help="a message string and @people directives to send notifications in \
case of success.",
    )
    parser.add_option(
        "--notify_error",
        action="store",
        type="string",
        default="",
        help="a message string and @people directives to send notifications in \
case of error.",
    )
    parser.add_option(
        "--notify_warning",
        action="store",
        type="string",
        default="",
        help="a message string and @people directives to send notifications in \
    case of warning.",
    )
    parser.add_option(
        "-b",
        "--buffer_outs",
        action="store_true",
        dest="buffer_outs",
        default=False,
        help="displays the stderr and stdout of the command only once it has \
returned (the command outputs remains buffered in dogwrap meanwhile)",
    )
    parser.add_option(
        "--send_metric",
        action="store_true",
        dest="send_metric",
        default=False,
        help="sends a metric for event duration",
    )
    parser.add_option(
        "--tags", action="store", type="string", dest="tags", default="", help="comma separated list of tags"
    )

    options, args = parser.parse_args(args=raw_args)

    if is_p3k():
        cmd = " ".join(args)
    else:
        cmd = b" ".join(args).decode("utf-8")

    return options, cmd


def main():
    options, cmd = parse_options()

    # If silent is checked we force the outputs to be buffered (and therefore
    # not forwarded to the Terminal streams) and we just avoid printing the
    # buffers at the end
    returncode, stdout, stderr, duration = execute(
        cmd,
        options.timeout,
        options.sigterm_timeout,
        options.sigkill_timeout,
        options.proc_poll_interval,
        options.buffer_outs,
    )

    if options.site in ("datadoghq.com", "us"):
        api_host = "https://api.datadoghq.com"
    elif options.site in ("datadoghq.eu", "eu"):
        api_host = "https://api.datadoghq.eu"
    elif options.site in ("us3.datadoghq.com", "us3"):
        api_host = "https://api.us3.datadoghq.com"
    elif options.site in ("us5.datadoghq.com", "us5"):
        api_host = "https://api.us5.datadoghq.com"
    elif options.site in ("ap1.datadoghq.com", "ap1"):
        api_host = "https://api.ap1.datadoghq.com"
    elif options.site in ("ddog-gov.com", "gov"):
        api_host = "https://api.ddog-gov.com"
    else:
        api_host = options.site

    initialize(api_key=options.api_key, api_host=api_host)
    host = api._host_name

    warning_codes = None

    if options.warning_codes:
        # Convert warning codes from string to int since return codes will evaluate the latter
        warning_codes = list(map(int, options.warning_codes))

    if returncode == 0:
        alert_type = SUCCESS
        event_priority = "low"
        event_title = u"[%s] %s succeeded in %.2fs" % (host, options.name, duration)
    elif returncode != 0 and options.submit_mode == "warnings":
        if not warning_codes:
            # the list of warning codes is empty - the option was not specified
            print("A comma separated list of exit codes need to be provided")
            sys.exit()
        elif returncode in warning_codes:
            alert_type = WARNING
            event_priority = "normal"
            event_title = u"[%s] %s failed in %.2fs" % (host, options.name, duration)
        else:
            print("Command exited with a different exit code that the one(s) provided")
            sys.exit()
    else:
        alert_type = ERROR
        event_priority = "normal"

        if returncode is Timeout:
            event_title = u"[%s] %s timed out after %.2fs" % (host, options.name, duration)
            returncode = -1
        else:
            event_title = u"[%s] %s failed in %.2fs" % (host, options.name, duration)

    notifications = ""

    if alert_type == SUCCESS and options.notify_success:
        notifications = options.notify_success
    elif alert_type == ERROR and options.notify_error:
        notifications = options.notify_error
    elif alert_type == WARNING and options.notify_warning:
        notifications = options.notify_warning

    if options.tags:
        tags = [t.strip() for t in options.tags.split(",")]
    else:
        tags = None

    event_body = build_event_body(cmd, returncode, stdout, stderr, notifications)

    event = {
        "alert_type": alert_type,
        "aggregation_key": options.name,
        "host": host,
        "priority": options.priority or event_priority,
        "tags": tags,
    }

    if options.buffer_outs:
        if is_p3k():
            stderr = stderr.decode("utf-8")
            stdout = stdout.decode("utf-8")

        print(stderr.strip(), file=sys.stderr)
        print(stdout.strip(), file=sys.stdout)

    if options.submit_mode == "all" or returncode != 0:
        if options.send_metric:
            event_name_tag = "event_name:{}".format(options.name)
            if tags:
                duration_tags = tags + [event_name_tag]
            else:
                duration_tags = [event_name_tag]
            api.Metric.send(metric="dogwrap.duration", points=duration, tags=duration_tags, type="gauge")
        api.Event.create(title=event_title, text=event_body, **event)

    sys.exit(returncode)


if __name__ == "__main__":
    if sys.argv[0].endswith("dogwrap"):
        warnings.warn("dogwrap is pending deprecation. Please use dogshellwrap instead.", PendingDeprecationWarning)
    main()
