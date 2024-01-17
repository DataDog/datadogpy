# -*- coding: utf-8 -*-

# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Tests for container.py
"""

import mock
import pytest

from datadog.dogstatsd.container import Cgroup


def get_mock_open(read_data=None):
    mock_open = mock.mock_open(read_data=read_data)
    return mock.patch("datadog.dogstatsd.container.open", mock_open)


@pytest.mark.parametrize(
    "file_contents,expected_container_id",
    (
        # Docker file
        (
            """
13:name=systemd:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
12:pids:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
11:hugetlb:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
10:net_prio:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
9:perf_event:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
8:net_cls:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
7:freezer:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
6:devices:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
5:memory:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
4:blkio:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
3:cpuacct:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
2:cpu:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
1:cpuset:/docker/3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860
            """,
            "3726184226f5d3147c25fdeab5b60097e378e8a720503a5e19ecfdf29f869860",
        ),
        # k8s file
        (
            """
11:perf_event:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
10:pids:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
9:memory:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
8:cpu,cpuacct:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
7:blkio:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
6:cpuset:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
5:devices:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
4:freezer:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
3:net_cls,net_prio:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
2:hugetlb:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
1:name=systemd:/kubepods/test/pod3d274242-8ee0-11e9-a8a6-1e68d864ef1a/3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1
            """,
            "3e74d3fd9db4c9dd921ae05c2502fb984d0cde1b36e581b13f79c639da4518a1",
        ),
        # ECS file
        (
            """
9:perf_event:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
8:memory:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
7:hugetlb:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
6:freezer:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
5:devices:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
4:cpuset:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
3:cpuacct:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
2:cpu:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
1:blkio:/ecs/test-ecs-classic/5a0d5ceddf6c44c1928d367a815d890f/38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce
            """,
            "38fac3e99302b3622be089dd41e7ccf38aff368a86cc339972075136ee2710ce",
        ),
        # Fargate file
        (
            """
11:hugetlb:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
10:pids:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
9:cpuset:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
8:net_cls,net_prio:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
7:cpu,cpuacct:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
6:perf_event:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
5:freezer:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
4:devices:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
3:blkio:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
2:memory:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
1:name=systemd:/ecs/55091c13-b8cf-4801-b527-f4601742204d/432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da
            """,
            "432624d2150b349fe35ba397284dea788c2bf66b885d14dfc1569b01890ca7da",
        ),
        # Fargate file >= 1.4.0
        (
            """
11:hugetlb:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
10:pids:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
9:cpuset:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
8:net_cls,net_prio:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
7:cpu,cpuacct:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
6:perf_event:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
5:freezer:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
4:devices:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
3:blkio:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
2:memory:/ecs/55091c13-b8cf-4801-b527-f4601742204d/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
1:name=systemd:/ecs/34dc0b5e626f2c5c4c5170e34b10e765-1234567890
            """,
            "34dc0b5e626f2c5c4c5170e34b10e765-1234567890",
        ),
        # Linux non-containerized file
        (
            """
11:blkio:/user.slice/user-0.slice/session-14.scope
10:memory:/user.slice/user-0.slice/session-14.scope
9:hugetlb:/
8:cpuset:/
7:pids:/user.slice/user-0.slice/session-14.scope
6:freezer:/
5:net_cls,net_prio:/
4:perf_event:/
3:cpu,cpuacct:/user.slice/user-0.slice/session-14.scope
2:devices:/user.slice/user-0.slice/session-14.scope
1:name=systemd:/user.slice/user-0.slice/session-14.scope
            """,
            None,
        ),
    ),
)
def test_container_id_from_cgroup(file_contents, expected_container_id):
    with get_mock_open(read_data=file_contents) as mock_open:
        if file_contents is None:
            mock_open.side_effect = IOError

        with mock.patch("os.stat", mock.MagicMock(return_value=mock.Mock(st_ino=0xEFFFFFFB))):
            reader = Cgroup()
        assert expected_container_id == reader.container_id

        mock_open.assert_called_once_with("/proc/self/cgroup", mode="r")


def test_container_id_inode():
    """Test that the inode is returned when the container ID cannot be found."""
    with mock.patch("datadog.dogstatsd.container.open", mock.mock_open(read_data="0::/")) as mock_open:
        with mock.patch("os.stat", mock.MagicMock(return_value=mock.Mock(st_ino=1234))):
            reader = Cgroup()
        assert reader.container_id == "in-1234"
        mock_open.assert_called_once_with("/proc/self/cgroup", mode="r")

    cgroupv1_priority = """
12:cpu,cpuacct:/
11:hugetlb:/
10:devices:/
9:rdma:/
8:net_cls,net_prio:/
7:memory:/
6:cpuset:/
5:pids:/
4:freezer:/
3:perf_event:/
2:blkio:/
1:name=systemd:/
0::/
"""

    paths_checked = []

    def inode_stat_mock(path):
        paths_checked.append(path)

        # The cgroupv1 controller is mounted on inode 0. This will cause a fallback to the cgroupv2 controller.
        if path == "/sys/fs/cgroup/memory/":
            return mock.Mock(st_ino=0)
        elif path == "/sys/fs/cgroup/":
            return mock.Mock(st_ino=1234)

    with mock.patch("datadog.dogstatsd.container.open", mock.mock_open(read_data=cgroupv1_priority)) as mock_open:
        with mock.patch("os.stat", mock.MagicMock(side_effect=inode_stat_mock)):
            reader = Cgroup()
        assert reader.container_id == "in-1234"
        assert paths_checked[-2:] == [
            "/sys/fs/cgroup/memory/",
            "/sys/fs/cgroup/"
        ]
        mock_open.assert_called_once_with("/proc/self/cgroup", mode="r")
