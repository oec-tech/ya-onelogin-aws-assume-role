# Configuration

Every command-line option can be set in a YAML file, so a plain
`ya-onelogin-aws-assume-role` is all you need to type.

## Where the file lives

The tool reads the first of:

1. the file given with `--config <path>`
2. the file named in the `ONELOGIN_AWS_ASSUME_ROLE_CONFIG` environment variable
3. `config.yaml` (or `config.yml`) in the folder given with `-c` / `--config-file-path`
4. `~/.onelogin/config.yaml`, which on Windows is `C:\Users\<you>\.onelogin\config.yaml`

The file holds your OneLogin API secret, so keep it readable only by you.

## Example

```yaml
# OneLogin API credentials and region (-i, -s, -r)
client_id: "0123456789abcdef"
client_secret: "..."
region: us

onelogin-username: jane@example.com     # -u
onelogin-subdomain: example             # -d
onelogin-app-id: 123456                 # -a

save-password: true                      # keep the password in the keyring
mfa-device: OneLogin Protect            # send the push without asking

aws-region: us-east-1
profile: my-profile                   # AWS profile to write (-p)
file: ~/.aws/credentials                # -f
duration: 10000                         # -z, in seconds

# Settings for one --profile, overriding the ones above
profiles:
  data:
    aws-account-id: "123456789012"
    aws-role-name: DataEngineer
  prod-read:
    aws-account-id: "210987654321"
    aws-role-name: ReadOnly

# Labels shown next to the account ids in the role menu
accounts:
  "123456789012": Data account
  "210987654321": Production
```

A [template](https://github.com/oec-tech/ya-onelogin-aws-assume-role/blob/master/config.yaml.template)
is in the repository.

## Profiles and the AWS profile they write

`-p NAME` does two things: it picks the `profiles:` entry called `NAME`, and it
writes the credentials to the AWS profile `[NAME]` in `~/.aws/credentials`.
With the example above, `-p data` assumes `DataEngineer` in `123456789012` and
writes `[data]`; a name without an entry (or no `-p` at all, with
`profile: my-profile` at the top) shows the role menu and writes that name.

To have several entries write to the **same** AWS profile, give them an
`aws-profile`:

```yaml
profiles:
  main:
    aws-account-id: "111111111111"
    aws-role-name: DataEngineer
    aws-profile: my-company-aws
  ai:
    aws-account-id: "222222222222"
    aws-role-name: ReadOnly
    aws-profile: my-company-aws
```

Now `-p main` and `-p ai` assume different roles, and both write
`[my-company-aws]`, so tools that use that AWS profile pick up
whichever you logged in to last. `--aws-profile` on the command line overrides
it for one run.

## Overlays: one file per account or setup

Keep the shared settings in `config.yaml` and put what differs in overlay files
next to it, named `config.<name>.yaml`:

```text
~/.onelogin/
├── config.yaml            # username, subdomain, keyring, MFA device, ...
├── config.accounta.yaml   # what's different for account A
└── config.accountb.yaml   # what's different for account B
```

```yaml
# config.accounta.yaml
onelogin-app-id: 123456
aws-region: us-east-1
profile: accounta
aws-account-id: "123456789012"
aws-role-name: DataEngineer
```

Pick one with `-O` / `--overlay`:

```console
ya-onelogin-aws-assume-role -O accounta
ya-onelogin-aws-assume-role --overlay accountb --duration 7200
```

- Settings in the overlay replace the same settings in `config.yaml`. Its
  `profiles` entries are merged setting by setting into the base's, and its
  `accounts` labels are added to the base's.
- Options given on the command line win over both (`--duration 7200` above).
- Several overlays stack in order: `-O accounta,dev` or `-O accounta -O dev`.
- Without `-O`, the `ONELOGIN_AWS_ASSUME_ROLE_OVERLAY` environment variable
  picks the overlay, which is handy per terminal or in a `credential_process`
  line.
- An overlay is looked for next to the base `config.yaml`, then in the `-c`
  folder and `~/.onelogin`. A value ending in `.yaml` is used as a path.
- A name that isn't found is an error, so a typo doesn't silently log you in
  to the wrong account.

## Setting names

Use the long command-line option without its dashes. Dashes and underscores
are interchangeable, so `onelogin-username`, `onelogin_username` and the
internal name `username` all work. Flags such as `cache-saml` or `no-menu` take
`true`. A few examples:

| Command line | `config.yaml` |
| --- | --- |
| `-u jane@example.com` | `onelogin-username: jane@example.com` |
| `-p data` | `profile: data` |
| `-z 10000` | `duration: 10000` |
| `-o powershell` | `output: powershell` |
| `--no-menu` | `menu: false` |

Unknown settings and wrong types are reported as errors, so typos don't go
unnoticed. `--otp` and `--config` only make sense on the command line.

## Precedence

From highest to lowest:

1. the command line
2. the `profiles` entry for the selected profile, from the overlays and `config.yaml`
3. the rest of the overlays (the last one given wins), then the rest of `config.yaml`
4. the older JSON files: the `profiles` entry, then the rest, of `onelogin.aws.json`, and `onelogin.sdk.json` for the API credentials

The profile is chosen by `-p`, or by `profile:` in the file. With `-p data`, the
example above uses account `123456789012` and role `DataEngineer`, so the role
is picked without a menu.

## Older JSON files

`onelogin.sdk.json` (API credentials, region, ip) and `onelogin.aws.json` (app
id, subdomain, username, profile, duration, region, account and role, keychain
settings, profiles) are still read from the `-c` folder, the current folder or
`~/.onelogin`. A role label file `accounts.yaml` with an `accounts:` mapping is
read from the same places. You can move everything into `config.yaml`.
