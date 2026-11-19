"""
Logs in to OneLogin (including MFA) and gets the SAMLResponse for the AWS app.
"""

import json
import os
import sys
import time

try:
    from aws_assume_role.onelogin_client import OneLoginClient
    from aws_assume_role.prompts import select_option
    from aws_assume_role.last_choices import get_last_choice, save_last_choice, index_of
    from aws_assume_role import prompts, ui
except ImportError:
    import prompts
    from onelogin_client import OneLoginClient
    from prompts import select_option
    from last_choices import get_last_choice, save_last_choice, index_of
    import ui


MFA_ATTEMPTS_FOR_WARNING = 3
TIME_SLEEP_ON_RESPONSE_PENDING = 15
MAX_ITER_GET_SAML_RESPONSE = 6
DEFAULT_MFA_POLL_INTERVAL = 3
MAX_MFA_POLL_INTERVAL = 30
PUSH_TIMEOUT = 90


def get_client(options):
    client_id = client_secret = ip = json_data = None
    region = 'us'
    client_file_name = 'onelogin.sdk.json'

    if options.client_id and options.client_secret:
        client_id = options.client_id
        client_secret = options.client_secret
        region = options.region
        ip = options.ip
    else:
        if options.config_file_path is not None and os.path.isfile(os.path.join(options.config_file_path, client_file_name)):
            json_data = open(os.path.join(options.config_file_path, client_file_name)).read()
        elif os.path.isfile(client_file_name):
            json_data = open(client_file_name).read()
        elif os.path.isfile(os.path.expanduser('~') + '/.onelogin/' + client_file_name):
            json_data = open(os.path.expanduser('~') + '/.onelogin/' + client_file_name).read()
        if json_data is not None:
            data = json.loads(json_data)
            if 'client_id' in data.keys() and 'client_secret' in data.keys():
                client_id = data['client_id']
                client_secret = data['client_secret']
                if 'region' in data.keys() and data['region']:
                    region = data['region']
                if 'ip' in data.keys() and data['ip']:
                    ip = data['ip']

    if not client_id or not client_secret:
        raise Exception("OneLogin Client ID and Secret are required")
    client = OneLoginClient(client_id, client_secret, region)
    client.api_configuration["assertion"] = options.saml_api_version
    if ip:
        client.ip = ip
    client.prepare_token()
    if client.error == 401 or client.access_token is None:
        raise Exception("Invalid client_id and client_secret. Access_token could not be retrieved")
    return client


def device_label(device):
    label = device.auth_factor_name or device.type
    if device.display_name:
        label += " (%s)" % device.display_name
    return label


def find_device(devices, name):
    """
    Returns the index of the MFA device that --mfa-device names: its id, type
    or label, ignoring case, or else the first device whose label contains it.
    """
    wanted = name.strip().lower()
    for index, device in enumerate(devices):
        names = (str(device.id), device.auth_factor_name, device.type, device.display_name, device_label(device))
        if wanted in [str(n).lower() for n in names if n]:
            return index
    for index, device in enumerate(devices):
        if wanted in device_label(device).lower():
            return index
    return None


def _debug(message):
    # OLAAR_DEBUG=1 shows each push check, to tell a lost approval from a slow one
    if os.environ.get('OLAAR_DEBUG'):
        print("[debug] %s" % message, file=sys.stderr, flush=True)


def _describe(response, client):
    if response is not None:
        return "%s (%s)" % (getattr(response, 'type', None), getattr(response, 'message', ''))
    return "error %s %s" % (getattr(client, 'error', None), getattr(client, 'error_description', None))


def _check_push(client, app_id, device_id, state_token):
    try:
        response = client.get_saml_assertion_verifying(app_id, device_id, state_token, None, do_not_notify=True)
    except Exception as error:
        # A dropped connection or a timeout: try again on the next check
        client.error, client.error_description = 'network', str(error)
        response = None
    _debug("push check: %s" % _describe(response, client))
    return response


