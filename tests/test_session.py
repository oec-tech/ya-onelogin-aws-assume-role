#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for explaining credentials that expire earlier than requested."""

import base64
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aws_assume_role import session  # noqa: E402

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _saml_response(session_end):
    xml = ('<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
           'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"><saml:Assertion>'
           '<saml:AuthnStatement SessionNotOnOrAfter="%s"/></saml:Assertion></samlp:Response>'
           % session_end.strftime('%Y-%m-%dT%H:%M:%SZ'))
    return base64.b64encode(xml.encode('utf-8'))


class ExplainSessionLengthTest(unittest.TestCase):
    def test_nothing_to_explain_when_granted_in_full(self):
        expiration = NOW + timedelta(seconds=10000)

        self.assertIsNone(session.explain_session_length(10000, expiration, _saml_response(expiration), NOW))

    def test_names_the_onelogin_session_when_it_matches(self):
        expiration = NOW + timedelta(hours=1)

        message = session.explain_session_length(10000, expiration, _saml_response(expiration), NOW)

        self.assertIn('expire in 60 minutes', message)
        self.assertIn('SessionNotOnOrAfter', message)
        self.assertIn('--credential-process', message)

    def test_falls_back_to_the_role_limit(self):
        expiration = NOW + timedelta(hours=1)

        message = session.explain_session_length(10000, expiration, _saml_response(NOW + timedelta(hours=8)), NOW)

        self.assertNotIn('SessionNotOnOrAfter', message)
        self.assertIn('maximum session duration', message)


if __name__ == '__main__':
    unittest.main()
