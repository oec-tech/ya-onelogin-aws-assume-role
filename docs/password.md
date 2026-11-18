# Your password

The tool can keep your OneLogin password in the system keyring, so you only
type it once:

| System | Where the password is kept |
| --- | --- |
| Windows | Credential Manager |
| macOS | Keychain |
| Linux | Secret Service (GNOME Keyring, KWallet) |

## Set it up (one line)

Add this to your `config.yaml`:

```yaml
onelogin-username: jane@example.com
save-password: true
```

That's all. What happens next:

1. **First run:** run the tool as usual (`olaar`). It looks in the keyring,
   finds nothing, and asks for your password as before:

    ```text
    No password saved in the keyring for account / service -> jane / onelogin
    OneLogin Password:
    ```

2. **After you log in successfully**, it saves the password and says where:

    ```text
    Saved the password in the system keyring (service 'onelogin', account 'jane')
    ```

    The *service* is `onelogin`; the *account* is your OneLogin username up to
    the `@`.

3. **Every later run** reads the password from the keyring and doesn't ask.

4. **When you change your OneLogin password**, the saved one is rejected; the
   tool asks for the new one and, once the login works, replaces the saved
   password:

    ```text
    Updated the password in the system keyring (service 'onelogin', account 'jane')
    ```

The password is only saved after OneLogin accepted it, so a typo never ends up
in the keyring.

!!! tip "Without a config file"
    `--save-password` on the command line does the same for that run. You still
    need it (or `save-password: true`) on later runs, because that's what tells
    the tool to look in the keyring.

## Check that it worked

Run the tool again: it should go straight to MFA without asking for the
password. To look at the saved entry directly:

=== "Windows"

    Open **Control Panel → Credential Manager → Windows Credentials** and look
    under *Generic Credentials* for `onelogin` (user name `jane`). Or, in a
    terminal:

    ```console
    uvx keyring get onelogin jane
    ```

=== "macOS"

    Open **Keychain Access** and search for `onelogin`. Or:

    ```console
    uvx keyring get onelogin jane
    ```

=== "Linux"

    ```console
    uvx keyring get onelogin jane
    ```

`uvx keyring get` prints the saved password, so mind who is looking at your
screen. Replace `jane` with your username up to the `@`.

## Change or remove it

```console
uvx keyring set onelogin jane    # asks for the new password and saves it
uvx keyring del onelogin jane    # removes it; the tool asks again next time
```

To stop using the keyring altogether, remove `save-password` (and any
`keychain-service` / `keychain-account`) from `config.yaml`.

## Other names

The service and account names can be changed with `keychain-service` and
`keychain-account` (or `--keychain-service` / `--keychain-account`), e.g. to
share an entry with another tool:

```yaml
keychain-service: my-company-sso
keychain-account: jane
```

With only these two set (no `save-password`), the tool reads the password from
that entry, offers to save it when it had to ask, and updates it when it was
wrong.

## Avoid `--onelogin-password`

`--onelogin-password` puts the password on the command line, where it is
visible in the process list and saved in your shell history. Use the keyring
instead.
