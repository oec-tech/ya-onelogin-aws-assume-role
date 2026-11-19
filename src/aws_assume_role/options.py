"""
Command-line options, merged with the settings in config.yaml and onelogin.aws.json.
"""

import argparse
import json
import os

import yaml


CONFIG_FILE_NAMES = ('config.yaml', 'config.yml')
CONFIG_ENV_VAR = 'ONELOGIN_AWS_ASSUME_ROLE_CONFIG'
OVERLAY_ENV_VAR = 'ONELOGIN_AWS_ASSUME_ROLE_OVERLAY'
# Marks the options that were not given on the command line: argparse only
# fills in a default for attributes the namespace doesn't have yet.
_UNSET = object()
# onelogin.aws.json keeps the keys it has always supported
JSON_KEYS = {
    'app_id': 'app_id', 'subdomain': 'subdomain', 'username': 'username', 'profile': 'profile_name',
    'duration': 'duration', 'aws_region': 'aws_region', 'aws_account_id': 'aws_account_id',
    'aws_role_name': 'aws_role_name', 'keychain_service': 'keychain_service',
    'keychain_account': 'keychain_account',
}
JSON_PROFILE_KEYS = ('aws_account_id', 'aws_role_name', 'aws_region', 'app_id')
# Only make sense on the command line
CLI_ONLY = ('help', 'config', 'overlays', 'otp')


def build_parser():
    parser = argparse.ArgumentParser(
        description="Assume an AWS role with OneLogin and get temporary AWS credentials. "
                    "Every option can also be set in config.yaml (see --config).")

    parser.add_argument("--config",
                        dest="config",
                        help="Path to a YAML settings file. Default: $%s, then config.yaml in "
                             "the --config-file-path folder, then ~/.onelogin/config.yaml" % CONFIG_ENV_VAR)

    parser.add_argument("-O", "--overlay",
                        dest="overlays",
                        action="append",
                        help="Name of a config overlay: settings from config.NAME.yaml, next to config.yaml, "
                             "override config.yaml. Repeat or separate with commas to stack several. "
                             "Default: $%s" % OVERLAY_ENV_VAR)
    parser.add_argument("-i", "--client_id",
                        dest="client_id",
                        help="A valid OneLogin API client_id")
    parser.add_argument("-s", "--client_secret",
                        dest="client_secret",
                        help="A valid OneLogin API client_secret")
    parser.add_argument("-r", "--region",
                        dest="region",
                        default="us",
                        help="Onelogin region. us or eu  (Default value: us)")
    parser.add_argument("-t", "--time",
                        dest="time",
                        default=45,
                        type=int,
                        help="Sleep time between iterations, in minutes  [15-60 min]")
    parser.add_argument("-l", "--loop",
                        dest="loop",
                        default=1,
                        type=int,
                        help="Number of iterations")
    parser.add_argument("-p", "--profile",
                        dest="profile_name",
                        help="Profile to use: picks the matching 'profiles' entry in config.yaml and saves the "
                             "credentials as the AWS profile of that name (unless --aws-profile says otherwise)")
    parser.add_argument("--aws-profile",
                        dest="aws_profile",
                        help="AWS profile name to write the credentials to, when it should differ from --profile "
                             "(e.g. set in a 'profiles' entry so several entries write to the same AWS profile)")
    parser.add_argument("-f", "--file",
                        dest="file",
                        help="Set a custom path to save the AWS credentials. (if not used, default AWS path is used)")
    parser.add_argument("-u", "--onelogin-username",
                        dest="username",
                        help="OneLogin username (email address)")
    parser.add_argument("--onelogin-password",
                        dest="password",
                        help="OneLogin password")
    parser.add_argument("--otp",
                        dest="otp",
                        help="2FA OTP")
    parser.add_argument("-a", "--onelogin-app-id",
                        dest="app_id",
                        help="OneLogin app id")
    parser.add_argument("-d", "--onelogin-subdomain",
                        dest="subdomain",
                        help="OneLogin subdomain")
    parser.add_argument("-z", "--duration",
                        dest="duration",
                        type=int,
                        help="Desired AWS Credential Duration")
    parser.add_argument("-x", "--interactive",
                        dest="interactive",
                        default=False,
                        action="store_true",
                        help="Be asked how to proceed in each iteration?")
    parser.add_argument("-c", "--config-file-path",
                        dest="config_file_path",
                        help="Path to config file (onelogin.aws.json)")
    parser.add_argument("--aws-region",
                        dest="aws_region",
                        help="AWS region to use")
    parser.add_argument("--aws-account-id",
                        dest="aws_account_id",
                        help="AWS account id from where to select the role")
    parser.add_argument("--aws-role-name",
                        dest="aws_role_name",
                        help="AWS role name to select")
    parser.add_argument("--cache-saml",
                        dest="cache_saml",
                        default=False,
                        help="Store and use cached SAML Response and the Onelogin info to retrieve it.",
                        action="store_true")
    parser.add_argument("--role_order",
                        dest="role_order",
                        default=False,
                        help="By default in order to select Account/Role, the list will be ordered by account ids. Enable this to list by role name instead.",
                        action="store_true")
    parser.add_argument("--ip",
                        dest="ip",
                        help="The IP address to use for the SAML assertion")
    parser.add_argument("--saml-api-version",
                        dest="saml_api_version",
                        type=int,
                        default=1,
                        help="The version of the OneLogin SAML APIs to use")
    parser.add_argument("--keychain-service",
                        dest="keychain_service",
                        help="Service name of the password in the system keyring (macOS Keychain, Windows Credential Manager, ...). Default: onelogin")
    parser.add_argument("--keychain-account",
                        dest="keychain_account",
                        help="Account name of the password in the system keyring. Default: the OneLogin username before the @")
    parser.add_argument("--credential-process",
                        dest="credential_process",
                        default=False,
                        action="store_true",
                        help="Print the credentials as JSON for the AWS credential_process setting, reusing them until they are about to expire")
    parser.add_argument("-o", "--output",
                        dest="output",
                        choices=["export", "cmd", "powershell", "json"],
                        help="How to print the credentials when not saving them to a profile: export (bash/zsh), "
                             "cmd (Windows Command Prompt), powershell or json. Default: export, or cmd on Windows")
    parser.add_argument("--no-menu",
                        dest="menu",
                        default=True,
                        action="store_false",
                        help="Show numbered lists instead of arrow-key menus for picking the MFA device and AWS role")
    parser.add_argument("--save-password",
                        dest="save_password",
                        default=False,
                        action="store_true",
                        help="Save the OneLogin password in the system keyring after logging in, so it isn't asked for again")
    parser.add_argument("--mfa-device",
                        dest="mfa_device",
                        help="MFA device to use without asking, e.g. \"OneLogin Protect\" or \"Google Authenticator\" (matches the name shown in the device list)")
    parser.add_argument("--check-config",
                        dest="check_config",
                        default=False,
                        action="store_true",
                        help="Check the config files and show the profiles and settings in effect, without logging in")
    parser.add_argument("--init-profiles",
                        dest="init_profiles",
                        default=False,
                        action="store_true",
                        help="Log in once, then write a profile for every AWS role you have, named after the account aliases, "
                             "to a 'generated:' block of config.yaml. Your own 'profiles:' and 'accounts:' win over it")
    parser.add_argument("--mfa-poll-interval",
                        dest="mfa_poll_interval",
                        type=int,
                        default=3,
                        help="Seconds between checks whether a push notification was approved (Default value: 3)")
    return parser


