import logging
import requests
import binascii
import os
from requests import ConnectionError

import auth.conf as conf
from auth.database.flaskAlchemyInit import HTTPRequestError

LOGGER = logging.getLogger('auth.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.INFO)


def configure_kong(user):
    # Disable Kong is not advised. Only use for debug purposes
    if conf.kongURL == '':
        return {
                'key': 'nokey',
                'secret': str(binascii.hexlify(os.urandom(16)), 'ascii'),
                'kongid': 'noid'
                }

    try:
        response = requests.post('%s/consumers' % conf.kongURL,
                                 data={'username': user})
        if response.status_code == 409:
            LOGGER.warning("Consumer already exists")
        elif not (200 <= response.status_code < 300):
            LOGGER.error("failed to set consumer: %d %s"
                         % (response.status_code, response.reason))
            LOGGER.error(response.json())
            return None

        headers = {"content-type": "application/x-www-form-urlencoded"}
        response = requests.post('%s/consumers/%s/jwt'
                                 % (conf.kongURL, user), headers=headers)
        if not (200 <= response.status_code < 300):
            LOGGER.error("failed to create key: %d %s"
                         % (response.status_code, response.reason))
            LOGGER.error(response.json())
            return None

        reply = response.json()
        return {
                'key': reply['key'],
                'secret': reply['secret'],
                'kongid': reply['id']
                }
    except ConnectionError as connection_error:
        LOGGER.error(f"Failed to connect to kong: {connection_error}")
        return None
    except TimeoutError as timeout_error:
        LOGGER.error(f"Kong timed out: {timeout_error}")
        return None
    except requests.TooManyRedirects as redirects_error:
        LOGGER.error(f"Thank you! But our Kong is in another castle: {redirects_error}")
        return None
    except requests.exceptions.RequestException as request_error:
        LOGGER.error(f"Something wrong happened while contacting Kong: {request_error}")
        return None


# Invalidate old kong shared secret
def revoke_kong_secret(username, token_id):
    if conf.kongURL == '':
        return
    try:
        requests.delete("%s/consumers/%s/jwt/%s"
                        % (conf.kongURL, username, token_id))
    except ConnectionError:
        LOGGER.error("Failed to connect to kong")
        raise HTTPRequestError(500, "Failed to connect to kong")
        

# Invalidate old kong shared secret and generates a new one
def reset_kong_secret(username, token_id):
    if conf.kongURL == 'DISABLED':
        return
    try:
        delete_response = requests.delete("%s/consumers/%s/jwt/%s"
                        % (conf.kongURL, username, token_id))  

        if not (200 <= delete_response.status_code < 300):
            LOGGER.error("failed to delete key: %d %s"
                         % (delete_response.status_code, delete_response.reason))
            LOGGER.error(delete_response.json())
            return None

        headers = {"content-type": "application/x-www-form-urlencoded"}
        response = requests.post('%s/consumers/%s/jwt'
                                 % (conf.kongURL, username), headers=headers)
        if not (200 <= response.status_code < 300):
            LOGGER.error("failed to create key: %d %s"
                         % (response.status_code, response.reason))
            LOGGER.error(response.json())
            return None   

        reply = response.json()

        return {
                'key': reply['key'],
                'secret': reply['secret'],
                'kongid': reply['id']
                }
    except ConnectionError:
        LOGGER.error("Failed to connect to kong")
        raise HTTPRequestError(500, "Failed to connect to kong")


def remove_from_kong(user):
    if conf.kongURL == '':
        return
    try:
        requests.delete("%s/consumers/%s" % (conf.kongURL, user))
    except ConnectionError:
        LOGGER.error("Failed to connect to kong")
        raise HTTPRequestError(500, "Failed to connect to kong")
