# Usage

`ya-onelogin-aws-assume-role`, `olaar` and `onelogin-aws-assume-role` are the
same command; the examples use the full name.

## Print, save or hand over the credentials

=== "Print for your shell"

    Without `--profile` or `--file`, the credentials are printed as lines to
    paste into your shell. Pick the format with `-o` / `--output`:

    | `--output` | Shell | Example line |
    | --- | --- | --- |
    | `export` (default on Linux/macOS) | bash, zsh | `export AWS_ACCESS_KEY_ID=...` |
    | `cmd` (default on Windows) | Command Prompt | `set AWS_ACCESS_KEY_ID=...` |
    | `powershell` | PowerShell | `$env:AWS_ACCESS_KEY_ID="..."` |
    | `json` | scripts | `{"AWS_ACCESS_KEY_ID": "...", ...}` |

    In PowerShell, set `output: powershell` in `config.yaml` once.

=== "Save to an AWS profile"

    ```console
    ya-onelogin-aws-assume-role -p data
    ```

    writes the credentials to the `data` profile in `~/.aws/credentials` (or
    the file given with `-f`), so `aws --profile data ...` uses them.

=== "On demand"

    See [automatic renewal](credential-process.md).

## "The security token included in the request is expired"

When the login succeeded but `aws s3 ls` still says the token expired, the AWS
CLI is not using the credentials that were just saved. The summary at the end
of a run names the profile it wrote. Check these, in this order:

1. **Old credentials in the shell.** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   and `AWS_SESSION_TOKEN` win over every profile. They are often left over from
   pasting the printed `set ...` lines earlier. Clear them, or open a new terminal:

    === "cmd"

        ```bat
        set AWS_ACCESS_KEY_ID=
        set AWS_SECRET_ACCESS_KEY=
        set AWS_SESSION_TOKEN=
        set AWS_SECURITY_TOKEN=
        ```

    === "PowerShell"

        ```powershell
        Remove-Item Env:AWS_ACCESS_KEY_ID, Env:AWS_SECRET_ACCESS_KEY, Env:AWS_SESSION_TOKEN, Env:AWS_SECURITY_TOKEN -ErrorAction SilentlyContinue
        ```

    === "bash/zsh"

        ```sh
        unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
        ```

2. **A different profile.** Without `--profile`, the AWS CLI uses `AWS_PROFILE`,
   or else `[default]`. With `olaar -p data`, use `aws s3 ls --profile data`, or
   `set AWS_PROFILE=data` (PowerShell: `$env:AWS_PROFILE="data"`).
3. **Nothing was saved.** Without `-p` (and without `profile:` in the config),
   the credentials are only printed for you to paste, and the summary says
   "Profile: none".

4. **Another credentials file.** The tool writes to `AWS_SHARED_CREDENTIALS_FILE`
   when it's set, like the AWS CLI, and to `~/.aws/credentials` otherwise
   (`-f`/`file:` overrides both).

`aws configure list` (add `--profile NAME` to check one profile) shows which
profile the AWS CLI picked and where its keys came from: `env` means variables
in the shell, `shared-credentials-file` means the file this tool writes.

The tool checks 1 and 2 after saving and prints a warning when either applies.

## Choosing the region

`--aws-region` (or `aws-region:`) sets the AWS region written with the
credentials. Without it, the tool asks, suggesting `$AWS_REGION`,
`$AWS_DEFAULT_REGION` or `us-west-2`.

## Other options

- `--loop N --time M` repeats the login N times, M minutes apart (15 to 60),
  rewriting the profile each time.
- `-x` / `--interactive` asks after each login whether to continue with
  another role or user.
- `--cache-saml` keeps the last SAML response in `~/.aws/saml_cache.txt`
  (readable only by you) to switch roles without logging in again while it is
  valid.
- `--role_order` sorts the role menu by role name instead of account id.

## All options

Every option can also be set in [`config.yaml`](configuration.md).

```text
options:
  -h, --help            show this help message and exit
  --config CONFIG       Path to a YAML settings file. Default: $ONELOGIN_AWS_ASSUME_ROLE_CONFIG,
                        then config.yaml in the --config-file-path folder, then
                        ~/.onelogin/config.yaml
  -O, --overlay OVERLAYS
                        Name of a config overlay: settings from config.NAME.yaml, next to
                        config.yaml, override config.yaml. Repeat or separate with commas to stack
                        several. Default: $ONELOGIN_AWS_ASSUME_ROLE_OVERLAY
  -i, --client_id CLIENT_ID
                        A valid OneLogin API client_id
  -s, --client_secret CLIENT_SECRET
                        A valid OneLogin API client_secret
  -r, --region REGION   Onelogin region. us or eu (Default value: us)
  -t, --time TIME       Sleep time between iterations, in minutes [15-60 min]
  -l, --loop LOOP       Number of iterations
  -p, --profile PROFILE_NAME
                        Profile to use: picks the matching 'profiles' entry in config.yaml and
                        saves the credentials as the AWS profile of that name (unless --aws-
                        profile says otherwise)
  --aws-profile AWS_PROFILE
                        AWS profile name to write the credentials to, when it should differ from
                        --profile (e.g. set in a 'profiles' entry so several entries write to the
                        same AWS profile)
  -f, --file FILE       Set a custom path to save the AWS credentials. (if not used, default AWS
                        path is used)
  -u, --onelogin-username USERNAME
                        OneLogin username (email address)
  --onelogin-password PASSWORD
                        OneLogin password
  --otp OTP             2FA OTP
  -a, --onelogin-app-id APP_ID
                        OneLogin app id
  -d, --onelogin-subdomain SUBDOMAIN
                        OneLogin subdomain
  -z, --duration DURATION
                        Desired AWS Credential Duration
  -x, --interactive     Be asked how to proceed in each iteration?
  -c, --config-file-path CONFIG_FILE_PATH
                        Path to config file (onelogin.aws.json)
  --aws-region AWS_REGION
                        AWS region to use
  --aws-account-id AWS_ACCOUNT_ID
                        AWS account id from where to select the role
  --aws-role-name AWS_ROLE_NAME
                        AWS role name to select
  --cache-saml          Store and use cached SAML Response and the Onelogin info to retrieve it.
  --role_order          By default in order to select Account/Role, the list will be ordered by
                        account ids. Enable this to list by role name instead.
  --ip IP               The IP address to use for the SAML assertion
  --saml-api-version SAML_API_VERSION
                        The version of the OneLogin SAML APIs to use
  --keychain-service KEYCHAIN_SERVICE
                        Service name of the password in the system keyring (macOS Keychain,
                        Windows Credential Manager, ...). Default: onelogin
  --keychain-account KEYCHAIN_ACCOUNT
                        Account name of the password in the system keyring. Default: the OneLogin
                        username before the @
  --credential-process  Print the credentials as JSON for the AWS credential_process setting,
                        reusing them until they are about to expire
  -o, --output {export,cmd,powershell,json}
                        How to print the credentials when not saving them to a profile: export
                        (bash/zsh), cmd (Windows Command Prompt), powershell or json. Default:
                        export, or cmd on Windows
  --no-menu             Show numbered lists instead of arrow-key menus for picking the MFA device
                        and AWS role
  --save-password       Save the OneLogin password in the system keyring after logging in, so it
                        isn't asked for again
  --mfa-device MFA_DEVICE
                        MFA device to use without asking, e.g. "OneLogin Protect" or "Google
                        Authenticator" (matches the name shown in the device list)
  --mfa-poll-interval MFA_POLL_INTERVAL
                        Seconds between checks whether a push notification was approved (Default
                        value: 3)
```