def get_options(argv=None):
    parser = build_parser()
    # --overlay appends to a list, so it starts as None rather than _UNSET
    namespace = argparse.Namespace(**{
        action.dest: None if action.dest == 'overlays' else _UNSET
        for action in parser._actions if action.dest != 'help'})
    options = parser.parse_args(argv, namespace)
    cli_provided = {dest for dest, value in vars(options).items() if value is not _UNSET and value is not None}

    config_file_path = options.config_file_path if 'config_file_path' in cli_provided else None
    yaml_path = find_yaml_config(options.config if 'config' in cli_provided else None, config_file_path)
    yaml_config = load_yaml_config(parser, yaml_path) if yaml_path else {}
    overlay_names = get_overlay_names(options.overlays if 'overlays' in cli_provided else None)
    overlay_paths = [find_overlay(parser, name, yaml_path, config_file_path) for name in overlay_names]
    for overlay_path in overlay_paths:
        yaml_config = merge_yaml_configs(yaml_config, load_yaml_config(parser, overlay_path))
    json_config = get_config(options.config_file_path if 'config_file_path' in cli_provided else
                             yaml_config.get('global', {}).get('config_file_path')) or {}

    # Lowest to highest precedence; each layer only sets what it has a value for
    layers = [
        {action.dest: action.default for action in parser._actions if action.dest != 'help'},
        {dest: json_config[key] for key, dest in JSON_KEYS.items() if json_config.get(key)},
        yaml_config.get('global', {}),
    ]
    profile_name = options.profile_name if 'profile_name' in cli_provided else None
    # The highest layer that names a profile picks it
    for layer in reversed(layers[1:]):
        profile_name = profile_name or layer.get('profile_name')
    json_profile = (json_config.get('profiles') or {}).get(profile_name) or {}
    layers.insert(2, {key: json_profile[key] for key in JSON_PROFILE_KEYS if json_profile.get(key)})
    layers.append(yaml_config.get('profiles', {}).get(profile_name, {}))

    for layer in layers:
        for dest, value in layer.items():
            if dest not in cli_provided:
                setattr(options, dest, value)
    options.config = yaml_path
    options.overlays = overlay_names
    options.config_files = [path for path in [yaml_path] + overlay_paths if path]
    options.account_aliases = yaml_config.get('accounts')
    options.yaml_profiles = yaml_config.get('profiles', {})
    options.generated_profiles = yaml_config.get('generated_profiles', set())
    options.own_account_names = yaml_config.get('own_accounts', {})
    options.selected_profile = profile_name
    options.known_profiles = set(options.yaml_profiles) | set(json_config.get('profiles') or {})
    options.overlay_paths = overlay_paths

    if options.credential_process:
        if cli_provided & {'file', 'loop', 'interactive'}:
            parser.error("--credential-process can't be combined with --file, --loop or --interactive")
        # Settings meant for the interactive command don't apply here
        options.file, options.loop, options.interactive = None, 1, False

    if (options.keychain_account or options.save_password) and not options.keychain_service:
        options.keychain_service = 'onelogin'
    if options.keychain_service and not options.keychain_account and options.username:
        options.keychain_account = options.username.split("@")[0]
    options.time = options.time
    if options.time < 15:
        options.time = 15
    elif options.time > 60:
        options.time = 60

    if not options.duration:
        options.duration = 3600
    elif options.duration < 900:
        options.duration = 900
    elif options.duration > 43200:
        options.duration = 43200

    options.mfa_poll_interval = min(max(options.mfa_poll_interval or 3, 1), 30)

    if not options.saml_api_version:
        options.saml_api_version = 1
    elif options.saml_api_version < 1:
        options.saml_api_version = 1
    elif options.saml_api_version > 2:
        options.saml_api_version = 2

    return options


