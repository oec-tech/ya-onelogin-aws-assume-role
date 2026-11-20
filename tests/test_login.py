#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for picking the MFA device and waiting for a push approval."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import login  # noqa: E402
from aws_assume_role.onelogin_client import Device, SAMLEndpointResponse  # noqa: E402

DEVICES = [
    Device({'device_id': 1, 'auth_factor_name': 'Google Authenticator'}),
    Device({'device_id': 2, 'auth_factor_name': 'OneLogin Protect', 'user_display_name': 'Pixel'}),
]


class FindDeviceTest(unittest.TestCase):
    def test_matches_the_name_ignoring_case(self):
        self.assertEqual(login.find_device(DEVICES, 'onelogin protect'), 1)

    def test_matches_the_id(self):
        self.assertEqual(login.find_device(DEVICES, '1'), 0)

    def test_matches_part_of_the_label(self):
        self.assertEqual(login.find_device(DEVICES, 'pixel'), 1)

    def test_no_match(self):
        self.assertIsNone(login.find_device(DEVICES, 'YubiKey'))


def _response(status_type):
    return SAMLEndpointResponse(status_type, status_type)


class WaitForPushTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(login.time, 'sleep')
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = mock.Mock(error=None)

    def test_polls_at_the_interval_until_approved(self):
        self.client.get_saml_assertion_verifying.side_effect = [_response('pending'), _response('success')]

        result = login.wait_for_push(self.client, 1, 2, 'state', _response('pending'), 3)

        self.assertEqual(result.type, 'success')
        self.assertEqual(self.sleep.call_args_list, [mock.call(3), mock.call(3)])

    def test_backs_off_while_rate_limited(self):
        def verify(*args, **kwargs):
            if verify.calls < 2:
                verify.calls += 1
                self.client.error = '429'
                return None
            self.client.error = None
            return _response('success')
        verify.calls = 0
        self.client.get_saml_assertion_verifying.side_effect = verify

        result = login.wait_for_push(self.client, 1, 2, 'state', _response('pending'), 3)

        self.assertEqual(result.type, 'success')
        self.assertEqual(self.sleep.call_args_list, [mock.call(3), mock.call(6), mock.call(12)])

    def test_stops_on_another_error(self):
        self.client.error = '400'

        self.assertIsNone(login.wait_for_push(self.client, 1, 2, 'state', None, 3))
        self.sleep.assert_not_called()

    def _verify_with_errors(self, errors):
        def verify(*args, **kwargs):
            if verify.errors:
                error = verify.errors.pop(0)
                if isinstance(error, Exception):
                    raise error
                self.client.error = error
                return None
            self.client.error = None
            return _response('success')
        verify.errors = list(errors)
        return verify

    def test_keeps_checking_through_network_and_server_errors(self):
        self.client.get_saml_assertion_verifying.side_effect = self._verify_with_errors(
            [ConnectionError("reset"), '502', '503'])

        result = login.wait_for_push(self.client, 1, 2, 'state', _response('pending'), 3)

        self.assertEqual(result.type, 'success')
        self.assertEqual(self.sleep.call_count, 4)

    def test_renews_an_expired_api_token(self):
        self.client.get_saml_assertion_verifying.side_effect = self._verify_with_errors(['401'])

        result = login.wait_for_push(self.client, 1, 2, 'state', _response('pending'), 3)

        self.assertEqual(result.type, 'success')
        self.client.get_access_token.assert_called_once_with()

    def test_stops_when_asked(self):
        import threading
        stop = threading.Event()
        stop.set()

        result = login.wait_for_push(self.client, 1, 2, 'state', _response('pending'), 3, stop)

        self.assertEqual(result.type, 'pending')
        self.client.get_saml_assertion_verifying.assert_not_called()

    def test_without_a_terminal_only_waits_for_the_push(self):
        self.client.get_saml_assertion_verifying.side_effect = [_response('success')]
        with mock.patch.object(login.prompts, 'menus_available', return_value=False), \
                mock.patch('sys.stdout', new_callable=lambda: __import__('io').StringIO()):
            pushed, code = login.wait_for_push_or_code(self.client, 1, 2, 'state', _response('pending'), 3)

        self.assertEqual((pushed.type, code), ('success', None))

    def test_gives_up_after_the_timeout(self):
        self.client.get_saml_assertion_verifying.return_value = _response('pending')

        with mock.patch.object(login.time, 'monotonic', side_effect=[0, 0, 50, login.PUSH_TIMEOUT]):
            result = login.wait_for_push(self.client, 1, 2, 'state', _response('pending'), 3)

        self.assertEqual(result.type, 'pending')


if __name__ == '__main__':
    unittest.main()