def wait_for_push(client, app_id, device_id, state_token, response, poll_interval, stop=None):
    """
    Checks every poll_interval seconds whether the push notification was
    approved, for up to PUSH_TIMEOUT seconds or until stop is set. Backs off
    while OneLogin rate-limits the checks, renews an expired API token, and
    keeps going through network errors and server errors. Returns the last
    response, or None after an error that checking again won't fix.
    """
    interval = poll_interval
    deadline = time.monotonic() + PUSH_TIMEOUT
    while time.monotonic() < deadline:
        if response is not None:
            if response.type != "pending":
                break
            interval = poll_interval
        elif client.error == '429':
            interval = min(interval * 2, MAX_MFA_POLL_INTERVAL)
        elif client.error == '401':
            # The API access token expired while waiting
            client.get_access_token()
        elif client.error not in ('network',) and not str(client.error).startswith('5'):
            break
        if stop is not None:
            if stop.wait(interval):
                break
        else:
            time.sleep(interval)
        response = _check_push(client, app_id, device_id, state_token)
    return response


PUSH_DONE = object()


def wait_for_push_or_code(client, app_id, device_id, state_token, response, poll_interval):
    """
    Waits for the push approval while also accepting the code from the app,
    whichever comes first. Returns (response, code): the push response when
    it was approved, or the code that was typed (or None for neither).
    Without a terminal it only waits for the push.
    """
    try:
        if not prompts.menus_available():
            raise ImportError
        import copy
        import threading
        import questionary
        from prompt_toolkit.application import run_in_terminal
    except ImportError:
        with ui.waiting("Approve the push notification in OneLogin Protect..."):
            return wait_for_push(client, app_id, device_id, state_token, response, poll_interval), None

    question = questionary.text("Approve the push in OneLogin Protect, or type the code from the app:",
                                style=prompts.menu_style(), qmark="?",
                                validate=lambda text: bool(text.strip()) or "Type the code, or approve the push")
    app = question.application
    stop = threading.Event()
    result = {}
    # Its own copy of the client, so the checks don't touch the error state of the main one
    poller = copy.copy(client)

    def notify(callback):
        loop = getattr(app, 'loop', None)
        for _ in range(50):
            if loop is not None and app.is_running:
                break
            time.sleep(0.1)
            loop = getattr(app, 'loop', None)
        if loop is not None and app.is_running and not stop.is_set():
            loop.call_soon_threadsafe(callback)

    def watch():
        result['response'] = wait_for_push(poller, app_id, device_id, state_token, response, poll_interval, stop)
        if stop.is_set():
            return
        if result['response'] is not None and result['response'].type == 'success':
            notify(lambda: app.exit(result=PUSH_DONE))
        else:
            notify(lambda: run_in_terminal(
                lambda: ui.warn("The push wasn't approved in time; type the code from the app")))

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    try:
        answer = question.unsafe_ask()
    except KeyboardInterrupt:
        stop.set()
        sys.exit(1)
    stop.set()
    pushed = result.get('response')
    if answer is PUSH_DONE or (pushed is not None and pushed.type == 'success'):
        return pushed, None
    return None, answer.strip()


def check_device_exists(devices, device_id):
    for device in devices:
        if device.id == device_id:
            return True
    return False