def get_config(config_file_path):
    json_data = None
    config_file_name = 'onelogin.aws.json'

    if config_file_path is not None and os.path.isfile(os.path.join(config_file_path, config_file_name)):
        json_data = open(os.path.join(config_file_path, config_file_name)).read()
    elif os.path.isfile(config_file_name):
        json_data = open(config_file_name).read()
    elif os.path.isfile(os.path.expanduser('~') + '/.onelogin/' + config_file_name):
        json_data = open(os.path.expanduser('~') + '/.onelogin/' + config_file_name).read()
    if json_data is not None:
        return json.loads(json_data)


def option_names(parser):
    """
    Maps the names accepted in config.yaml to option dests: the dest itself, and
    each long option without its dashes (e.g. onelogin_username, profile).
    """
    names = {}
    for action in parser._actions:
        if action.dest in CLI_ONLY:
            continue
        names[action.dest] = action.dest
        for option_string in action.option_strings:
            if option_string.startswith('--'):
                names[option_string[2:].replace('-', '_')] = action.dest
    return names


def find_yaml_config(config, config_file_path):
    if config:
        return config
    if os.environ.get(CONFIG_ENV_VAR):
        return os.environ[CONFIG_ENV_VAR]
    for folder in (config_file_path, os.path.join(os.path.expanduser('~'), '.onelogin')):
        for name in CONFIG_FILE_NAMES if folder else ():
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                return path
    return None


class UniqueKeyLoader(yaml.SafeLoader):
    """
    A YAML loader that rejects a key repeated in one mapping, which plain YAML
    loading silently resolves by keeping the last one.
    """


