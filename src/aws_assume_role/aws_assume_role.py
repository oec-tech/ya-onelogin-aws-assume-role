#!/usr/bin/python

"""
The onelogin-aws-assume-role command: picks the AWS role from the SAMLResponse,
assumes it with STS, and prints the credentials or saves them to a profile.
"""

import getpass
import json
import os
import sys
import time
import boto3
import botocore.client
import keyring

from base64 import b64decode
from botocore.exceptions import ClientError

try:
    from aws_assume_role.writer import ConfigFileWriter
    from aws_assume_role.accounts import process_account_and_role_choices
    from aws_assume_role.credential_process import credential_process
    from aws_assume_role.login import get_client, get_saml_response
    from aws_assume_role.options import get_options
    from aws_assume_role.prompts import read_line, get_yes_or_not, get_duration, ask_iteration_new_user, select_option
    from aws_assume_role.last_choices import get_last_choice, save_last_choice, index_of
    from aws_assume_role import prompts
    from aws_assume_role.saml import get_attributes, is_valid_saml_assertion, get_data_from_cache, write_data_to_cache, clean_cache
    from aws_assume_role.session import explain_session_length, explain_max_session_duration
except ImportError:
    from writer import ConfigFileWriter
    from accounts import process_account_and_role_choices
    from credential_process import credential_process
    from login import get_client, get_saml_response
    from options import get_options
    from prompts import read_line, get_yes_or_not, get_duration, ask_iteration_new_user, select_option
    from last_choices import get_last_choice, save_last_choice, index_of
    import prompts
    from saml import get_attributes, is_valid_saml_assertion, get_data_from_cache, write_data_to_cache, clean_cache
    from session import explain_session_length, explain_max_session_duration


def append_iterations(iterations):
    iterations.append(iterations[-1] + 1)
    return iterations


ROLE_ATTRIBUTE = 'https://aws.amazon.com/SAML/Attributes/Role'
DEFAULT_AWS_REGION = 'us-west-2'
SEPARATOR = "-----------------------------------------------------------------------"


def index_roles(roles, role_order=False):
    """
    Indexes the SAML role strings ("role_arn,principal_arn") by account id and
    role name, and also by role name and account id when listing by role.
    """
    by_account = {}
    by_role = {}
    for role in roles:
        role_info = role.split(",")[0].split(":")
        account_id = role_info[4]
        role_name = role_info[5].replace("role/", "")
        by_account.setdefault(account_id, {})[role_name] = role
        if role_order:
            by_role.setdefault(role_name, {})[account_id] = role
    return by_account, by_role


def choose_role(roles, options, onelogin_subdomain, username_or_email, app_id):
    """
    Returns the role string to assume: the one --aws-account-id and
    --aws-role-name select, the only one, or the one picked from the menu.
    Returns None when the SAMLResponse has no usable role.
    """
    roles = [role for role in roles if role]
    if len(roles) == 1:
        data = roles[0].split(',')
        if data[0] == 'Default' or len(data) < 2 or not data[1]:
            return None
        print("Unique AWS Role available selected: %s" % roles[0])
        return roles[0]
    if not roles:
        return None

    print("")
    by_account, by_role = index_roles(roles, options.role_order)
    selection_info, labels, role_option = process_account_and_role_choices(by_account, by_role, options)
    if role_option is None:
        if options.aws_account_id and options.aws_role_name:
            print("SAMLResponse from Identity Provider does not contain available AWS Role: %s for AWS Account: %s" % (options.aws_role_name, options.aws_account_id))
        last_role = get_last_choice(onelogin_subdomain, username_or_email, app_id, 'role')
        role_option = select_option("Select the desired AWS Role", labels, index_of(selection_info, last_role))
        save_last_choice(onelogin_subdomain, username_or_email, app_id, 'role', selection_info[role_option])

    selected_role = selection_info[role_option]
    print("Option %s selected, AWS Role: %s" % (role_option, selected_role))
    return selected_role


def get_default_aws_region():
    return os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or DEFAULT_AWS_REGION


def get_aws_region(options):
    """
    Returns --aws-region, or asks for it, defaulting to the AWS_REGION or
    AWS_DEFAULT_REGION environment variable, then us-west-2.
    """
    if options.aws_region:
        return options.aws_region
    default = get_default_aws_region()
    print("\nAWS Region (" + default + "): ")
    aws_region = read_line()
    if not aws_region or aws_region == "-":
        return default
    return aws_region


