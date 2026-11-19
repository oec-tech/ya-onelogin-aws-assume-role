#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for saving the OneLogin password in the system keyring."""

import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import aws_assume_role  # noqa: E402


def _options(**kwargs):
    values = dict(keychain_service='onelogin', keychain_account=None, save_password=False)
    values.update(kwargs)
    return SimpleNamespace(**values)


class SavePasswordToKeyringTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(aws_assume_role, 'keyring')
        self.keyring = patcher.start()
        self.addCleanup(patcher.stop)

    def _save(self, options, password, keyring_password, answer=None):
        with mock.patch.object(aws_assume_role.ui, 'confirm', return_value=answer == 'y') as ask, \
                redirect_stdout(StringIO()):
            aws_assume_role.save_password_to_keyring(options, 'jane@example.com', password, keyring_password)
        return ask

    def test_asks_before_saving_a_typed_password(self):
        ask = self._save(_options(), 'pw', None, answer='y')

        ask.assert_called_once()
        self.keyring.set_password.assert_called_once_with('onelogin', 'jane', 'pw')

    def test_does_not_save_when_declined(self):
        self._save(_options(), 'pw', None, answer='n')

        self.keyring.set_password.assert_not_called()

    def test_save_password_saves_without_asking(self):
        ask = self._save(_options(save_password=True, keychain_account='me'), 'pw', None)

        ask.assert_not_called()
        self.keyring.set_password.assert_called_once_with('onelogin', 'me', 'pw')

    def test_updates_a_wrong_saved_password(self):
        ask = self._save(_options(), 'new', 'old')

        ask.assert_not_called()
        self.keyring.set_password.assert_called_once_with('onelogin', 'jane', 'new')

    def test_leaves_a_correct_saved_password_alone(self):
        self._save(_options(), 'pw', 'pw')

        self.keyring.set_password.assert_not_called()

    def test_does_nothing_without_a_keyring_service(self):
        self._save(_options(keychain_service=None), 'pw', None)

        self.keyring.set_password.assert_not_called()


if __name__ == '__main__':
    unittest.main()
