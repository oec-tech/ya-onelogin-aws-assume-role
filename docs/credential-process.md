# Automatic renewal

Instead of writing credentials to `~/.aws/credentials`, the AWS CLI and SDKs
can ask this tool for them whenever they need them, using the
[`credential_process`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sourcing-external.html)
setting. You never run the tool yourself; when the credentials expire, the next
AWS command logs in again, and with the setup below all you do is approve the
MFA push.

## Set it up

1. Put everything except MFA in `config.yaml`: username, subdomain, app id,
   region, a [saved password](password.md), `mfa-device`, and the account and
   role for each profile:

    ```yaml
    onelogin-username: jane@example.com
    onelogin-subdomain: example
    onelogin-app-id: 123456
    region: us
    save-password: true
    mfa-device: OneLogin Protect
    aws-region: us-east-1
    duration: 10000

    profiles:
      data:
        aws-account-id: "123456789012"
        aws-role-name: DataEngineer
    ```

2. Add a profile to `~/.aws/config` (on Windows `C:\Users\<you>\.aws\config`):

    ```ini
    [profile data]
    credential_process = ya-onelogin-aws-assume-role --credential-process --profile data
    region = us-east-1
    ```

    With [overlays](configuration.md#overlays-one-file-per-account-or-setup),
    use `--credential-process -O accounta` instead of `--profile`.

3. Use it like any other profile:

    ```console
    aws s3 ls --profile data
    ```

## How it behaves

- The credentials are cached in `~/.aws/onelogin/cache` and reused until 15
  minutes before they expire, so most commands don't log in at all. Delete
  that folder to force a new login.
- Prompts go to your terminal, not to the AWS CLI. On Linux and macOS the
  arrow-key menus work here too; on Windows the numbered lists are used.
- Several commands at once (for example Terraform with several providers) wait
  for one login instead of each asking for MFA. On Windows they aren't
  serialized.
- `--file`, `--loop` and `--interactive` can't be combined with
  `--credential-process` on the command line; set in `config.yaml`, they're
  ignored in this mode.
- If the tool is started without a terminal (for example by an IDE), prompts go
  to stderr, which you usually can't see. Configure everything except MFA.

## Without credential_process

`--loop` and `--time` re-run the login on a timer and rewrite the profile:

```console
ya-onelogin-aws-assume-role -p data --loop 8 --time 50
```