def credential_values(aws_session_token, aws_region):
    credentials = aws_session_token['Credentials']
    return {
        'AWS_ACCESS_KEY_ID': credentials['AccessKeyId'],
        'AWS_SECRET_ACCESS_KEY': credentials['SecretAccessKey'],
        'AWS_SESSION_TOKEN': credentials['SessionToken'],
        'AWS_SESSION_EXPIRATION': credentials['Expiration'].strftime('%Y-%m-%dT%H:%M:%S%z'),
        'AWS_SECURITY_TOKEN': credentials['SessionToken'],
        'AWS_REGION': aws_region,
    }


def default_output():
    return 'cmd' if sys.platform.startswith('win') else 'export'


def format_credentials(aws_session_token, aws_region, output):
    """
    Formats the credentials as lines to paste into a shell (export for
    bash/zsh, cmd for the Windows Command Prompt, powershell), or as JSON.
    """
    values = credential_values(aws_session_token, aws_region)
    if output == 'json':
        return json.dumps(values, indent=2)
    templates = {
        'export': 'export %s=%s',
        'cmd': 'set %s=%s',
        'powershell': '$env:%s="%s"',
    }
    return "\n".join(templates[output] % (name, value) for name, value in values.items())


def print_credentials(aws_session_token, aws_region, output=None):
    output = output or default_output()
    if output == 'json':
        print(format_credentials(aws_session_token, aws_region, output))
        return
    print("\n%s\n" % SEPARATOR)
    print("Success!\n")
    print("Assumed Role User: %s\n" % aws_session_token['AssumedRoleUser']['Arn'])
    print("Temporary AWS Credentials Granted via OneLogin\n")
    print("Copy/Paste to set these as environment variables\n")
    print("%s\n" % SEPARATOR)
    print(format_credentials(aws_session_token, aws_region, output))


def save_credentials(config_file_writer, aws_file, profile_name, aws_session_token, aws_region):
    values = credential_values(aws_session_token, aws_region)
    config_file_writer.update_config({
        '__section__': profile_name,
        'aws_access_key_id': values['AWS_ACCESS_KEY_ID'],
        'aws_secret_access_key': values['AWS_SECRET_ACCESS_KEY'],
        'aws_session_token': values['AWS_SESSION_TOKEN'],
        'aws_session_expiration': values['AWS_SESSION_EXPIRATION'],
        'aws_security_token': values['AWS_SECURITY_TOKEN'],
        'region': aws_region,
    }, aws_file)


def get_keyring_account(options, username_or_email):
    # Without --keychain-account it defaults to the username before the @
    return options.keychain_account or username_or_email.split("@")[0]


def save_password_to_keyring(options, username_or_email, password, keyring_password):
    """
    After a successful login, stores the password in the system keyring when it
    was typed in: always with --save-password or when the saved one was wrong,
    otherwise after asking.
    """
    if not options.keychain_service or not password or password == keyring_password:
        return
    account = get_keyring_account(options, username_or_email)
    if keyring_password is None and not options.save_password:
        print("Save the OneLogin password in the system keyring (service '%s', account '%s')?  (y/n)" % (options.keychain_service, account))
        if get_yes_or_not() != 'y':
            return
    try:
        keyring.set_password(options.keychain_service, account, password)
    except Exception as e:
        print("Unable to save the password in the keyring: %s" % e)
        return
    print("%s the password in the system keyring (service '%s', account '%s')" % (
        "Saved" if keyring_password is None else "Updated", options.keychain_service, account))


def main():
    options = get_options()
    # On Windows a credential_process prompts on CONOUT$, which the menus can't drive
    prompts.use_menus = options.menu and not (options.credential_process and os.name == 'nt')
    if options.credential_process:
        credential_process(options, assume_role)
    else:
        assume_role(options)


