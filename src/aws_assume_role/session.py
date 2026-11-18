"""
Explains why AWS granted shorter credentials than --duration asked for.
"""

import base64

from datetime import datetime, timedelta, timezone

try:
    from aws_assume_role.saml import parse_xml, parse_saml_time
except ImportError:
    from saml import parse_xml, parse_saml_time


SAML_ASSERTION_NS = 'urn:oasis:names:tc:SAML:2.0:assertion'
# Expirations this close to the requested duration count as granted in full
TOLERANCE = timedelta(minutes=2)
CREDENTIAL_PROCESS_TIP = ("To have the AWS CLI and SDKs renew the credentials by themselves, use "
                          "--credential-process (see the README).")


def get_session_not_on_or_after(saml_response):
    """
    Returns when the OneLogin session in the SAMLResponse ends
    (AuthnStatement SessionNotOnOrAfter), or None.
    """
    try:
        doc = parse_xml(base64.b64decode(saml_response))
        for statement in doc.iter('{%s}AuthnStatement' % SAML_ASSERTION_NS):
            value = statement.get('SessionNotOnOrAfter')
            if value:
                return parse_saml_time(value)
    except Exception:
        pass
    return None


def format_duration(delta):
    minutes = max(int(delta.total_seconds() // 60), 0)
    if minutes < 120:
        return "%s minutes" % minutes
    return "%.1f hours" % (minutes / 60)


def explain_session_length(requested_seconds, expiration, saml_response, now=None):
    """
    Returns a message when the credentials expire noticeably earlier than
    requested, naming the limit that most likely cut them short, or None.
    """
    now = now or datetime.now(timezone.utc)
    expiration = expiration.astimezone(timezone.utc)
    requested = timedelta(seconds=requested_seconds)
    if expiration - now >= requested - TOLERANCE:
        return None

    message = "\nNote: you asked for %s, but these credentials expire in %s." % (
        format_duration(requested), format_duration(expiration - now))
    session_end = get_session_not_on_or_after(saml_response)
    if session_end is not None and abs(session_end - expiration) <= TOLERANCE:
        message += ("\nAWS ends the credentials when the OneLogin session in the SAML response ends "
                    "(SessionNotOnOrAfter). To get longer sessions, ask your OneLogin admin to raise "
                    "the session length of the AWS app in OneLogin.")
    else:
        message += ("\nThe limit is set outside this tool, by the IAM role's maximum session duration "
                    "or by the AWS app in OneLogin.")
    return message + "\n" + CREDENTIAL_PROCESS_TIP


def explain_max_session_duration(requested_seconds):
    return ("The IAM role allows shorter sessions than the %s you asked for. Its 'Maximum session duration' "
            "is 1 hour unless an AWS admin raises it (up to 12 hours) in the IAM console.\n%s" % (
                format_duration(timedelta(seconds=requested_seconds)), CREDENTIAL_PROCESS_TIP))
