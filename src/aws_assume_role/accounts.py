#
# Display Account Aliases
#
# Handles displaying a 'pretty' AWS account alias based on yaml config file provided by the user
# Currently the onelogin saml does not support pulling the acct alias dynamically with the role names

import yaml
import os

def get_account_aliases_info(config_file_path):
    account_aliases = []
    accountsfile = None

    if config_file_path is not None and os.path.isfile(os.path.join(config_file_path, 'accounts.yaml')):
        accountsfile = open(os.path.join(config_file_path, 'accounts.yaml')).read()
    elif os.path.isfile('accounts.yaml'):
        accountsfile = open('accounts.yaml').read()
    elif os.path.isfile(os.path.expanduser('~') + '/.onelogin/' + 'accounts.yaml'):
        accountsfile = open(os.path.expanduser('~') + '/.onelogin/' + 'accounts.yaml').read()

    if accountsfile is not None:
        account_aliases = yaml.safe_load(accountsfile)
    return account_aliases


def identify_known_accounts(account_aliases, account_id):
    """
    Given a known list of account IDs from yaml config, append note about their account if they're known to us.
    :return: Account description
    """
    # If the accounts custom aliases yaml file does not exist just default to normal behavior
    if account_aliases:
        if 'accounts' in account_aliases.keys():
            accounts = account_aliases["accounts"]
            for acct in accounts.keys():
                if str(acct) == account_id:
                    return accounts[acct]
        return "Unidentified"
    else:
        return ""


def format_choice(role_name, account_id, account_aliases=None, mark=""):
    """
    Formats one account/role option of the role menu
    """
    account_alias = identify_known_accounts(account_aliases, account_id)
    if account_alias:
        return "%s (Account: %s - %s)%s" % (role_name, account_id, account_alias, mark)
    return "%s (Account %s)%s" % (role_name, account_id, mark)


def process_account_and_role_choices(info_indexed_by_account, info_indexed_by_roles, options):
    """
    Returns the role strings in menu order, their labels, and the index of the
    role that --aws-account-id/--aws-role-name select (or None).
    """
    role_option = None
    selection_info = []
    labels = []
    if info_indexed_by_account:
        account_aliases = get_account_aliases_info(options.config_file_path)
        # Labels from the 'accounts' section of config.yaml win over accounts.yaml
        config_aliases = getattr(options, 'account_aliases', None)
        if config_aliases:
            account_aliases = dict(account_aliases or {})
            account_aliases['accounts'] = dict(account_aliases.get('accounts') or {}, **config_aliases)
        if len(info_indexed_by_roles) > 0:
            # Order by role name
            entries = [(role_name, account_id, role_string)
                       for role_name, account_ids in sorted(info_indexed_by_roles.items())
                       for account_id, role_string in sorted(account_ids.items())]
        else:
            entries = [(role_name, account_id, role_string)
                       for account_id, role_names in sorted(info_indexed_by_account.items())
                       for role_name, role_string in sorted(role_names.items())]
        for role_name, account_id, role_string in entries:
            mark, found = check_info(account_id, role_name, options.aws_account_id, options.aws_role_name)
            if found:
                role_option = len(selection_info)
            selection_info.append(role_string)
            labels.append(format_choice(role_name, account_id, account_aliases, mark))

    return selection_info, labels, role_option


def same_account(account_id, config_account_id):
    """
    Compares account ids, also when the configured one lost its leading zeros
    (an unquoted number in YAML) or has spaces or dashes.
    """
    if not config_account_id:
        return False
    wanted = str(config_account_id).replace("-", "").strip()
    if wanted.isdigit() and account_id.isdigit():
        return int(account_id) == int(wanted)
    return account_id == wanted


def same_role(role_name, config_role_name):
    # IAM role names are case-insensitive
    return bool(config_role_name) and role_name.lower() == str(config_role_name).strip().lower()


def check_info(account_id, role_name, config_account_id, config_role_name):
    mark = ""
    found = False
    if same_account(account_id, config_account_id) and same_role(role_name, config_role_name):
        mark = " **"
        found = True
    elif same_account(account_id, config_account_id) or same_role(role_name, config_role_name):
        mark = " *"
    return mark, found



    