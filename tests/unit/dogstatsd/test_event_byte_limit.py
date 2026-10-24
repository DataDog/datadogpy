# -*- coding: utf-8 -*-
# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""Event size validation must use the encoded packet size."""

import os

import pytest
from mock import patch

from datadog.dogstatsd import DogStatsd


@pytest.mark.parametrize("field", ["title", "message", "tags"])
def test_event_rejects_oversized_unicode_packet(field):
    """Multibyte content must not bypass the event protocol's byte limit."""
    kwargs = {"title": u"x", "message": u"y"}
    kwargs[field] = [u"\u00e9" * 4096] if field == "tags" else u"\u00e9" * 4096
    with patch.dict(os.environ, {}, clear=True):
        client = DogStatsd(disable_telemetry=True)
    with patch.object(client, "_send") as send:
        with pytest.raises(ValueError, match="payload is too big"):
            client.event(**kwargs)
        send.assert_not_called()


@pytest.mark.parametrize("message", [u"a" * 8179, u"\u00e9" * 4089 + u"a"])
def test_event_accepts_packet_at_byte_limit(message):
    """ASCII and multibyte payloads keep the existing inclusive 8192-byte boundary."""
    with patch.dict(os.environ, {}, clear=True):
        client = DogStatsd(disable_telemetry=True)
    with patch.object(client, "_send") as send:
        client.event(u"x", message)
        send.assert_called_once()
        packet = send.call_args[0][0]
        assert len(packet.encode("utf-8")) == 8192