def _construct_unique_mapping(loader, node, deep=False):
    seen = {}
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                "while reading a mapping", node.start_mark,
                "'%s' appears twice (first on line %s)" % (key, seen[key] + 1), key_node.start_mark)
        seen[key] = key_node.start_mark.line
    return loader.construct_mapping(node, deep=deep)


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def load_yaml_config(parser, path):
    """
    Reads config.yaml: any command-line option by name, plus 'profiles'
    (settings for one --profile) and 'accounts' (account id -> label shown
    when picking a role). Returns {'global', 'profiles', 'accounts'}.
    """
    try:
        with open(os.path.expanduser(path)) as f:
            data = yaml.load(f, Loader=UniqueKeyLoader) or {}
    except OSError as e:
        parser.error("can't read the config file %s: %s" % (path, e.strerror))
    except yaml.YAMLError as e:
        parser.error("can't parse the config file %s: %s" % (path, e))
    if not isinstance(data, dict):
        parser.error("the config file %s must contain a mapping of option: value" % path)

    names = option_names(parser)
    actions = {action.dest: action for action in parser._actions}

    def convert(section, values):
        if not isinstance(values, dict):
            parser.error("%s in %s must be a mapping of option: value" % (section, path))
        converted = {}
        for key, value in values.items():
            dest = names.get(str(key).replace('-', '_'))
            if dest is None:
                parser.error("unknown setting '%s' in %s %s" % (key, path, section))
            if value is None or value == '':
                continue
            action = actions[dest]
            if action.type is not None:
                try:
                    value = action.type(value)
                except (TypeError, ValueError):
                    parser.error("setting '%s' in %s %s must be a %s" % (key, path, section, action.type.__name__))
            elif not isinstance(value, bool):
                value = os.path.expanduser(str(value)) if dest in ('file', 'config_file_path') else str(value)
            if action.choices and value not in action.choices:
                parser.error("setting '%s' in %s %s must be one of: %s" % (key, path, section, ", ".join(action.choices)))
            converted[dest] = value
        return converted

    def sections(source, where):
        profiles = source.pop('profiles', None) or {}
        accounts = source.pop('accounts', None) or {}
        if not isinstance(profiles, dict) or not isinstance(accounts, dict):
            parser.error("'profiles' and 'accounts' in %s%s must be mappings" % (where, path))
        return ({str(name): convert("profile '%s'" % name, values or {}) for name, values in profiles.items()},
                {str(account): str(label) for account, label in accounts.items()})

    # 'generated' is written by --init-profiles; what you write yourself wins over it
    generated = data.pop('generated', None) or {}
    if not isinstance(generated, dict):
        parser.error("'generated' in %s must be a mapping" % path)
    generated_profiles, generated_accounts = sections(dict(generated), "'generated' in ")
    profiles, accounts = sections(data, "")
    merged_profiles = {name: dict(values) for name, values in generated_profiles.items()}
    for name, values in profiles.items():
        merged_profiles[name] = dict(merged_profiles.get(name, {}), **values)
    return {
        'global': convert('', data),
        'profiles': merged_profiles,
        'accounts': dict(generated_accounts, **accounts),
        'generated_profiles': set(generated_profiles) - set(profiles),
        'own_accounts': accounts,
    }


def get_overlay_names(cli_overlays):
    """
    Returns the overlay names from --overlay (repeated or comma-separated),
    or else from the environment variable.
    """
    values = cli_overlays or [os.environ.get(OVERLAY_ENV_VAR, '')]
    return [name.strip() for value in values for name in value.split(',') if name.strip()]


def find_overlay(parser, name, yaml_path, config_file_path):
    """
    Finds config.NAME.yaml (or .yml) next to the base config.yaml, else in the
    --config-file-path folder or ~/.onelogin. A name ending in .yaml/.yml is
    taken as a path.
    """
    if name.endswith(('.yaml', '.yml')):
        path = os.path.expanduser(name)
        if os.path.isfile(path):
            return path
        parser.error("config overlay %s not found" % name)
    folders = [os.path.dirname(os.path.abspath(os.path.expanduser(yaml_path)))] if yaml_path else []
    folders += [config_file_path, os.path.join(os.path.expanduser('~'), '.onelogin')]
    for folder in folders:
        for extension in ('yaml', 'yml'):
            path = os.path.join(folder, 'config.%s.%s' % (name, extension)) if folder else None
            if path and os.path.isfile(path):
                return path
    parser.error("config overlay '%s' not found: looked for config.%s.yaml in %s" % (
        name, name, ", ".join(folder for folder in folders if folder)))


def merge_yaml_configs(base, overlay):
    """
    Returns base with overlay's settings on top: global settings and account
    labels replace the base's one by one, and each profile's settings replace
    that profile's in the base.
    """
    profiles = {name: dict(values) for name, values in base.get('profiles', {}).items()}
    for name, values in overlay.get('profiles', {}).items():
        profiles[name] = dict(profiles.get(name, {}), **values)
    return {
        'global': dict(base.get('global', {}), **overlay.get('global', {})),
        'profiles': profiles,
        'accounts': dict(base.get('accounts', {}), **overlay.get('accounts', {})),
        'generated_profiles': (base.get('generated_profiles', set()) | overlay.get('generated_profiles', set()))
        - (set(overlay.get('profiles', {})) - overlay.get('generated_profiles', set())),
        'own_accounts': dict(base.get('own_accounts', {}), **overlay.get('own_accounts', {})),
    }
