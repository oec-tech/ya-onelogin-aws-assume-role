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

For OneLogin Protect, the push goes out immediately and the tool asks:

```text
? Approve the push in OneLogin Protect, or type the code from the app:
```

Approve the push on your phone, **or** type the 6-digit code from the app and
press Enter, whichever is quicker. You don't have to wait for the push to
expire before typing the code.

While the question is open, the tool checks every **3 seconds** whether you
approved the push, for up to 90 seconds. Change the interval with
`--mfa-poll-interval` (1 to 30 seconds). When OneLogin rate-limits the checks,
the tool waits twice as long each time, up to 30 seconds. A dropped
connection or a server error doesn't end the checks, and an API token that
expires while waiting is renewed. After 90 seconds the question stays open
for the code. Without a terminal (scripts, `--credential-process`), it only
waits for the push and asks for the code afterwards.

### The push was approved but nothing happened

Type the code from the app instead; it works right away. To help find the
cause, run with `OLAAR_DEBUG=1`. That prints each check OneLogin answers, such
as `push check: pending (Authentication pending on OL Protect)`, so you can see
whether OneLogin still reported the push as pending after you approved it:

```console
OLAAR_DEBUG=1 olaar -p data          # macOS, Linux
set OLAAR_DEBUG=1 & olaar -p data    # Windows cmd
```

For OTP apps (Google Authenticator and similar) and SMS, type the code when
asked, or pass it with `--otp`.

## Menus

On a terminal, the MFA device and the AWS role are picked from arrow-key
menus: move with the arrow keys, **type to filter** the list, and press Enter.
Each menu starts on the device or role you picked last time, which is
remembered per user and app in `~/.onelogin/last_choices.json` (only ARNs and
device ids, nothing secret).

When the settings name an account or a role (`aws-account-id` or
`aws-role-name`, for example in a `profiles:` entry picked with `-p`) but not a
role you have, the role menu first lists only the matching roles: those in that
account, or with that role name. Pick one, or pick **Show all N roles...** at
the bottom to see every role. When both are set and match a role you have, no
menu is shown at all.

`--no-menu` (or `menu: false`) brings back numbered lists. They're also used
automatically when the input or output isn't a terminal.

## Skip the role menu entirely

The role list only arrives after MFA, so the way to choose ahead of time is to
name the role:

```yaml
aws-account-id: "123456789012"
aws-role-name: DataEngineer
```

Put these under `profiles:` to have a different role per profile. Quote the
account id, so YAML reads it as text and keeps any leading zeros. Give your
accounts readable names in the `accounts:` section so the menu shows
`DataEngineer (Account: 123456789012 - Data account)`.
