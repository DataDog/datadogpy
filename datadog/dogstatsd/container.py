# Unless explicitly stated otherwise all files in this repository are licensed under
# the BSD-3-Clause License. This product includes software developed at Datadog
# (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc

import errno
import re


class UnresolvableContainerID(Exception):
    """
    Unable to get container ID from cgroup.
    """


class ContainerID(object):
    """
    A reader class that retrieves the current container ID parsed from a the cgroup file.

    Returns:
    object: ContainerID

    Raises:
        `NotImplementedError`: No proc filesystem is found (non-Linux systems)
        `UnresolvableContainerID`: Unable to read the container ID
    """

    CGROUP_PATH = "/proc/self/cgroup"
    UUID_SOURCE = r"[0-9a-f]{8}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{12}"
    CONTAINER_SOURCE = r"[0-9a-f]{64}"
    TASK_SOURCE = r"[0-9a-f]{32}-\d+"
    LINE_RE = re.compile(r"^(\d+):([^:]*):(.+)$")
    CONTAINER_RE = re.compile(r"(?:.+)?({0}|{1}|{2})(?:\.scope)?$".format(UUID_SOURCE, CONTAINER_SOURCE, TASK_SOURCE))

    def __init__(self):
        self._container_id = self._read_container_id(self.CGROUP_PATH)

    def _read_container_id(self, fpath):
        try:
            with open(fpath, mode="r") as fp:
                for line in fp:
                    line = line.strip()
                    match = self.LINE_RE.match(line)
                    if not match:
                        continue
                    _, _, path = match.groups()
                    parts = [p for p in path.split("/")]
                    if len(parts):
                        match = self.CONTAINER_RE.match(parts.pop())
                        if match:
                            return match.group(1)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise NotImplementedError("Unable to open {}.".format(self.CGROUP_PATH))
        except Exception:
            raise UnresolvableContainerID("Unable to read the container ID.")
        return None

    def get_container_id(self):
        """
        Returns the container ID if found, None otherwise.
        """
        return self._container_id
