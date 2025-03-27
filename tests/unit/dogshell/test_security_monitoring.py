# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Tests for Security Monitoring dogshell commands.
"""

import json
import os
import tempfile
import unittest

import mock

from datadog.dogshell.security_monitoring import SecurityMonitoringClient

class TestSecurityMonitoringCommands(unittest.TestCase):
    """
    Test class for Security Monitoring dogshell commands.
    """

    def setUp(self):
        """
        Setup common mocks.
        """
        self.rule_get_all_mock = mock.patch('datadog.api.security_monitoring_rules.SecurityMonitoringRule.get_all')
        self.rule_get_mock = mock.patch('datadog.api.security_monitoring_rules.SecurityMonitoringRule.get')
        self.rule_create_mock = mock.patch('datadog.api.security_monitoring_rules.SecurityMonitoringRule.create')
        self.rule_update_mock = mock.patch('datadog.api.security_monitoring_rules.SecurityMonitoringRule.update')
        self.rule_delete_mock = mock.patch('datadog.api.security_monitoring_rules.SecurityMonitoringRule.delete')
        
        self.signal_get_all_mock = mock.patch('datadog.api.security_monitoring_signals.SecurityMonitoringSignal.get_all')
        self.signal_get_mock = mock.patch('datadog.api.security_monitoring_signals.SecurityMonitoringSignal.get')
        self.signal_change_triage_state_mock = mock.patch('datadog.api.security_monitoring_signals.SecurityMonitoringSignal.change_triage_state')
        
        self.rule_get_all = self.rule_get_all_mock.start()
        self.rule_get = self.rule_get_mock.start()
        self.rule_create = self.rule_create_mock.start()
        self.rule_update = self.rule_update_mock.start()
        self.rule_delete = self.rule_delete_mock.start()
        
        self.signal_get_all = self.signal_get_all_mock.start()
        self.signal_get = self.signal_get_mock.start()
        self.signal_change_triage_state = self.signal_change_triage_state_mock.start()
        
    def tearDown(self):
        """
        Reset mocks.
        """
        self.rule_get_all_mock.stop()
        self.rule_get_mock.stop()
        self.rule_create_mock.stop()
        self.rule_update_mock.stop()
        self.rule_delete_mock.stop()
        
        self.signal_get_all_mock.stop()
        self.signal_get_mock.stop()
        self.signal_change_triage_state_mock.stop()
    
    def test_rules_list(self):
        """
        Test 'security-monitoring rules list' command.
        """
        expected_response = {'rules': [{'id': 'abc-123'}]}
        self.rule_get_all.return_value = expected_response
        
        args = mock.MagicMock()
        args.page_size = 10
        args.page_number = 1
        args.timeout = None

        response = SecurityMonitoringClient._show_all_rules(args)
        self.rule_get_all.assert_called_once_with(
            **{
                'page[size]': 10,
                'page[number]': 1
            })
        self.assertEqual(response, 0)  # Expect success code
    
    def test_rules_get(self):
        """
        Test 'security-monitoring rules get' command.
        """
        rule_id = 'abc-123'
        expected_response = {'id': rule_id}
        self.rule_get.return_value = expected_response
        
        args = mock.MagicMock()
        args.rule_id = rule_id
        args.timeout = None
        
        response = SecurityMonitoringClient._show_rule(args)
        self.rule_get.assert_called_once_with(rule_id)
        self.assertEqual(response, 0)  # Expect success code
    
    def test_rules_create(self):
        """
        Test 'security-monitoring rules create' command.
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        try:
            rule_data = {
                'name': 'Test rule',
                'is_enabled': True
            }
            json.dump(rule_data, temp_file)
            temp_file.close()
            
            expected_response = {'id': 'new-rule-id'}
            self.rule_create.return_value = expected_response
            
            args = mock.MagicMock()
            args.file = temp_file.name
            args.timeout = None
            
            response = SecurityMonitoringClient._create_rule(args)
            self.rule_create.assert_called_once_with(**rule_data)
            self.assertEqual(response, 0)  # Expect success code
        finally:
            os.unlink(temp_file.name)
    
    def test_rules_update(self):
        """
        Test 'security-monitoring rules update' command.
        """
        rule_id = 'abc-123'
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        try:
            rule_data = {
                'name': 'Updated rule',
                'is_enabled': False
            }
            json.dump(rule_data, temp_file)
            temp_file.close()
            
            expected_response = {'id': rule_id}
            self.rule_update.return_value = expected_response
            
            args = mock.MagicMock()
            args.rule_id = rule_id
            args.file = temp_file.name
            args.timeout = None
            
            response = SecurityMonitoringClient._update_rule(args)
            self.rule_update.assert_called_once_with(rule_id, **rule_data)
            self.assertEqual(response, 0)  # Expect success code
        finally:
            os.unlink(temp_file.name)
    
    def test_rules_delete(self):
        """
        Test 'security-monitoring rules delete' command.
        """
        rule_id = 'abc-123'
        expected_response = {'deleted': rule_id}
        self.rule_delete.return_value = expected_response
        
        args = mock.MagicMock()
        args.rule_id = rule_id
        args.timeout = None
        
        response = SecurityMonitoringClient._delete_rule(args)
        self.rule_delete.assert_called_once_with(rule_id)
        self.assertEqual(response, 0)  # Expect success code
    
    def test_signals_list(self):
        """
        Test 'security-monitoring signals list' command.
        """
        expected_response = {'signals': [{'id': 'sig-123'}]}
        self.signal_get_all.return_value = expected_response
        
        args = mock.MagicMock()
        args.query = 'security:attack'
        args.from_time = 'now-1h'
        args.to_time = 'now'
        args.sort = '-timestamp'
        args.page_size = 10
        args.page_cursor = None
        args.timeout = None
        
        response = SecurityMonitoringClient._list_signals(args)
        self.signal_get_all.assert_called_once_with(
            **{
                'filter[query]': 'security:attack',
                'filter[from]': 'now-1h',
                'filter[to]': 'now',
                'sort': '-timestamp',
                'page[size]': 10
            }
        )
        self.assertEqual(response, 0)  # Expect success code
    
    def test_signals_get(self):
        """
        Test 'security-monitoring signals get' command.
        """
        signal_id = 'sig-123'
        expected_response = {'id': signal_id}
        self.signal_get.return_value = expected_response
        
        args = mock.MagicMock()
        args.signal_id = signal_id
        args.timeout = None
        
        response = SecurityMonitoringClient._get_signal(args)
        self.signal_get.assert_called_once_with(signal_id)
        self.assertEqual(response, 0)  # Expect success code
    
    def test_signals_change_triage_state(self):
        """
        Test 'security-monitoring signals triage' command.
        """
        signal_id = 'sig-123'
        state = 'archived'
        expected_response = {'status': 'success'}
        self.signal_change_triage_state.return_value = expected_response
        
        args = mock.MagicMock()
        args.signal_id = 'sig-123'
        args.state = state
        args.timeout = None
        
        response = SecurityMonitoringClient._change_triage_state(args)
        self.signal_change_triage_state.assert_called_once_with(signal_id, state)
        self.assertEqual(response, 0)  # Expect success code


if __name__ == "__main__":
    unittest.main()