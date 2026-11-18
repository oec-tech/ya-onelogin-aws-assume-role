# ya-onelogin-aws-assume-role

!!! warning "Unofficial fork"
    This is an unofficial [community fork](https://github.com/oec-tech/ya-onelogin-aws-assume-role).
    It is **not** the official OneLogin tool and is not supported by OneLogin. The
    original project is [onelogin/onelogin-python-aws-assume-role](https://github.com/onelogin/onelogin-python-aws-assume-role),
    published on PyPI as `onelogin-aws-assume-role`. This fork is called
    `ya-onelogin-aws-assume-role` ("yet another") to keep the two apart.

`ya-onelogin-aws-assume-role`, or `olaar` for short, logs you in to OneLogin (with MFA), lets you pick an
AWS role from the OneLogin AWS app, and gets temporary AWS credentials for it
with `sts:AssumeRoleWithSAML`. It can print the credentials for your shell,
write them to an AWS profile, or hand them to the AWS CLI and SDKs on demand as
a `credential_process`.

## What this fork adds

- **[One config file](configuration.md)** (`config.yaml`) for every option, with
  per-profile settings and readable labels for your AWS accounts.
- **[No more typing your password](password.md)**: it is saved in Windows
  Credential Manager, macOS Keychain or the Linux Secret Service.
- **[Faster MFA](mfa.md)**: pick your device ahead of time with `--mfa-device`;
  push approval is noticed within about 3 seconds.
- **Arrow-key menus** with type-to-filter for the MFA device and AWS role, starting
  on your last choice.
- **[Automatic renewal](credential-process.md)** through the AWS
  `credential_process` setting, so you only approve the MFA push when the
  credentials run out.
- **[Clear session limits](session-length.md)**: when AWS hands out shorter
  credentials than you asked for, the tool says which limit did it.
- `--output powershell` / `json`, Python 3.10 to 3.14, and a set of bug fixes,
  including a private SAML cache file.

## A login in one command

With a [config file](configuration.md) and a [saved password](password.md):

```console
$ olaar
OneLogin AWS Assume Role Tool

Using MFA device: OneLogin Protect (Pixel)
PUSH with OTP token sent to device 1234567, waiting for approval...

Obtained SAMLResponse from OneLogin to be used at AWS
? Select the desired AWS Role (arrow keys to move, type to filter, Enter to select)
 » DataEngineer (Account: 123456789012 - Data account)
   ReadOnly (Account: 210987654321 - Production)
```

Next: [install it](install.md).
