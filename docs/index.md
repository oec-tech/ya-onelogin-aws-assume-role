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
  push approval is noticed within about 3 seconds, and you can type the code
  from the app at any time instead.
- **A modern terminal UI**: colored status lines, a spinner while you wait,
  a summary of the new credentials, and arrow-key menus with
  type-to-filter that start on your last choice. With `-p`, the role menu shows
  only the roles of that profile's account or role name first.
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
$ olaar -p data
╭──────────────────────────────────────────────────╮
│ olaar  OneLogin → AWS  v2.1.1                    │
│ ya-onelogin-aws-assume-role, an unofficial fork  │
╰──────────────────────────────────────────────────╯
✔ Using the password saved in the keyring
✔ MFA device: OneLogin Protect (Pixel)
? Approve the push in OneLogin Protect, or type the code from the app:
✔ Push approved
✔ Logged in to OneLogin
✔ Role DataEngineer in account 123456789012 (from your settings)
╭─ AWS credentials saved ────────────────────────────╮
│ Role      DataEngineer                             │
│ Account   123456789012                             │
│ Expires   2026-01-01 22:00 (in 12h 0m)             │
│ Region    us-east-1                                │
│ Saved to  profile [data] in ~/.aws/credentials     │
╰────────────────────────────────────────────────────╯
```

Next: [install it](install.md).
