# Install

The tool needs Python 3.10 or newer. Install it straight from this fork's
repository: the `onelogin-aws-assume-role` package on PyPI is the upstream
release and doesn't include this fork's changes.

The package is called `ya-onelogin-aws-assume-role` and installs three
commands that do the same thing:

| Command | Why |
| --- | --- |
| `ya-onelogin-aws-assume-role` | the fork's full name |
| `olaar` | short to type |
| `onelogin-aws-assume-role` | the original name, so existing scripts and AWS profiles keep working |

Because of that last one, don't install the upstream package in the same
environment.

## With uv (recommended, works on Windows)

[uv](https://docs.astral.sh/uv/) installs the tool in its own environment and
puts the command on your `PATH`.

=== "Windows (PowerShell)"

    ```powershell
    # Install uv once
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

    # Install or update the tool
    uv tool install --force git+https://github.com/oec-tech/ya-onelogin-aws-assume-role
    ```

=== "macOS / Linux"

    ```bash
    # Install uv once
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Install or update the tool
    uv tool install --force git+https://github.com/oec-tech/ya-onelogin-aws-assume-role
    ```

If the command isn't found afterwards, run `uv tool update-shell` and open a new
terminal.

To try it without installing:

```console
uvx --from git+https://github.com/oec-tech/ya-onelogin-aws-assume-role olaar --help
```

## With pipx or pip

```console
pipx install git+https://github.com/oec-tech/ya-onelogin-aws-assume-role
# or, inside a virtualenv
pip install git+https://github.com/oec-tech/ya-onelogin-aws-assume-role
```

## Prerequisites in OneLogin and AWS

- A OneLogin **AWS Multi Account** (or single account) app, with your AWS
  accounts set up as SAML identity providers. You need the app's **app id**.
- OneLogin **API credentials** (client id and secret) with the
  *Authentication Only* scope, and your instance's **subdomain** and **region**
  (`us` or `eu`).

Put these in your [config file](configuration.md) next.
