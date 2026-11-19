#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for --check-config."""

import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import check_config  # noqa: E402


def _options(**kwargs):
    values = dict(config='/cfg/config.yaml', overlay_paths=[], config_file_path=None, file=None,
                  client_id='id', client_secret='secret', password=None, keychain_service=None,
                  keychain_account=None, username='jane@example.com', region='us', subdomain='example',
                  app_id='123456', mfa_device=None, yaml_profiles={}, account_aliases=None,
                  selected_profile=None, aws_profile=None, profile_name=None, aws_account_id=None,
                  aws_role_name=None, aws_region='us-east-1', duration=3600)
    values.update(kwargs)
    return SimpleNamespace(**values)


class CheckProfilesTest(unittest.TestCase):
    def test_rows_and_shared_aws_profiles(self):
        rows, problems = check_config.check_profiles({
            'a': {'aws_account_id': '111111111111', 'aws_role_name': 'Admin', 'aws_profile': 'work'},
            'b': {'aws_account_id': '111111111111', 'aws_role_name': 'Dev', 'aws_profile': 'work'},
        }, {'111111111111': 'Data'})

        self.assertEqual(rows[0], ('a', '111111111111 (Data)', 'Admin', 'work'))
        self.assertEqual(problems, [('note', "Profiles 'a', 'b' all write the AWS profile [work]; the last login wins.")])

    def test_warns_about_an_account_id_that_lost_digits(self):
        _, problems = check_config.check_profiles({'a': {'aws_account_id': '12345678901', 'aws_role_name': 'X'}}, None)

        self.assertEqual(problems[0][0], 'warn')
        self.assertIn("isn't 12 digits", problems[0][1])

    def test_notes_partial_entries(self):
        _, problems = check_config.check_profiles({'a': {'aws_account_id': '111111111111'}}, None)

        self.assertIn('names only the account', problems[0][1])


class CheckConfigTest(unittest.TestCase):
    def _check(self, options, environ=None):
        keyring = mock.Mock(get_password=mock.Mock(return_value=None))
        with redirect_stdout(StringIO()) as out, mock.patch.object(check_config, 'find_sdk_file', return_value=None):
            code = check_config.check_config(options, environ or {}, keyring)
        return code, out.getvalue()

    def test_good_config(self):
        code, text = self._check(_options(profile_name='data', selected_profile='data',
                                          yaml_profiles={'data': {'aws_account_id': '111111111111'}}))

        self.assertEqual(code, 0)
        self.assertIn('data *', text)
        self.assertIn('profile [data]', text)
        self.assertIn('The config looks good', text)

    def test_missing_api_keys_fail(self):
        code, text = self._check(_options(client_id=None, client_secret=None))

        self.assertEqual(code, 1)
        self.assertIn('No OneLogin API client_id and client_secret', text)

    def test_reports_whether_the_password_is_saved(self):
        _, text = self._check(_options(keychain_service='onelogin'))

        self.assertIn("account 'jane': not saved yet", text)

    def test_unknown_profile_is_pointed_out(self):
        _, text = self._check(_options(profile_name='nope', selected_profile='nope'))

        self.assertIn("Profile 'nope' has no entry", text)


if __name__ == '__main__':
    unittest.main()
