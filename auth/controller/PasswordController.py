# This file contains function that implements password
# related policies

import logging
import binascii
from pbkdf2 import crypt
import os
import datetime

import sqlalchemy.orm.exc as orm_exceptions
from difflib import SequenceMatcher
from marisa_trie import Trie

from database.flaskAlchemyInit import HTTPRequestError
from database.historicModels import PasswdInactive, PasswordRequestInactive
from database.Models import PasswordRequest, User
from utils.emailUtils import send_mail
import conf

from auth.healthcheck import HEALTHCHECK, ServiceStatus

LOGGER = logging.getLogger('auth.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.INFO)


# read a password blacklist file
# and put these password on a trie
def load_password_blacklist():
    global password_blackList
    if conf.password_blackList == 'NOBLACKLIST':
        LOGGER.warning('No password blacklist file defined.')
        password_blackList = Trie()
        return

    if os.path.isfile('compiledPwdBlacklist.bin'):
        LOGGER.info('Loading pre-compiled password blacklist...')
        password_blackList = Trie()
        password_blackList.load('compiledPwdBlacklist.bin')
        LOGGER.info('... pre-compiled password blacklist was loaded.')

    else:
        try:
            LOGGER.info('Compiling password blacklist...')
            with open(conf.password_blackList, encoding="utf-8") as f:
                pwds = f.read().splitlines()
                password_blackList = Trie(pwds)
            password_blackList.save('compiledPwdBlacklist.bin')
        except FileNotFoundError:
            LOGGER.error('File ' + conf.password_blackList
                         + ' not found. Aborting.')
            exit(-1)


# load password blacklist on startup
load_password_blacklist()
HEALTHCHECK.password_compilation_monitor.trigger("loaded", ServiceStatus.systemOk)


# check if a password is obvious weak
# throws a exception if the password fail a test
def check_password_format(user, password):
    password_len = len(password)
    if password_len < conf.passwdMinLen:
        raise HTTPRequestError(400, 'password must have at least '
                                    + str(conf.passwdMinLen)
                                    + ' characters')
    if password_len > 512:
        raise HTTPRequestError(400, 'Calm down! 512 characters is the '
                                    ' maximum password length')
    lower_pwd = password.lower()

    # check if the password can be guessed with user info
    if (SequenceMatcher(None, lower_pwd, user.username)
        .find_longest_match(0, password_len, 0, len(user.username))
        .size > 4
        or
        SequenceMatcher(None, lower_pwd, user.email)
        .find_longest_match(0, password_len, 0, len(user.email))
        .size > 4
        or
        SequenceMatcher(None, lower_pwd, user.name.lower())
        .find_longest_match(0, password_len, 0, len(user.name.lower()))
            .size > 4):
        raise HTTPRequestError(400, 'Please, choose a password that is'
                                    ' harder to guess. Your user info may'
                                    ' give hints on this password')

    # check for dull sequences
    # like 'aaa' '123' 'abc'
    last_char = '\0'
    count_equals = 1
    count_up = 1
    count_down = 1
    for c in password:
        if ord(c) == ord(last_char) + 1:
            count_up += 1
        else:
            count_up = 1

        if ord(c) == ord(last_char) - 1:
            count_down += 1
        else:
            count_down = 1

        if c == last_char:
            count_equals += 1
        else:
            count_equals = 1

        if count_equals == 3 or count_up == 3 or count_down == 3:
            raise HTTPRequestError(400, 'do not use passwords with '
                                        ' easy to guess'
                                        ' character sequences')
        last_char = c

    # check vs a blacklist
    if password in password_blackList:
        raise HTTPRequestError(400, "This password can't be used, as it is "
                                    " in our blacklist of bad passwords")


def create_pwd(password):
    salt = str(binascii.hexlify(os.urandom(8)), 'ascii')
    password_hash = crypt(password, salt, 1000).split('$').pop()
    return salt, password_hash


# update a password.
# verify if the new password was used before
# save the current password on inactive table
def update(db_session, user, new_password):
    check_password_format(user, new_password)

    # check actual password
    if user.hash and (user.hash ==
                      crypt(new_password, user.salt, 1000).split('$').pop()):
        raise HTTPRequestError(400, "Please, choose a password"
                                    " that was not used before.")

    # check all old password from database
    if conf.passwdHistoryLen > 0:
        oldpwds = (
                    db_session.query(PasswdInactive)
                    .filter_by(user_id=user.id)
                    .order_by(PasswdInactive.deletion_date.desc())
                    .limit(conf.passwdHistoryLen)
                   )

        for pwd in oldpwds:
            if pwd.hash == crypt(new_password, pwd.salt, 1000).split('$').pop():
                raise HTTPRequestError(400, "Please, choose a password"
                                            " that was not used before")
    PasswdInactive.createInactiveFromUser(db_session, user)
    return create_pwd(new_password)


# an authenticated user can update it password
def update_endpoint(db_session, user_id, up_data):
    if up_data.get('oldpasswd', None) is None:
        raise HTTPRequestError(400, "Missing user's oldpasswd")

    if up_data.get('newpasswd', None) is None:
        raise HTTPRequestError(400, "Missing user's newpasswd")

    try:
        user = db_session.query(User). \
            filter_by(id=user_id).one()
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, 'User not found')

    if user.hash and (user.hash ==
       crypt(up_data['oldpasswd'], user.salt, 1000).split('$').pop()):
        user.salt, user.hash = update(db_session, user, up_data['newpasswd'])
        db_session.add(user)
    else:
        raise HTTPRequestError(400, "Incorrect password")


