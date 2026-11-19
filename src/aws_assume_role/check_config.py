"""
--check-config: reads the config files the way a login would, then shows the
files used, the profiles, the settings in effect and anything that looks wrong,
without contacting OneLogin or AWS.
"""

import json
import os
import re

try:
    from aws_assume_role import ui
    from aws_assume_role.aws_assume_role import default_credentials_file, profile_usage_hints, shorten_home
except ImportError:
    import ui
    from aws_assume_role import default_credentials_file, profile_usage_hints, shorten_home

SDK_FILE_NAME = 'onelogin.sdk.json'
ACCOUNT_ID = re.compile(r'^\d{12}$')


def find_sdk_file(config_file_path):
    """
    Returns the onelogin.sdk.json that a login would read, or None.
    """
    candidates = [os.path.join(config_file_path, SDK_FILE_NAME)] if config_file_path else []
    candidates += [SDK_FILE_NAME, os.path.join(os.path.expanduser('~'), '.onelogin', SDK_FILE_NAME)]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def check_profiles(profiles, aliases):
    """
    Returns (rows, problems) for the 'profiles' entries: one row per entry
    and (level, message) pairs for what looks wrong.
    """
    rows = []
    problems = []
    writes = {}
    for name, values in profiles.items():
        account = values.get('aws_account_id')
        role = values.get('aws_role_name')
        target = values.get('aws_profile') or name
        writes.setdefault(target, []).append(name)
        label = account or ''
        if account and aliases and str(account) in aliases:
            label = "%s (%s)" % (account, aliases[str(account)])
        rows.append((name, label or '-', role or '-', target))
        if account and not ACCOUNT_ID.match(str(account).replace('-', '')):
            problems.append(('warn', "Profile '%s': aws-account-id '%s' isn't 12 digits. Quote it in YAML "
                                     "(\"012345678901\") so leading zeros are kept." % (name, account)))
        if not account and not role:
            problems.append(('note', "Profile '%s' names no account or role, so it always shows the full role menu." % name))
        elif not account or not role:
            problems.append(('note', "Profile '%s' names only the %s, so it shows a menu of the matching roles."
                                     % (name, "role" if role else "account")))
    for target, names in writes.items():
        if len(names) > 1:
            problems.append(('note', "Profiles %s all write the AWS profile [%s]; the last login wins."
                                     % (", ".join("'%s'" % n for n in names), target)))
    return rows, problems


def check_config(options, environ=None, keyring_module=None):
    """
    Prints the check and returns the exit code: 1 when a login can't work as
    configured, otherwise 0.
    """
    environ = os.environ if environ is None else environ
    errors = 0

    # Files
    files = []
    if options.config:
        files.append(("Config", shorten_home(options.config)))
    for path in getattr(options, 'overlay_paths', []) or []:
        files.append(("Overlay", shorten_home(path)))
    sdk_file = find_sdk_file(options.config_file_path)
    if sdk_file:
        files.append(("API keys", shorten_home(sdk_file)))
    aws_file = options.file or default_credentials_file(environ)
    files.append(("Writes to", shorten_home(aws_file)))
    ui.summary("Files", files, style="cyan")
    if not options.config:
        ui.warn("No config.yaml found (looked in ~/.onelogin, -c and ONELOGIN_AWS_ASSUME_ROLE_CONFIG)")

    # OneLogin
    client_ok = bool(options.client_id and options.client_secret)
    if not client_ok and sdk_file:
        try:
            with open(sdk_file) as f:
                data = json.load(f)
            client_ok = bool(data.get('client_id') and data.get('client_secret'))
        except (OSError, ValueError) as e:
            ui.error("Can't read %s: %s" % (shorten_home(sdk_file), e))
            errors += 1
    if not client_ok:
        ui.error("No OneLogin API client_id and client_secret (set them in config.yaml or %s)" % SDK_FILE_NAME)
        errors += 1
    password = "asked every time"
    if options.password:
        password = "from the command line or config (consider save-password instead)"
    elif options.keychain_service:
        account = options.keychain_account or (options.username or '').split('@')[0]
        password = "keyring service '%s', account '%s'" % (options.keychain_service, account)
        try:
            keyring_module = keyring_module or __import__('keyring')
            saved = account and keyring_module.get_password(options.keychain_service, account)
            password += ": saved" if saved else ": not saved yet (asked once, then saved)"
        except Exception as e:
            password += ": can't read the keyring (%s)" % str(e).split('.')[0]
    ui.summary("OneLogin", [
        ("API keys", "found" if client_ok else "missing"),
        ("Region", options.region),
        ("Subdomain", options.subdomain or "asked at login"),
        ("Username", options.username or "asked at login"),
        ("App ID", options.app_id or "asked at login"),
        ("Password", password),
        ("MFA device", options.mfa_device or "picked from a menu"),
    ], style="red" if not client_ok else "cyan")

    # Profiles
    profiles = getattr(options, 'yaml_profiles', {}) or {}
    rows, problems = check_profiles(profiles, options.account_aliases)
    selected = getattr(options, 'selected_profile', None)
    if rows:
        ui.table("Profiles (-p NAME)", ["Name", "Account", "Role", "Writes"],
                 [row if row[0] != selected else (row[0] + " *",) + row[1:] for row in rows])
        if selected:
            ui.note("* used by this run")
    if selected and selected not in profiles:
        ui.warn("Profile '%s' has no entry under 'profiles:', so the role menu is shown and [%s] is written"
                % (selected, options.aws_profile or selected))
    for level, message in problems:
        getattr(ui, level)(message)

    # This run
    write_profile = options.aws_profile or options.profile_name
    ui.summary("This run (%s)" % ("olaar -p %s" % selected if selected else "olaar"), [
        ("Account", options.aws_account_id or "picked from a menu"),
        ("Role", options.aws_role_name or "picked from a menu"),
        ("AWS region", options.aws_region or "asked at login"),
        ("Session", "%s seconds (%sh)" % (options.duration, round(options.duration / 3600.0, 1))),
        ("Saves to", "profile [%s]" % write_profile if write_profile else "nowhere: printed for you to paste"),
    ], style="cyan")
    if write_profile:
        for level, message in profile_usage_hints(write_profile, environ, os.name == 'nt'):
            getattr(ui, level)(message)

    warnings = sum(1 for level, _ in problems if level == 'warn')
    if errors:
        ui.error("%s problem(s) to fix before logging in" % errors)
    elif warnings:
        ui.warn("A login can work, but check the warning(s) above")
    else:
        ui.ok("The config looks good")
    return 1 if errors else 0
