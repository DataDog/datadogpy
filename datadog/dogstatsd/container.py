# Unless explicitly stated otherwise all files in this repository are licensed under
# the BSD-3-Clause License. This product includes software developed at Datadog
# (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc

import errno
import os
import re


class UnresolvableContainerID(Exception):
    """
    Unable to get container ID from cgroup.
    """


class Cgroup(object):
    """
    A reader class that retrieves either:
    - The current container ID parsed from the cgroup file
    - The cgroup controller inode.

    Returns:
    object: Cgroup

    Raises:
        `NotImplementedError`: No proc filesystem is found (non-Linux systems)
        `UnresolvableContainerID`: Unable to read the container ID
    """

    CGROUP_PATH = "/proc/self/cgroup"
    CGROUP_MOUNT_PATH = "/sys/fs/cgroup"  # cgroup mount path.
    CGROUP_NS_PATH = "/proc/self/ns/cgroup"  # path to the cgroup namespace file.
    CGROUPV1_BASE_CONTROLLER = "memory"  # controller used to identify the container-id in cgroup v1 (memory).
    CGROUPV2_BASE_CONTROLLER = ""  # controller used to identify the container-id in cgroup v2.
    HOST_CGROUP_NAMESPACE_INODE = 0xEFFFFFFB  # inode of the host cgroup namespace.

    UUID_SOURCE = r"[0-9a-f]{8}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{12}"
    CONTAINER_SOURCE = r"[0-9a-f]{64}"
    TASK_SOURCE = r"[0-9a-f]{32}-\d+"
    LINE_RE = re.compile(r"^(\d+):([^:]*):(.+)$")
    CONTAINER_RE = re.compile(r"(?:.+)?({0}|{1}|{2})(?:\.scope)?$".format(UUID_SOURCE, CONTAINER_SOURCE, TASK_SOURCE))

    def __init__(self):
        if self._is_host_cgroup_namespace():
            self.container_id = self._read_cgroup_path()
            return
        self.container_id = self._get_cgroup_from_inode()

    def _is_host_cgroup_namespace(self):
        """Check if the current process is in a host cgroup namespace."""
        try:
            return (
                os.stat(self.CGROUP_NS_PATH).st_ino == self.HOST_CGROUP_NAMESPACE_INODE
                if os.path.exists(self.CGROUP_NS_PATH)
                else False
            )
        except Exception:
            return False

    def _read_cgroup_path(self):
        """Read the container ID from the cgroup file."""
        try:
            with open(self.CGROUP_PATH, mode="r") as fp:
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
                            return "ci-{0}".format(match.group(1))
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise NotImplementedError("Unable to open {}.".format(self.CGROUP_PATH))
        except Exception as e:
            raise UnresolvableContainerID("Unable to read the container ID: " + str(e))
        return None

    def _get_cgroup_from_inode(self):
        """Read the container ID from the cgroup inode."""
        # Parse /proc/self/cgroup and get a map of controller to its associated cgroup node path.
        cgroup_controllers_paths = {}
        with open(self.CGROUP_PATH, mode="r") as fp:
            for line in fp:
                tokens = line.strip().split(":")
                if len(tokens) != 3:
                    continue
                if tokens[1] == self.CGROUPV1_BASE_CONTROLLER or tokens[1] == self.CGROUPV2_BASE_CONTROLLER:
                    cgroup_controllers_paths[tokens[1]] = tokens[2]

        # Retrieve the cgroup inode from "/sys/fs/cgroup + controller + cgroupNodePath"
        for controller in [
            self.CGROUPV1_BASE_CONTROLLER,
            self.CGROUPV2_BASE_CONTROLLER,
        ]:
            if controller in cgroup_controllers_paths:
                inode_path = os.path.join(
                    self.CGROUP_MOUNT_PATH,
                    controller,
                    cgroup_controllers_paths[controller] if cgroup_controllers_paths[controller] != "/" else "",
                )
                inode = os.stat(inode_path).st_ino
                # 0 is not a valid inode. 1 is a bad block inode and 2 is the root of a filesystem.
                if inode > 2:
                    return "in-{0}".format(inode)

        return None
