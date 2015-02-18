"""
A small class to run a task periodically in a thread.
"""


from threading import Thread, Event


class PeriodicTimer(Thread):
    def __init__(self, interval, function, *args, **kwargs):
        Thread.__init__(self)
        self.daemon = True
        assert interval > 0
        self.interval = interval
        assert function
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.finished = Event()

    def _is_alive(self):
        # HACK: The Python interpreter can start cleaning up objects in the
        # main thread before killing daemon threads, so these references can be
        # null result in errors like that in case #18, tagged
        # "most likely raised during interpreter shutdown". This is hack to
        # try gracefully fail in these circumstances.
        #
        # http://stackoverflow.com/questions/1745232
        return (
            bool(self.finished) and
            bool(self.interval) and
            bool(self.function)
        )

    def end(self):
        if self._is_alive():
            self.finished.set()

    def run(self):
        while True:
            if not self._is_alive() or self.finished.isSet():
                break
            self.finished.wait(self.interval)
            self.function(*self.args, **self.kwargs)
