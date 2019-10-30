'''

Wraps shell commands and sends the result to Datadog as events. Ex:

dogwrap -n test-job -k $API_KEY --submit_mode all "ls -lah"

Note that you need to enclose your command in quotes to prevent python
from thinking the command line arguments belong to the python command
instead of the wrapped command.

You can also have the script only send events if they fail:

dogwrap -n test-job -k $API_KEY --submit_mode errors "ls -lah"

And you can give the command a timeout too:

dogwrap -n test-job -k $API_KEY --timeout=1 "sleep 3"

'''
# stdlib
from __future__ import print_function
import argparse
import os
import subprocess
import sys
import threading
import time

# datadog
from datadog import initialize, api
from datadog.util.config import get_version
from datadog.util.compat import is_p3k


SUCCESS = 'success'
ERROR = 'error'
WARNING = 'warning'

MAX_EVENT_BODY_LENGTH = 3000


class Timeout(Exception):
    pass


class OutputReader(threading.Thread):
    '''
    Thread collecting the output of a subprocess, optionally forwarding it to
    a given file descriptor and storing it for further retrieval.
    '''
    def __init__(self, proc_out, fwd_out=None):
        '''
        Instantiates an OutputReader.
        :param proc_out: the output to read
        :type proc_out: file descriptor
        :param fwd_out: the output to forward to (None to disable forwarding)
        :type fwd_out: file descriptor or None
        '''
        threading.Thread.__init__(self)
        self.daemon = True
        self._out_content = b""
        self._out = proc_out
        self._fwd_out = fwd_out

    def run(self):
        '''
        Thread's main loop: collects the output optionnally forwarding it to
        the file descriptor passed in the constructor.
        '''
        for line in iter(self._out.readline, b''):
            if self._fwd_out is not None:
                self._fwd_out.write(line)
            self._out_content += line
        self._out.close()

    @property
    def content(self):
        '''
        The content stored in out so far. (Not threadsafe, wait with .join())
        '''
        return self._out_content


def poll_proc(proc, sleep_interval, timeout):
    '''
    Polls the process until it returns or a given timeout has been reached
    '''
    start_time = time.time()
    returncode = None
    while returncode is None:
        returncode = proc.poll()
        if time.time() - start_time > timeout:
            raise Timeout()
        else:
            time.sleep(sleep_interval)
    return returncode


def execute(cmd, cmd_timeout, sigterm_timeout, sigkill_timeout,
            proc_poll_interval, buffer_outs):
    '''
    Launches the process and monitors its outputs
    '''
    start_time = time.time()
    returncode = -1
    stdout = b''
    stderr = b''
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    except Exception:
        print(u"Failed to execute %s" % (repr(cmd)), file=sys.stderr)
        raise
    try:
        # Let's that the threads collecting the output from the command in the
        # background
        stdout = sys.stdout.buffer if is_p3k() else sys.stdout
        stderr = sys.stderr.buffer if is_p3k() else sys.stderr
        out_reader = OutputReader(proc.stdout, stdout if not buffer_outs else None)
        err_reader = OutputReader(proc.stderr, stderr if not buffer_outs else None)
        out_reader.start()
        err_reader.start()

        # Let's quietly wait from the program's completion here et get the exit
        # code when it finishes
        returncode = poll_proc(proc, proc_poll_interval, cmd_timeout)

        # Let's harvest the outputs collected by our background threads after
        # making sure they're done reading it.
        out_reader.join()
        err_reader.join()
        stdout = out_reader.content
        stderr = err_reader.content

        duration = time.time() - start_time
    except Timeout:
        duration = time.time() - start_time
        try:
            proc.terminate()
            sigterm_start = time.time()
            try:
                print("Command timed out after %.2fs, killing with SIGTERM", file=sys.stderr) \
                    % (time.time() - start_time)
                poll_proc(proc, proc_poll_interval, sigterm_timeout)
                returncode = Timeout
            except Timeout:
                print("SIGTERM timeout failed after %.2fs, killing with SIGKILL", file=sys.stderr) \
                    % (time.time() - sigterm_start)
                proc.kill()
                poll_proc(proc, proc_poll_interval, sigkill_timeout)
                returncode = Timeout
        except OSError as e:
            # Ignore OSError 3: no process found.
            if e.errno != 3:
                raise
    return returncode, stdout, stderr, duration