# check if a PasswordRequest is expired
# if it is, will be removed
def check_request_validity(db_session, reset_request):
    if ((reset_request.created_date
         + datetime.timedelta(minutes=conf.passwdRequestExpiration))
            < datetime.datetime.utcnow()):
        # save on inactive table before deletion
        PasswordRequestInactive.createInactiveFromRequest(db_session,
                                                          reset_request)
        db_session.delete(reset_request)
        db_session.commit()
        return False
    else:
        return True


def reset_password(db_session, link, reset_data):
    if 'passwd' not in reset_data.keys():
        raise HTTPRequestError(400, 'missing password')
    try:
        reset_request = db_session.query(PasswordRequest). \
            filter_by(link=link).one()
        if check_request_validity(db_session, reset_request):
            user = User.get_by_name_or_id(reset_request.user_id)
            user.salt, user.hash = update(db_session, user, reset_data['passwd'])

            # remove this used reset request
            PasswordRequestInactive.createInactiveFromRequest(db_session,
                                                              reset_request)
            db_session.delete(reset_request)
            return user
        else:
            raise HTTPRequestError(404, 'Page not found or expired')
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, 'Page not found or expired')


def create_password_reset_request(db_session, username):
    try:
        user = db_session.query(User). \
            filter_by(username=username).one()
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, 'User not found')

    # verify if this user have an active password reset request
    old_request = db_session.query(PasswordRequest). \
        filter_by(user_id=user.id).one_or_none()
    if old_request and check_request_validity(db_session, old_request):
        raise HTTPRequestError(409, 'You have a password reset'
                                    ' request in progress')

    request_dict = {
                    'user_id': user.id,
                    'link': str(binascii.hexlify(os.urandom(16)), 'ascii')
                  }

    password_request = PasswordRequest(**request_dict)
    db_session.add(password_request)

    with open('templates/passwordReset.html', 'r') as f:
        html = f.read()
    reset_link = conf.resetPwdView + request_dict['link']
    html = html.format(name=user.name, link=reset_link)
    send_mail(user.email, 'Password Reset', html)


def create_password_set_request(db_session, user):
    # verify if this user have an active password reset request
    request_dict = {
                    'user_id': user.id,
                    'link': str(binascii.hexlify(os.urandom(16)), 'ascii')
                  }

    password_request = PasswordRequest(**request_dict)
    db_session.add(password_request)

    with open('templates/passwordSet.html', 'r') as f:
        html = f.read()
    reset_link = conf.resetPwdView + request_dict['link']
    html = html.format(name=user.name,
                       link=reset_link,
                       username=user.username)
    send_mail(user.email, 'Account Activation', html)


# force expiration of the user's password reset request
def expire_password_reset_requests(db_session, userid):
    reset_request = db_session.query(PasswordRequest). \
        filter_by(user_id=userid).one_or_none()
    if reset_request:
        # save on inactive table before deletion
        PasswordRequestInactive.createInactiveFromRequest(db_session, reset_request)
        db_session.delete(reset_request)
