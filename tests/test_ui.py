#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for the role picker's filtering and the plain-text fallbacks of
the terminal output and prompts."""

import os
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import aws_assume_role, prompts, ui  # noqa: E402


def _role(account, name):
    return 'arn:aws:iam::%s:role/%s,arn:aws:iam::%s:saml-provider/OneLogin' % (account, name, account)


ROLES = [_role('111111111111', 'Admin'), _role('111111111111', 'ReadOnly'),
         _role('222222222222', 'Admin'), _role('333333333333', 'Dev')]
LABELS = ['a', 'b', 'c', 'd']


def _options(account=None, role=None):
    return SimpleNamespace(aws_account_id=account, aws_role_name=role)


class RelatedRolesTest(unittest.TestCase):
    def test_nothing_set_means_no_filter(self):
        self.assertEqual(aws_assume_role.related_roles(ROLES, _options()), [])

    def test_matches_the_account(self):
        self.assertEqual(aws_assume_role.related_roles(ROLES, _options(account='111111111111')), [0, 1])

    def test_matches_the_role_name(self):
        self.assertEqual(aws_assume_role.related_roles(ROLES, _options(role='Admin')), [0, 2])

    def test_matches_either(self):
        self.assertEqual(aws_assume_role.related_roles(ROLES, _options('333333333333', 'Admin')), [0, 2, 3])


class MatchingTest(unittest.TestCase):
    def test_role_names_ignore_case(self):
        self.assertEqual(aws_assume_role.related_roles(ROLES, _options(role='dev')), [3])

    def test_account_ids_written_as_numbers_keep_leading_zeros(self):
        from aws_assume_role.accounts import same_account
        self.assertTrue(same_account('012345678901', 12345678901))
        self.assertTrue(same_account('012345678901', '0123-4567-8901'))
        self.assertFalse(same_account('012345678901', None))


class PickRoleTest(unittest.TestCase):
    def _pick(self, options, answers, last_index=None):
        with mock.patch.object(aws_assume_role, 'select_option', side_effect=answers) as select:
            return aws_assume_role.pick_role(ROLES, LABELS, options, last_index), select

    def test_shows_only_related_roles_first(self):
        picked, select = self._pick(_options(account='111111111111'), [1])

        self.assertEqual(picked, 1)
        select.assert_called_once_with('Select the AWS role', ['a', 'b', 'Show all 4 roles...'], 0)

    def test_starts_on_the_last_role_when_it_is_related(self):
        _, select = self._pick(_options(account='111111111111'), [0], last_index=1)

        self.assertEqual(select.call_args[0][2], 1)

    def test_show_all_opens_the_full_list(self):
        picked, select = self._pick(_options(role='Dev'), [1, 2], last_index=0)

        self.assertEqual(picked, 2)
        self.assertEqual(select.call_args_list[1][0], ('Select the AWS role (all roles)', LABELS, 0))

    def test_full_list_without_settings(self):
        picked, select = self._pick(_options(), [3], last_index=2)

        self.assertEqual(picked, 3)
        select.assert_called_once_with('Select the AWS role', LABELS, 2)


class CredentialRowsTest(unittest.TestCase):
    def test_describes_role_account_expiry_and_region(self):
        expiration = datetime.now(timezone.utc) + timedelta(minutes=90, seconds=30)
        token = {'AssumedRoleUser': {'Arn': 'arn:aws:sts::111111111111:assumed-role/Admin/jane'},
                 'Credentials': {'Expiration': expiration}}

        rows = dict(aws_assume_role.credential_rows(token, 'us-east-1'))

        self.assertEqual(rows['Role'], 'Admin')
        self.assertEqual(rows['Account'], '111111111111')
        self.assertIn('(in 1h 30m)', rows['Expires'])
        self.assertEqual(rows['Region'], 'us-east-1')

    def test_short_sessions_show_minutes(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.assertIn('(in 15m)', aws_assume_role.describe_expiration(now + timedelta(minutes=15), now))


class PlainFallbackTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(prompts, 'menus_available', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ask_text_uses_the_default_for_an_empty_answer(self):
        with mock.patch('sys.stdin', StringIO('\n')), redirect_stdout(StringIO()) as out:
            self.assertEqual(ui.ask_text('AWS region', 'us-east-1'), 'us-east-1')
        self.assertIn('AWS region (us-east-1):', out.getvalue())

    def test_confirm_reads_y_or_n(self):
        with mock.patch('sys.stdin', StringIO('maybe\nn\n')), redirect_stdout(StringIO()):
            self.assertFalse(ui.confirm('Save it?'))

    def test_status_lines_are_plain_text_when_not_a_terminal(self):
        with redirect_stdout(StringIO()) as out:
            ui.ok('Logged in [to OneLogin]')
            ui.summary('AWS credentials ready', [('Role', 'Admin'), ('Region', None)])
            with ui.waiting('Waiting...'):
                pass
        text = out.getvalue()
        self.assertIn('Logged in [to OneLogin]', text)
        self.assertIn('Admin', text)
        self.assertNotIn('Region', text)
        self.assertNotIn('\x1b[', text)


if __name__ == '__main__':
    unittest.main()