def assume_role(options):
    """
    Logs in to OneLogin and assumes the selected AWS role, then prints or saves
    the credentials. With --credential-process it returns the
    AssumeRoleWithSAML response instead.
    """
    print("\nya-onelogin-aws-assume-role: OneLogin AWS Assume Role Tool (unofficial fork)\n")

    client = get_client(options)

    client.get_access_token()

    mfa_verify_info = None
    role_arn = principal_arn = None
    ip = None

    if hasattr(client, 'ip'):
        ip = client.ip

    # --aws-profile names the AWS profile to write; otherwise it's --profile
    write_profile = options.aws_profile or options.profile_name
    profile_name = write_profile or "default"

    if options.file is None:
        aws_file = os.path.expanduser('~/.aws/credentials')
    else:
        aws_file = options.file

    cmd_otp = None
    if options.otp:
        cmd_otp = options.otp

    config_file_writer = None
    botocore_config = botocore.client.Config(signature_version=botocore.UNSIGNED)
    ask_for_user_again = False
    ask_for_role_again = False
    sleep = False
    iterations = list(range(0, options.loop))
    duration = options.duration
    username_or_email = password = app_id = onelogin_subdomain = None
    keyring_password = None
    result = None

    for i in iterations:
        if sleep:
            time.sleep(options.time * 60)
            sleep = False

            if result is not None and not is_valid_saml_assertion(b64decode(result['saml_response'])):
                result = None
        # Only use the otp provided by the command line on the first loop
        if i > 0:
            cmd_otp = None

        if options.cache_saml:
            cached_data = get_data_from_cache()
            if cached_data:
                if is_valid_saml_assertion(b64decode(cached_data['saml_response'])):
                    print("Found a valid SAML cache for the user %s" % cached_data['username_or_email'])
                    result = cached_data

                    username_or_email = result['username_or_email']
                    onelogin_subdomain = result['onelogin_subdomain']
                    mfa_verify_info = result['mfa_verify_info']
                    app_id = result['app_id']
                else:
                    print("The cached SAML expired for the user %s" % cached_data['username_or_email'])
                    if i == 0:
                        print("Reuse rest of the data?  (y/n)")
                        answer = get_yes_or_not()
                        if answer == 'y':
                            username_or_email = cached_data['username_or_email']
                            onelogin_subdomain = cached_data['onelogin_subdomain']
                            mfa_verify_info = cached_data['mfa_verify_info']
                            app_id = cached_data['app_id']
                        else:
                            clean_cache()

        # Allow user set a new profile name when switching from User or Role
        if ask_for_user_again or ask_for_role_again:
            if not (write_profile is None and options.file is None):
                print("Do you want to set a new profile name?  (y/n)")
                answer = get_yes_or_not()
                if answer == 'y':
                    print("Profile name: ")
                    profile_name = read_line()

        missing_onelogin_data = username_or_email is None or password is None or app_id is None or onelogin_subdomain is None

        if ask_for_user_again:
            print("OneLogin Username: ")
            username_or_email = read_line()
            keyring_password = None

            password = getpass.getpass("\nOneLogin Password: ")
            ask_for_user_again = False
            ask_for_role_again = True
        elif result is None and missing_onelogin_data:
            # Capture OneLogin Account Details
            if username_or_email is None:
                if options.username:
                    username_or_email = options.username
                else:
                    print("OneLogin Username: ")
                    username_or_email = read_line()

            if password is None:
                if options.password:
                    password = options.password
                else:
                    if options.keychain_service:
                        keychain_account = get_keyring_account(options, username_or_email)
                        try:
                            password = keyring_password = keyring.get_password(options.keychain_service, keychain_account)
                        except Exception as e:
                            print("Unable to read the keyring: %s" % e)
                        if password is None:
                            print("No password saved in the keyring for account / service -> %s / %s" % (keychain_account, options.keychain_service))
                if password is None:
                    password = getpass.getpass("\nOneLogin Password: ")

            if app_id is None:
                if options.app_id:
                    app_id = options.app_id
                else:
                    print("\nAWS App ID: ")
                    app_id = read_line()

            if options.subdomain:
                onelogin_subdomain = options.subdomain
            elif onelogin_subdomain is None:
                print("\nOnelogin Instance Sub Domain: ")
                onelogin_subdomain = read_line()

        if result is None:
            result = get_saml_response(client, username_or_email, password, app_id, onelogin_subdomain, ip, mfa_verify_info, cmd_otp,
                                       mfa_device=options.mfa_device, poll_interval=options.mfa_poll_interval)

            username_or_email = result['username_or_email']
            password = result['password']
            if not options.password:
                save_password_to_keyring(options, username_or_email, password, keyring_password)
                keyring_password = password if options.keychain_service else None
            onelogin_subdomain = result['onelogin_subdomain']
            mfa_verify_info = result['mfa_verify_info']

            if options.cache_saml:
                cached_content = result
                cached_content['app_id'] = app_id
                write_data_to_cache(cached_content)

        saml_response = result['saml_response']

        if i == 0 or ask_for_role_again:
            if ask_for_role_again:
                duration = options.duration

            attributes = get_attributes(saml_response)
            if ROLE_ATTRIBUTE not in attributes:
                print("SAMLResponse from Identity Provider does not contain AWS Role info")
                if ask_iteration_new_user():
                    ask_for_user_again = True
                    result = None
                    iterations = append_iterations(iterations)
                    continue
            else:
                selected_role = choose_role(attributes[ROLE_ATTRIBUTE], options, onelogin_subdomain, username_or_email, app_id)
                if selected_role is None:
                    print("SAMLResponse from Identity Provider does not contain available AWS Role for this user")
                    if ask_iteration_new_user():
                        ask_for_user_again = True
                        result = None
                        iterations = append_iterations(iterations)
                        continue

                selected_role_data = selected_role.split(',')
                role_arn = selected_role_data[0]
                principal_arn = selected_role_data[1]
                ask_for_user_again = False

        if i == 0 or ask_for_role_again:
            # AWS Region - prompt on first run or when switching roles
            aws_region = get_aws_region(options)
            ask_for_role_again = False

        conn = boto3.client('sts', region_name=aws_region, config=botocore_config)
        try:
            if not role_arn or role_arn == "Default" or not principal_arn:
                print("Missing/Invalid selected AWS Role or Account")
                if ask_iteration_new_user():
                    ask_for_user_again = True
                    result = None
                    iterations = append_iterations(iterations)
                    continue
            aws_session_token = conn.assume_role_with_saml(
                RoleArn=role_arn,
                PrincipalArn=principal_arn,
                SAMLAssertion=saml_response,
                DurationSeconds=duration
            )
        except ClientError as err:
            if hasattr(err, 'message'):
                error_msg = err.message
            else:
                error_msg = err.__str__()

            if 'Token must be redeemed within 5 minutes of issuance' in error_msg or \
               'An error occurred (ExpiredTokenException) when calling the AssumeRoleWithSAML operation' in error_msg:
                print(error_msg)
                print("Generating a new SAMLResponse with the data already provided....")
                result = None
                iterations = append_iterations(iterations)
                ask_for_user_again = False
                ask_for_role_again = False
                continue
            elif "The requested DurationSeconds exceeds the MaxSessionDuration set for this role." in error_msg:
                print(error_msg)
                print(explain_max_session_duration(duration))
                print("Introduce a new value, to be used on this Role, for DurationSeconds between 900 and 43200. Previously was %s" % duration)
                duration = get_duration()
                iterations = append_iterations(iterations)
                ask_for_user_again = False
                ask_for_role_again = False
                continue
            elif "Not authorized to perform sts:AssumeRoleWithSAML" in error_msg:
                print(error_msg)
                ask_for_user_again = True
                result = None
                iterations = append_iterations(iterations)
                continue
            elif "Request ARN is invalid" in error_msg:
                print(error_msg)
                ask_for_user_again = False
                ask_for_role_again = True
                iterations = append_iterations(iterations)
                continue
            else:
                raise err

        session_note = explain_session_length(duration, aws_session_token['Credentials']['Expiration'], saml_response)
        if session_note:
            print(session_note)

        if options.credential_process:
            return aws_session_token

        if write_profile is None and options.file is None:
            print_credentials(aws_session_token, aws_region, options.output)
        else:
            if config_file_writer is None:
                config_file_writer = ConfigFileWriter()
            save_credentials(config_file_writer, aws_file, profile_name, aws_session_token, aws_region)

            print("Success!\n")
            print("Temporary AWS Credentials Granted via OneLogin\n")
            print("Updated AWS profile '%s' located at %s" % (profile_name, aws_file))

        if options.interactive:
            print("\n\nThe process regenerated credentials for user %s with AWS Role %s " % (username_or_email, selected_role))
            print("Do you want to execute now the process for the same user but with other AWS Role?  (y/n)")
            answer = get_yes_or_not()
            if answer == 'y':
                ask_for_user_again = False
                ask_for_role_again = True
                iterations = append_iterations(iterations)
                continue
            print("Do you want to execute now the process for other user?  (y/n)")
            answer = get_yes_or_not()
            if answer == 'y':
                ask_for_user_again = True
                result = None
                iterations = append_iterations(iterations)
                continue
            break

        if i < len(iterations) - 1:
            print("This process will regenerate credentials %s more times.\n" % (len(iterations) - i - 1))
            print("Press Ctrl + C to exit")
            sleep = True
        else:
            print("\nExecuted a total of %s iterations" % len(iterations))


if __name__ == '__main__':
    main()