def get_saml_response(client, username_or_email, password, app_id, onelogin_subdomain, ip=None, mfa_verify_info=None, cmd_otp=None,
                      mfa_device=None, poll_interval=DEFAULT_MFA_POLL_INTERVAL):
    saml_endpoint_response = client.get_saml_assertion(username_or_email, password, app_id, onelogin_subdomain, ip)

    try_get_saml_response = 0
    verified_with_push = False
    while saml_endpoint_response is None or saml_endpoint_response.type == "pending":
        if saml_endpoint_response is None:
            if client.error in ['400', '401']:
                error_msg = "\n\nError %s. %s" % (client.error, client.error_description)
                if client.error_description == "Invalid subdomain":
                    ui.error("OneLogin doesn't know the subdomain '%s'" % onelogin_subdomain)
                    onelogin_subdomain = ui.ask_text("OneLogin subdomain (the part before .onelogin.com)")
                elif client.error_description in ["Authentication Failed: Invalid user credentials",
                                                  "password is empty"]:
                    ui.error("Wrong username or password" if client.error_description != "password is empty"
                             else "The password is empty")
                    password = ui.ask_password()
                elif client.error_description == "username is empty":
                    ui.error("The username is empty")
                    username_or_email = ui.ask_text("OneLogin username")
                else:
                    # An unrecognized 400/401 here is typically a wrong AWS app
                    # id (or an app the user isn't entitled to). Fail fast rather
                    # than re-submitting credentials, which can lock the account.
                    raise Exception(error_msg + "\nVerify that the AWS app id is "
                                    "correct and assigned to this user.")
            elif client.error is not None:
                # Any other error (e.g. app not found, rate limited, server
                # error) will not be resolved by re-sending the same request.
                # Retrying would burn login attempts and can lock the OneLogin
                # account, so stop here instead of looping (see issue 69).
                ui.error("OneLogin error %s: %s" % (client.error, client.error_description))
                sys.exit(1)

        if saml_endpoint_response and saml_endpoint_response.type == "pending":
            time.sleep(TIME_SLEEP_ON_RESPONSE_PENDING)
        saml_endpoint_response = client.get_saml_assertion(username_or_email, password, app_id, onelogin_subdomain, ip)
        try_get_saml_response += 1
        if try_get_saml_response == MAX_ITER_GET_SAML_RESPONSE:
            ui.error("OneLogin didn't confirm the login after %s tries" % MAX_ITER_GET_SAML_RESPONSE)
            sys.exit()

    if saml_endpoint_response and saml_endpoint_response.type is None:
        ui.error("OneLogin login failed: %s" % saml_endpoint_response.message)
        sys.exit()

    if saml_endpoint_response and saml_endpoint_response.type == "success":
        if saml_endpoint_response.mfa is not None:
            device_type = None
            mfa = saml_endpoint_response.mfa
            devices = mfa.devices
            state_token = mfa.state_token

            if mfa.user and mfa.user.get('id'):
                enriched = client.get_otp_devices(mfa.user['id'])
                if enriched:
                    devices = enriched

            if mfa_verify_info is None or 'device_id' not in mfa_verify_info:
                ui.step("OneLogin asks for a second factor (MFA)")
            else:
                if not check_device_exists(devices, mfa_verify_info['device_id']):
                    ui.warn("The MFA device you used before (ID %s) isn't available anymore" % mfa_verify_info['device_id'])
                    mfa_verify_info = None
                else:
                    device_id = mfa_verify_info['device_id']
                    device_type = mfa_verify_info['device_type']

            # Consider case 0 or MFA that requires a trigger
            if mfa_verify_info is None or device_type in ["OneLogin SMS", "OneLogin Protect"]:
                if mfa_verify_info is None:
                    device_selection = find_device(devices, mfa_device) if mfa_device else None
                    if device_selection is not None:
                        ui.ok("MFA device: %s" % device_label(devices[device_selection]))
                    else:
                        if mfa_device:
                            ui.warn("No MFA device matches '%s'" % mfa_device)
                        device_ids = [str(device.id) for device in devices]
                        last_device = get_last_choice(onelogin_subdomain, username_or_email, app_id, 'mfa_device')
                        device_selection = select_option("Select the MFA device",
                                                         [device_label(device) for device in devices],
                                                         index_of(device_ids, last_device))
                        save_last_choice(onelogin_subdomain, username_or_email, app_id, 'mfa_device', device_ids[device_selection])
                        if len(devices) == 1:
                            ui.ok("MFA device: %s" % device_label(devices[0]))
                    device = devices[device_selection]
                    device_id = device.id
                    device_type = device.auth_factor_name or device.type

                    mfa_verify_info = {
                        'device_id': device_id,
                        'device_type': device_type,
                    }

                if device_type == "OneLogin SMS":
                    # Trigger SMS
                    saml_endpoint_response = client.get_saml_assertion_verifying(app_id, device_id, state_token, None, do_not_notify=True)
                    ui.step("Sent a code by SMS")
                elif device_type == "OneLogin Protect":
                    # Send the push (also when a code was used last time: codes are single-use)
                    saml_endpoint_response = client.get_saml_assertion_verifying(app_id, device_id, state_token, None, do_not_notify=False)
                    _debug("push sent: %s" % _describe(saml_endpoint_response, client))
                    pushed, typed_code = wait_for_push_or_code(client, app_id, device_id, state_token,
                                                               saml_endpoint_response, poll_interval)

                    if pushed is not None and pushed.type == 'success':
                        saml_endpoint_response = pushed
                        verified_with_push = True
                        ui.ok("Push approved")
                    elif typed_code:
                        cmd_otp = typed_code
                    else:
                        ui.warn("The push wasn't approved in time; enter the code from the app instead")

                if not verified_with_push:
                    if cmd_otp:
                        otp_token = cmd_otp
                    else:
                        # Otherwise, let's request OTP token to be inserted manually
                        otp_token = ui.ask_text("Code from %s" % device_type)
            elif 'otp_token' not in mfa_verify_info:
                if cmd_otp:
                    otp_token = cmd_otp
                else:
                    otp_token = ui.ask_text("Code from %s" % mfa_verify_info['device_type'])
            else:
                otp_token = mfa_verify_info['otp_token']

            if not verified_with_push:
                saml_endpoint_response = client.get_saml_assertion_verifying(app_id, device_id, state_token, otp_token, do_not_notify=True)

                mfa_error = 0
                while client.error or saml_endpoint_response is None:
                    if client.error_description == "State token is invalid or expired":
                        # State token expired so the OTP Token was not able to be processed
                        # regenerate new SAMLResponse and get new state_token
                        return get_saml_response(client, username_or_email, password, app_id, onelogin_subdomain, ip, mfa_verify_info,
                                                 mfa_device=mfa_device, poll_interval=poll_interval)
                    else:
                        if mfa_error > MFA_ATTEMPTS_FOR_WARNING and len(devices) > 1:
                            if ui.confirm("The code failed %s times. Pick another MFA device?" % MFA_ATTEMPTS_FOR_WARNING):
                                # Let's regenerate the SAMLResponse and initialize again the count
                                return get_saml_response(client, username_or_email, password, app_id, onelogin_subdomain, ip, None,
                                                        poll_interval=poll_interval)
                            else:
                                ui.note("Then try another code.")
                        else:
                            if device_type == "OneLogin SMS":
                                # Trigger SMS, before ask for OTP
                                saml_endpoint_response = client.get_saml_assertion_verifying(app_id, device_id, state_token, None, do_not_notify=True)

                            if client.error_description == "Failed authentication with this factor":
                                ui.error("That code was wrong or expired")
                            else:
                                ui.error("OneLogin couldn't check that code")

                        otp_token = ui.ask_text("New code")
                        saml_endpoint_response = client.get_saml_assertion_verifying(app_id, device_id, state_token, otp_token, do_not_notify=True)

                    mfa_error = mfa_error + 1
                    mfa_verify_info['otp_token'] = otp_token

    if saml_endpoint_response.saml_response is not None:
        ui.ok("Logged in to OneLogin")
    result = {
        'saml_response': saml_endpoint_response.saml_response,
        'mfa_verify_info': mfa_verify_info,
        'username_or_email': username_or_email,
        'password': password,
        'onelogin_subdomain': onelogin_subdomain
    }
    return result