def trim_text(text, max_len):
    """
    Trim input text to fit the `max_len` condition.

    If trim is needed: keep the first 1/3rd of the budget on the top,
    and the other 2 thirds on the bottom.
    """
    if len(text) <= max_len:
        return text

    trimmed_text = \
        u"{top_third}\n"\
        u"```\n" \
        u"*...trimmed...*\n" \
        u"```\n" \
        u"{bottom_two_third}\n".format(
            top_third=text[:max_len // 3],
            bottom_two_third=text[len(text) - (2 * max_len) // 3:]
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
        fmt_notifications = u"**>>>> NOTIFICATIONS <<<<**\n\n {notifications}\n".format(
            notifications=notifications.decode("utf-8", "replace")
        )

    return \
        u"%%%\n" \
        u"**>>>> CMD <<<<**\n```\n{command} \n```\n" \
        u"**>>>> EXIT CODE <<<<**\n\n {returncode}\n\n\n" \
        u"{stdout}" \
        u"{stderr}" \
        u"{notifications}" \
        u"%%%\n".format(
            command=cmd,
            returncode=returncode,
            stdout=fmt_stdout,
            stderr=fmt_stderr,
            notifications=fmt_notifications,
        )


def parse_options(raw_args=None):
    '''
    Parse the raw command line options into an options object and the remaining command string
    '''
    parser = argparse.ArgumentParser(usage="prog -n [event_name] -k [api_key] --submit_mode \
[ all | errors ] [options] \"command\". \n\nNote that you need to enclose your command in \
quotes to prevent python executing as soon as there is a space in your command. \n \nNOTICE: In \
normal mode, the whole stderr is printed before stdout, in flush_live mode they will be mixed but \
there is not guarantee that messages sent by the command on both stderr and stdout are printed in \
the order they were sent.", epilog="%prog {0}".format(get_version()))

    parser.add_argument('-n', '--name', action='store', help="the name of the event \
as it should appear on your Datadog stream")
    parser.add_argument('--config', help="location of your dogrc file (default ~/.dogrc)",
                        default=os.path.expanduser('~/.dogrc'))
    parser.add_argument('-k', '--api_key', action='store',
                      help="your DataDog API Key")
    parser.add_argument('-m', '--submit_mode', action='store',
                      default='errors', choices=['errors', 'all'], help="[ all | errors ] if set \
to error, an event will be sent only of the command exits with a non zero exit status or if it \
times out.")
    parser.add_argument('-w', '--warning', nargs='+', action='store', type=int, \
                        help="a whitespace separated list of exit codes, treated as warnings", default=None)
    parser.add_argument('-p', '--priority', action='store', choices=['normal', 'low'],
                      help="the priority of the event (default: 'normal')")
    parser.add_argument('-t', '--timeout', action='store', type=int, default=60 * 60 * 24,
                      help="(in seconds)  a timeout after which your command must be aborted. An \
event will be sent to your DataDog stream (default: 24hours)")
    parser.add_argument('--sigterm_timeout', action='store', type=int, default=60 * 2,
                      help="(in seconds)  When your command times out, the \
process it triggers is sent a SIGTERM. If this sigterm_timeout is reached, it will be sent a \
SIGKILL signal. (default: 2m)")
    parser.add_argument('--sigkill_timeout', action='store', type=int, default=60,
                      help="(in seconds) how long to wait at most after SIGKILL \
                              has been sent (default: 60s)")
    parser.add_argument('--proc_poll_interval', action='store', type=float, default=0.5,
                      help="(in seconds). interval at which your command will be polled \
(default: 500ms)")
    parser.add_argument('--notify_success', action='store', default='',
                      help="a message string and @people directives to send notifications in \
case of success.")
    parser.add_argument('--notify_error', action='store', default='',
                      help="a message string and @people directives to send notifications in \
case of error.")
    parser.add_argument('--notify_warning', action='store', default='',
                        help="a message string and @people directives to send notifications in \
    case of warning.")
    parser.add_argument('-b', '--buffer_outs', action='store_true', dest='buffer_outs', default=False,
                      help="displays the stderr and stdout of the command only once it has \
returned (the command outputs remains buffered in dogwrap meanwhile)")
    parser.add_argument('--tags', action='store', dest='tags', default='',
                      help="comma separated list of tags")

    args = parser.parse_args(args=raw_args)

    if is_p3k():
        cmd = ' '.join(args)
    else:
        cmd = b' '.join(args).decode('utf-8')

    return args, cmd


def main():
    args, cmd = parse_options()

    # If silent is checked we force the outputs to be buffered (and therefore
    # not forwarded to the Terminal streams) and we just avoid printing the
    # buffers at the end
    returncode, stdout, stderr, duration = execute(
        cmd, args.timeout,
        args.sigterm_timeout, args.sigkill_timeout,
        args.proc_poll_interval, args.buffer_outs)

    initialize(api_key=args.api_key)
    host = api._host_name

    if returncode == 0:
        alert_type = SUCCESS
        event_priority = 'low'
        event_title = u'[%s] %s succeeded in %.2fs' % (host, args.name,
                                                       duration)
    elif returncode in args.warning:
        alert_type = WARNING
        event_priority = 'normal'
        if returncode is Timeout:
            event_title = u'[%s] %s timed out after %.2fs' % (host, args.name, duration)
            returncode = -1
        else:
            event_title = u'[%s] %s failed in %.2fs' % (host, args.name, duration)
    else:
        alert_type = ERROR
        event_priority = 'normal'

        if returncode is Timeout:
            event_title = u'[%s] %s timed out after %.2fs' % (host, args.name, duration)
            returncode = -1
        else:
            event_title = u'[%s] %s failed in %.2fs' % (host, args.name, duration)

    notifications = ""
    if alert_type == SUCCESS and args.notify_success:
        notifications = args.notify_success
    elif alert_type == ERROR and args.notify_error:
        notifications = args.notify_error
    elif alert_type == WARNING and args.notify_warning:
        notifications = args.notify_warning

    if args.tags:
        tags = [t.strip() for t in args.tags.split(',')]
    else:
        tags = None

    event_body = build_event_body(cmd, returncode, stdout, stderr, notifications)

    event = {
        'alert_type': alert_type,
        'aggregation_key': args.name,
        'host': host,
        'priority': args.priority or event_priority,
        'tags': tags
    }

    if args.buffer_outs:
        if is_p3k():
            stderr = stderr.decode('utf-8')
            stdout = stdout.decode('utf-8')

        print(stderr.strip(), file=sys.stderr)
        print(stdout.strip(), file=sys.stdout)

    if args.submit_mode == 'all' or returncode != 0:
        api.Event.create(title=event_title, text=event_body, **event)

    sys.exit(returncode)


if __name__ == '__main__':
    main()
