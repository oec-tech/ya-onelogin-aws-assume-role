# Session length

`-z` / `duration:` asks AWS for credentials that last up to 12 hours (43200
seconds; the default is 3600). Two limits outside this tool can make them
expire earlier.

## The IAM role's maximum session duration

Each IAM role has a **Maximum session duration**, 1 hour unless an AWS admin
raises it (up to 12 hours) in the IAM console under the role's *Summary*.
Asking for more fails with *The requested DurationSeconds exceeds the
MaxSessionDuration set for this role*; the tool explains this and asks for a
shorter duration.

## The OneLogin session

AWS also ends the credentials when the OneLogin session in the SAML response
ends (`SessionNotOnOrAfter`). This happens **silently**, so `-z` seems to have
no effect. The session length is set on the AWS app in OneLogin; ask your
OneLogin admin to raise it.

## What the tool tells you

When the credentials expire more than two minutes earlier than you asked, the
tool prints a note after logging in:

```text
Note: you asked for 2.8 hours, but these credentials expire in 59 minutes.
AWS ends the credentials when the OneLogin session in the SAML response ends
(SessionNotOnOrAfter). To get longer sessions, ask your OneLogin admin to raise
the session length of the AWS app in OneLogin.
```

Whatever the limit, [automatic renewal](credential-process.md) makes it matter
much less: an expired session only means one more MFA approval.
