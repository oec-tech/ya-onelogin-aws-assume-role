#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for merging the command-line options with onelogin.aws.json."""

import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import options  # noqa: E402


def _get_options(argv, config=None, yaml_path=None):
    with mock.patch.object(sys, 'argv', ['onelogin-aws-assume-role'] + argv), \
            mock.patch.object(options, 'get_config', return_value=config), \
            mock.patch.object(options, 'find_yaml_config', return_value=yaml_path):
        return options.get_options()


class KeychainOptionsTest(unittest.TestCase):
    def test_keychain_service_without_username_does_not_crash(self):
        opts = _get_options([], {'keychain_service': 'onelogin'})

        self.assertEqual(opts.keychain_service, 'onelogin')
        self.assertIsNone(opts.keychain_account)

    def test_keychain_account_defaults_to_the_username(self):
        opts = _get_options([], {'keychain_service': 'onelogin', 'username': 'jane@example.com'})

        self.assertEqual(opts.keychain_account, 'jane')

    def test_keychain_service_defaults_without_a_config_file(self):
        opts = _get_options(['--keychain-account', 'jane'])

        self.assertEqual(opts.keychain_service, 'onelogin')


class YamlConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir)

    def _write(self, content):
        path = os.path.join(self.tmp_dir, 'config.yaml')
        with open(path, 'w') as f:
            f.write(textwrap.dedent(content))
        return path

    def test_sets_every_option_by_its_command_line_name(self):
        path = self._write("""
            client_id: abc
            client_secret: shh
            region: eu
            onelogin-username: jane@example.com
            onelogin_subdomain: example
            onelogin_app_id: 123456
            aws_region: eu-west-1
            profile: my-profile
            file: ~/creds
            duration: 10000
            mfa_device: OneLogin Protect
            cache_saml: true
        """)

        opts = _get_options([], yaml_path=path)

        self.assertEqual((opts.client_id, opts.client_secret, opts.region), ('abc', 'shh', 'eu'))
        self.assertEqual((opts.username, opts.subdomain, opts.app_id), ('jane@example.com', 'example', '123456'))
        self.assertEqual((opts.aws_region, opts.profile_name, opts.duration), ('eu-west-1', 'my-profile', 10000))
        self.assertEqual(opts.file, os.path.expanduser('~/creds'))
        self.assertEqual(opts.mfa_device, 'OneLogin Protect')
        self.assertIs(opts.cache_saml, True)

    def test_precedence_is_command_line_then_profile_then_global(self):
        path = self._write("""
            aws_region: eu-west-1
            aws_account_id: "999"
            region: eu
            profiles:
              data:
                aws_account_id: "111"
                aws_role_name: DataEngineer
        """)

        opts = _get_options(['-p', 'data', '--aws-account-id', '222', '-r', 'us'], yaml_path=path)

        self.assertEqual(opts.aws_account_id, '222')
        self.assertEqual(opts.aws_role_name, 'DataEngineer')
        self.assertEqual(opts.aws_region, 'eu-west-1')
        # Given on the command line with the default value, still wins
        self.assertEqual(opts.region, 'us')

    def test_entries_can_write_to_the_same_aws_profile(self):
        path = self._write("""
            profiles:
              main:
                aws-account-id: "111"
                aws-profile: shared
              ai:
                aws-account-id: "222"
                aws-profile: shared
        """)

        opts = _get_options(['-p', 'ai'], yaml_path=path)

        self.assertEqual((opts.profile_name, opts.aws_account_id, opts.aws_profile), ('ai', '222', 'shared'))
        self.assertEqual(_get_options(['-p', 'ai', '--aws-profile', 'other'], yaml_path=path).aws_profile, 'other')

    def test_profile_from_the_config_selects_its_settings(self):
        path = self._write("""
            profile: data
            profiles:
              data:
                aws_role_name: DataEngineer
        """)

        self.assertEqual(_get_options([], yaml_path=path).aws_role_name, 'DataEngineer')

    def test_profile_in_yaml_wins_over_onelogin_aws_json(self):
        path = self._write("profile: data\n")

        self.assertEqual(_get_options([], {'profile': 'old'}, yaml_path=path).profile_name, 'data')

    def test_yaml_overrides_onelogin_aws_json(self):
        path = self._write("aws_region: eu-west-1\n")

        opts = _get_options([], {'aws_region': 'us-east-1', 'app_id': '5'}, yaml_path=path)

        self.assertEqual((opts.aws_region, opts.app_id), ('eu-west-1', '5'))

    def test_reads_account_labels(self):
        path = self._write("""
            accounts:
              123456789012: Data account
        """)

        self.assertEqual(_get_options([], yaml_path=path).account_aliases, {'123456789012': 'Data account'})

    def test_unknown_setting_is_an_error(self):
        path = self._write("aws_regoin: eu-west-1\n")

        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            _get_options([], yaml_path=path)
        self.assertIn("unknown setting 'aws_regoin'", stderr.getvalue())

    def test_duplicate_profile_names_are_an_error(self):
        path = self._write("""
            profiles:
              abcd:
                aws-role-name: MyRole
              abcd:
                aws-role-name: MyOtherRole
        """)

        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            _get_options([], yaml_path=path)
        self.assertIn("'abcd' appears twice (first on line 3)", stderr.getvalue())

    def test_wrong_type_is_an_error(self):
        path = self._write("duration: forever\n")

        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            _get_options([], yaml_path=path)

    def test_credential_process_ignores_file_and_loop_from_the_config(self):
        path = self._write("""
            file: ~/creds
            loop: 5
        """)

        opts = _get_options(['--credential-process'], yaml_path=path)

        self.assertIsNone(opts.file)
        self.assertEqual(opts.loop, 1)

    def test_credential_process_rejects_file_on_the_command_line(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            _get_options(['--credential-process', '-f', 'creds'])


class OverlayTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir)
        self.base = self._write('config.yaml', """
            onelogin-username: jane@example.com
            aws-region: eu-west-1
            duration: 3600
            profile: data
            profiles:
              data:
                aws-account-id: "111"
                aws-role-name: Reader
            accounts:
              "111": Data account
        """)
        self._write('config.accounta.yaml', """
            aws-region: us-east-1
            profiles:
              data:
                aws-role-name: Admin
            accounts:
              "222": Account A
        """)
        self._write('config.accountb.yml', """
            duration: 7200
        """)
        patcher = mock.patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write(self, name, content):
        path = os.path.join(self.tmp_dir, name)
        with open(path, 'w') as f:
            f.write(textwrap.dedent(content))
        return path

    def test_overlay_overrides_the_base(self):
        opts = _get_options(['-O', 'accounta'], yaml_path=self.base)

        self.assertEqual(opts.aws_region, 'us-east-1')
        self.assertEqual(opts.username, 'jane@example.com')
        # Profile settings merge key by key
        self.assertEqual((opts.aws_account_id, opts.aws_role_name), ('111', 'Admin'))
        self.assertEqual(opts.account_aliases, {'111': 'Data account', '222': 'Account A'})
        self.assertEqual(opts.config_files, [self.base, os.path.join(self.tmp_dir, 'config.accounta.yaml')])

    def test_command_line_overrides_the_overlay(self):
        opts = _get_options(['--overlay', 'accounta', '--aws-region', 'ap-south-1', '--aws-role-name', 'Dev'],
                            yaml_path=self.base)

        self.assertEqual((opts.aws_region, opts.aws_role_name), ('ap-south-1', 'Dev'))

    def test_overlays_stack_in_order(self):
        opts = _get_options(['-O', 'accounta,accountb'], yaml_path=self.base)

        self.assertEqual((opts.aws_region, opts.duration), ('us-east-1', 7200))
        self.assertEqual(opts.overlays, ['accounta', 'accountb'])

    def test_overlay_from_the_environment(self):
        with mock.patch.dict(os.environ, {options.OVERLAY_ENV_VAR: 'accountb'}):
            self.assertEqual(_get_options([], yaml_path=self.base).duration, 7200)

    def test_overlay_given_as_a_path(self):
        path = self._write('elsewhere.yaml', "aws-region: sa-east-1\n")

        self.assertEqual(_get_options(['-O', path], yaml_path=self.base).aws_region, 'sa-east-1')

    def test_missing_overlay_is_an_error(self):
        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            _get_options(['-O', 'nope'], yaml_path=self.base)
        self.assertIn("config overlay 'nope' not found", stderr.getvalue())

    def test_overlay_can_pick_the_profile(self):
        self._write('config.prod.yaml', """
            profile: prod
            profiles:
              prod:
                aws-account-id: "333"
        """)

        opts = _get_options(['-O', 'prod'], yaml_path=self.base)

        self.assertEqual((opts.profile_name, opts.aws_account_id), ('prod', '333'))


class FindYamlConfigTest(unittest.TestCase):
    def test_explicit_path_wins(self):
        with mock.patch.dict(os.environ, {options.CONFIG_ENV_VAR: 'env.yaml'}):
            self.assertEqual(options.find_yaml_config('mine.yaml', None), 'mine.yaml')

    def test_environment_variable(self):
        with mock.patch.dict(os.environ, {options.CONFIG_ENV_VAR: 'env.yaml'}):
            self.assertEqual(options.find_yaml_config(None, None), 'env.yaml')

    def test_config_file_path_folder(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        open(os.path.join(tmp_dir, 'config.yaml'), 'w').close()

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(options.find_yaml_config(None, tmp_dir), os.path.join(tmp_dir, 'config.yaml'))


class SavePasswordOptionTest(unittest.TestCase):
    def test_save_password_uses_the_default_keyring_service(self):
        opts = _get_options(['--save-password', '-u', 'jane@example.com'])

        self.assertEqual((opts.keychain_service, opts.keychain_account), ('onelogin', 'jane'))


if __name__ == '__main__':
    unittest.main()
