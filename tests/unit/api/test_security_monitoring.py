# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Tests for Security Monitoring API endpoints.
"""

import unittest

from datadog.api.security_monitoring_rules import SecurityMonitoringRule
from datadog.api.security_monitoring_signals import SecurityMonitoringSignal

# We'll implement proper testing in a follow-up PR
class TestSecurityMonitoring(unittest.TestCase):
    """
    Simple tests that classes exist
    """
    
    def test_classes_exist(self):
        """Test that our classes are defined correctly"""
        self.assertEqual(SecurityMonitoringRule._resource_name, "security_monitoring/rules")
        self.assertEqual(SecurityMonitoringRule._api_version, "v2")
        
        self.assertEqual(SecurityMonitoringSignal._resource_name, "security_monitoring/signals")
        self.assertEqual(SecurityMonitoringSignal._api_version, "v2")


if __name__ == "__main__":
    unittest.main()