#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for --init-profiles: naming the profiles, looking up account
aliases, and writing the generated block into config.yaml."""

import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import init_profiles, options as options_module  # noqa: E402


def _role(account, name):
    return 'arn:aws:iam::%s:role/%s,arn:aws:iam::%s:saml-provider/OneLogin' % (account, name, account)


ROLES = [_role('011111111111', 'Admin'), _role('011111111111', 'ReadOnly'), _role('222222222222', 'Dev_Team')]


class FakeSts:
    def __init__(self, denied=()):
        self.denied = denied
        self.calls = []

    def assume_role_with_saml(self, RoleArn, **kwargs):
        self.calls.append(RoleArn)
        if RoleArn in self.denied:
            raise Exception("AccessDenied")
        return {'Credentials': {'AccessKeyId': RoleArn}}


def _iam_factory(aliases):
    def factory(credentials):
        account = credentials['AccessKeyId'].split(':')[4]
        return SimpleNamespace(list_account_aliases=lambda: {'AccountAliases': aliases.get(account, [])})
    return factory


class LookupTest(unittest.TestCase):
    def test_reads_the_alias_once_per_account(self):
        sts = FakeSts()
        names = init_profiles.lookup_account_names(ROLES, 'saml', 'us-east-1', sts,
                                                   _iam_factory({'011111111111': ['acme-prod']}))

        self.assertEqual(names, {'011111111111': 'acme-prod'})
        self.assertEqual(len(sts.calls), 2)

    def test_tries_the_next_role_when_one_is_denied(self):
        sts = FakeSts(denied={ROLES[0].split(',')[0]})
        names = init_profiles.lookup_account_names(ROLES[:2], 'saml', 'us-east-1', sts,
                                                   _iam_factory({'011111111111': ['acme-prod']}))

        self.assertEqual(names, {'011111111111': 'acme-prod'})


class GenerateTest(unittest.TestCase):
    def test_names_profiles_after_the_alias_or_the_account_id(self):
        block = init_profiles.generate(ROLES, {'011111111111': 'Acme Prod'})

        self.assertEqual(list(block['profiles']), ['acme-prod-admin', 'acme-prod-readonly', '222222222222-dev-team'])
        self.assertEqual(block['profiles']['acme-prod-admin'],
                         {'aws-account-id': '011111111111', 'aws-role-name': 'Admin'})
        self.assertEqual(block['accounts'], {'011111111111': 'Acme Prod'})

    def test_keeps_names_unique(self):
        block = init_profiles.generate([_role('1', 'a-b'), _role('1', 'a_b')], {})
        self.assertEqual(list(block['profiles']), ['1-a-b', '1-a-b-2'])


class WriteBlockTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, 'config.yaml')

    def _write(self, names):
        init_profiles.write_block(self.path, init_profiles.render_block(init_profiles.generate(ROLES, names)))
        with open(self.path) as f:
            return f.read()

    def test_appends_and_then_replaces_the_block_keeping_the_rest(self):
        with open(self.path, 'w') as f:
            f.write("username: jane\nprofiles:\n  mine:\n    aws-role-name: Admin\n")

        self._write({})
        text = self._write({'011111111111': 'acme-prod'})

        self.assertTrue(text.startswith("username: jane\nprofiles:\n  mine:"))
        self.assertEqual(text.count(init_profiles.BEGIN_MARKER), 1)
        self.assertIn("acme-prod-admin:", text)
        self.assertNotIn("011111111111-admin:", text)
        self.assertIn('aws-account-id: "011111111111"', text)

    def test_creates_the_file(self):
        self.path = os.path.join(self.folder, 'new', 'config.yaml')
        self.assertIn("generated:", self._write({}))

    def test_own_entries_win_over_the_generated_ones(self):
        with open(self.path, 'w') as f:
            f.write("accounts:\n  '011111111111': My name\n"
                    "profiles:\n  acme-prod-admin:\n    duration: 7200\n")
        self._write({'011111111111': 'acme-prod'})

        with mock.patch.dict(os.environ, {}, clear=False):
            options = options_module.get_options(['--config', self.path, '-p', 'acme-prod-admin'])

        self.assertEqual(options.account_aliases['011111111111'], 'My name')
        self.assertEqual(options.aws_account_id, '011111111111')
        self.assertEqual(options.aws_role_name, 'Admin')
        self.assertEqual(options.duration, 7200)
        self.assertEqual(options.generated_profiles, {'acme-prod-readonly', '222222222222-dev-team'})
        self.assertEqual(options.own_account_names, {'011111111111': 'My name'})


class InitProfilesTest(unittest.TestCase):
    def test_writes_and_reports(self):
        path = os.path.join(tempfile.mkdtemp(), 'config.yaml')
        options = SimpleNamespace(config=path, yaml_profiles={'acme-prod-admin': {}}, generated_profiles=set())
        with mock.patch.object(init_profiles, 'lookup_account_names', return_value={'011111111111': 'acme-prod'}), \
                redirect_stdout(StringIO()) as out:
            init_profiles.init_profiles(ROLES + [''], 'saml', options, 'us-east-1')

        text = out.getvalue()
        self.assertIn('acme-prod-admin (+ your settings)', text)
        self.assertIn('No account name for 222222222222', text)
        self.assertIn('Wrote 3 profiles', text)
        self.assertTrue(os.path.isfile(path))

    def test_your_account_names_win_in_the_profile_names(self):
        path = os.path.join(tempfile.mkdtemp(), 'config.yaml')
        options = SimpleNamespace(config=path, own_account_names={'222222222222': 'Sandbox'})
        with mock.patch.object(init_profiles, 'lookup_account_names', return_value={'222222222222': 'alias'}), \
                redirect_stdout(StringIO()) as out:
            init_profiles.init_profiles(ROLES, 'saml', options, 'us-east-1')

        with open(path) as f:
            text = f.read()
        self.assertIn('sandbox-dev-team:', text)
        self.assertIn('"222222222222": alias', text)
        self.assertIn('No account name for 011111111111', out.getvalue())


if __name__ == '__main__':
    unittest.main()
