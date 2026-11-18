# MFA and menus

## Pick your MFA device ahead of time

Without help, the tool lists your MFA devices and waits for you to choose one.
`--mfa-device` (or `mfa-device:` in `config.yaml`) chooses it for you:

```yaml
mfa-device: OneLogin Protect
```

It matches the device's id, type or label as shown in the device list,
ignoring case, and then any device whose label contains the text, so
`pixel` matches `OneLogin Protect (Pixel)`. If nothing matches, you get the
normal list.

## Push approval

For OneLogin Protect, the push goes out immediately and the tool checks every
**3 seconds** whether you approved it, for up to 90 seconds. Change the
interval with `--mfa-poll-interval` (1 to 30 seconds). When OneLogin
rate-limits the checks, the tool waits twice as long each time, up to 30
seconds. If the push isn't approved in time, it asks for the code from the
app instead.

For OTP apps (Google Authenticator and similar) and SMS, type the code when
asked, or pass it with `--otp`.

## Menus

On a terminal, the MFA device and the AWS role are picked from arrow-key
menus: move with the arrow keys, **type to filter** the list, and press Enter.
Each menu starts on the device or role you picked last time, which is
remembered per user and app in `~/.onelogin/last_choices.json` (only ARNs and
device ids, nothing secret).

`--no-menu` (or `menu: false`) brings back numbered lists. They're also used
automatically when the input or output isn't a terminal.

## Skip the role menu entirely

The role list only arrives after MFA, so the way to choose ahead of time is to
name the role:

```yaml
aws-account-id: "123456789012"
aws-role-name: DataEngineer
```

Put these under `profiles:` to have a different role per profile. Give your
accounts readable names in the `accounts:` section so the menu shows
`DataEngineer (Account: 123456789012 - Data account)`.
