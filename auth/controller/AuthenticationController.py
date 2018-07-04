# this file contains functions to check user credentials
# and generate a JWT token
import time
import binascii
import jwt
import os

from pbkdf2 import crypt
from sqlalchemy.orm import exc as orm_exceptions
from sqlalchemy import exc as sqlalchemy_exceptions

import auth.conf as conf

from auth.database.flaskAlchemyInit import HTTPRequestError
from auth.database.Models import User
from auth.database.flaskAlchemyInit import log
from auth.alarms import AlarmError

from dojot.module import Log

LOGGER = Log().color_log()

def authenticate(db_session, auth_data):
    if 'username' not in auth_data.keys():
        raise HTTPRequestError(400, 'missing username')
    if 'passwd' not in auth_data.keys():
        raise HTTPRequestError(400, 'missing password')

    username = auth_data['username']
    passwd = auth_data['passwd']

    try:
        user = db_session.query(User).filter_by(username=username.lower()).one()
    except orm_exceptions.NoResultFound:
        raise AlarmError(401, 'AuthenticationError', username)
    except sqlalchemy_exceptions.DBAPIError:
        raise HTTPRequestError(500, 'Problem connecting to database')

    if not user.hash:
        raise HTTPRequestError(401, 'This user is inactive')

    if user.hash == crypt(passwd, user.salt, 1000).split('$').pop():
        groups_id = [g.id for g in user.groups]

        claims = {
            'iss': user.key,
            'iat': int(time.time()),
            'exp': int(time.time() + conf.tokenExpiration),
            'profile': user.profile,  # Obsolete. Kept for compatibility
            'groups': groups_id,
            'userid': user.id,

            # Generate a random string as nonce
            'jti': str(binascii.hexlify(os.urandom(16)), 'ascii'),
            'service': user.service,
            'username': user.username
        }
        encoded = jwt.encode(claims, user.secret, algorithm='HS256')
        LOGGER.info('user ' + user.username + ' loged in')
        return str(encoded, 'ascii')

    raise AlarmError(403, 'AuthorizationError', username, user.id)


# this helper function receive a base64 JWT token
# the function decodes the JWT, checks the signature (if configured to check)
# and returns the jwt payload as a python dictionary
def get_jwt_payload(raw_jwt):
    if not raw_jwt:
        raise HTTPRequestError(401, "AuthenticationError")

    # remove the bearer of the token
    split_token = raw_jwt.split(' ')
    if len(split_token) > 1:
        raw_jwt = split_token[1]

    try:
        jwt_payload = jwt.decode(raw_jwt, verify=False)
    except jwt.exceptions.DecodeError:
        raise HTTPRequestError(401, "Corrupted JWT")

    if jwt_payload.get('userid', None) is None:
        raise HTTPRequestError(401, "Invalid JWT payload")

    # TODO: Change signature verification for a public/private key schema
    # TODO: where Auth has the private key for signing tokens.

    return jwt_payload


def user_id_from_jwt(token):
    if not token:
        raise HTTPRequestError(401, "AuthenticationError")
    return get_jwt_payload(token)['userid']
