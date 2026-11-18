#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for the role/MFA menus and remembering the last choice."""

import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import accounts, last_choices, prompts  # noqa: E402


class SelectOptionTest(unittest.TestCase):
    def test_single_option_needs_no_question(self):
        self.assertEqual(prompts.select_option('Pick', ['only']), 0)

    def test_numbered_list_without_a_terminal(self):
        out = StringIO()
        with mock.patch.object(prompts, 'menus_available', return_value=False), \
                mock.patch('sys.stdin', StringIO('5\n1\n')), redirect_stdout(out):
            self.assertEqual(prompts.select_option('Pick a role', ['a', 'b'], default=0), 1)
        self.assertIn(' 1 | b', out.getvalue())
        self.assertIn('Pick a role [0-1] (last time: 0)', out.getvalue())

    def test_menu_starts_on_the_default(self):
        with mock.patch.object(prompts, 'menus_available', return_value=True), \
                mock.patch('questionary.select') as select:
            select.return_value.ask.return_value = 2
            self.assertEqual(prompts.select_option('Pick', ['a', 'b', 'c'], default=1), 2)
        self.assertEqual(select.call_args.kwargs['default'].value, 1)
        self.assertTrue(select.call_args.kwargs['use_search_filter'])

    def test_falls_back_when_the_menu_fails(self):
        with mock.patch.object(prompts, 'menus_available', return_value=True), \
                mock.patch('questionary.select', side_effect=Exception('no console')), \
                mock.patch('sys.stdin', StringIO('0\n')), redirect_stdout(StringIO()):
            self.assertEqual(prompts.select_option('Pick', ['a', 'b']), 0)

    def test_no_menu_option_disables_menus(self):
        with mock.patch.object(prompts, 'use_menus', False):
            self.assertFalse(prompts.menus_available())


class LastChoicesTest(unittest.TestCase):
    def setUp(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        patcher = mock.patch.object(last_choices, 'LAST_CHOICES_PATH', os.path.join(tmp_dir, 'sub', 'last.json'))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_remembers_per_user_and_app(self):
        last_choices.save_last_choice('example', 'jane', '1', 'role', 'arn:role')

        self.assertEqual(last_choices.get_last_choice('example', 'jane', '1', 'role'), 'arn:role')
        self.assertIsNone(last_choices.get_last_choice('example', 'jane', '2', 'role'))
        self.assertIsNone(last_choices.get_last_choice('example', 'jane', '1', 'mfa_device'))

    def test_unreadable_file_is_ignored(self):
        os.makedirs(os.path.dirname(last_choices.LAST_CHOICES_PATH))
        with open(last_choices.LAST_CHOICES_PATH, 'w') as f:
            f.write('not json')

        self.assertIsNone(last_choices.get_last_choice('example', 'jane', '1', 'role'))


class RoleChoicesTest(unittest.TestCase):
    def test_labels_include_account_aliases(self):
        by_account = {'111': {'Admin': 'arn:111:Admin'}, '222': {'Dev': 'arn:222:Dev'}}
        options = SimpleNamespace(config_file_path=None, account_aliases={'111': 'Data account'},
                                  aws_account_id='222', aws_role_name='Dev')

        with mock.patch.object(accounts, 'get_account_aliases_info', return_value=[]):
            selection, labels, chosen = accounts.process_account_and_role_choices(by_account, {}, options)

        self.assertEqual(selection, ['arn:111:Admin', 'arn:222:Dev'])
        self.assertEqual(labels, ['Admin (Account: 111 - Data account)', 'Dev (Account: 222 - Unidentified) **'])
        self.assertEqual(chosen, 1)


if __name__ == '__main__':
    unittest.main()
