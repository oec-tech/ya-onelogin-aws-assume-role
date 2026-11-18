#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for the steps of assume_role: picking the role and region, and
printing or saving the credentials."""

import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import aws_assume_role  # noqa: E402

ADMIN = 'arn:aws:iam::111111111111:role/Admin,arn:aws:iam::111111111111:saml-provider/OneLogin'
DEV = 'arn:aws:iam::222222222222:role/Dev,arn:aws:iam::222222222222:saml-provider/OneLogin'
TOKEN = {
    'Credentials': {'AccessKeyId': 'AKIA', 'SecretAccessKey': 'secret', 'SessionToken': 'token',
                    'Expiration': datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)},
    'AssumedRoleUser': {'Arn': 'arn:aws:sts::111111111111:assumed-role/Admin/jane'},
}


def _options(**kwargs):
    values = dict(role_order=False, aws_account_id=None, aws_role_name=None, config_file_path=None,
                  account_aliases=None, aws_region=None)
    values.update(kwargs)
    return SimpleNamespace(**values)


class IndexRolesTest(unittest.TestCase):
    def test_indexes_by_account_and_by_role(self):
        by_account, by_role = aws_assume_role.index_roles([ADMIN, DEV], role_order=True)

        self.assertEqual(by_account, {'111111111111': {'Admin': ADMIN}, '222222222222': {'Dev': DEV}})
        self.assertEqual(by_role, {'Admin': {'111111111111': ADMIN}, 'Dev': {'222222222222': DEV}})


class ChooseRoleTest(unittest.TestCase):
    def _choose(self, roles, options, answer=None):
        with mock.patch.object(aws_assume_role, 'select_option', return_value=answer) as select, \
                mock.patch.object(aws_assume_role, 'get_last_choice', return_value=DEV), \
                mock.patch.object(aws_assume_role, 'save_last_choice') as save, \
                mock.patch('aws_assume_role.accounts.get_account_aliases_info', return_value=[]), \
                redirect_stdout(StringIO()):
            return aws_assume_role.choose_role(roles, options, 'sub', 'jane', '1'), select, save

    def test_single_role_is_selected(self):
        role, select, _ = self._choose([ADMIN], _options())

        self.assertEqual(role, ADMIN)
        select.assert_not_called()

    def test_no_usable_role(self):
        self.assertIsNone(self._choose([], _options())[0])
        self.assertIsNone(self._choose(['Default,'], _options())[0])

    def test_configured_role_is_selected_without_asking(self):
        role, select, _ = self._choose([ADMIN, DEV], _options(aws_account_id='222222222222', aws_role_name='Dev'))

        self.assertEqual(role, DEV)
        select.assert_not_called()

    def test_menu_starts_on_the_last_role_and_remembers_the_pick(self):
        role, select, save = self._choose([ADMIN, DEV], _options(), answer=0)

        self.assertEqual(role, ADMIN)
        self.assertEqual(select.call_args.args[2], 1)
        save.assert_called_once_with('sub', 'jane', '1', 'role', ADMIN)


class GetAwsRegionTest(unittest.TestCase):
    def _ask(self, answer, env=None):
        with mock.patch.dict(os.environ, env or {}, clear=True), \
                mock.patch('sys.stdin', StringIO(answer + '\n')), redirect_stdout(StringIO()):
            return aws_assume_role.get_aws_region(_options())

    def test_configured_region_is_used(self):
        self.assertEqual(aws_assume_role.get_aws_region(_options(aws_region='eu-west-1')), 'eu-west-1')

    def test_empty_answer_uses_the_environment(self):
        self.assertEqual(self._ask('', {'AWS_DEFAULT_REGION': 'eu-central-1'}), 'eu-central-1')

    def test_empty_answer_without_environment(self):
        self.assertEqual(self._ask(''), 'us-west-2')

    def test_typed_region(self):
        self.assertEqual(self._ask('ap-south-1'), 'ap-south-1')


class FormatCredentialsTest(unittest.TestCase):
    def test_export(self):
        text = aws_assume_role.format_credentials(TOKEN, 'eu-west-1', 'export')

        self.assertIn('export AWS_ACCESS_KEY_ID=AKIA', text)
        self.assertIn('export AWS_REGION=eu-west-1', text)

    def test_cmd(self):
        self.assertIn('set AWS_SESSION_TOKEN=token', aws_assume_role.format_credentials(TOKEN, 'eu-west-1', 'cmd'))

    def test_powershell(self):
        self.assertIn('$env:AWS_SECRET_ACCESS_KEY="secret"',
                      aws_assume_role.format_credentials(TOKEN, 'eu-west-1', 'powershell'))

    def test_json(self):
        values = json.loads(aws_assume_role.format_credentials(TOKEN, 'eu-west-1', 'json'))

        self.assertEqual(values['AWS_ACCESS_KEY_ID'], 'AKIA')
        self.assertEqual(values['AWS_SESSION_EXPIRATION'], '2026-01-01T12:00:00+0000')

    def test_json_is_printed_alone(self):
        out = StringIO()
        with redirect_stdout(out):
            aws_assume_role.print_credentials(TOKEN, 'eu-west-1', 'json')

        self.assertEqual(json.loads(out.getvalue())['AWS_REGION'], 'eu-west-1')


class SaveCredentialsTest(unittest.TestCase):
    def test_writes_the_profile(self):
        writer = mock.Mock()

        aws_assume_role.save_credentials(writer, '/creds', 'dev', TOKEN, 'eu-west-1')

        values, path = writer.update_config.call_args.args
        self.assertEqual(path, '/creds')
        self.assertEqual(values['__section__'], 'dev')
        self.assertEqual(values['aws_access_key_id'], 'AKIA')
        self.assertEqual(values['region'], 'eu-west-1')


if __name__ == '__main__':
    unittest.main()
