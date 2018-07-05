import dredd_hooks as hooks
import auth.controller.CRUDController as crud
import auth.controller.RelationshipController as rship
import crud_api_hook as crud
import auth_hook as auth
from auth.database.flaskAlchemyInit import db, HTTPRequestError
from auth.database.flaskAlchemyInit import log
from dojot.module import Log

LOGGER = Log().color_log()

USER_GROUP = []
USER_PERMS = []
GROUP_PERMS = []

REQUESTER = {
    "userid": 0,
    "username": "dredd"
}


@hooks.before("Reports > User direct permissions > Retrieve user direct permissions")
@hooks.before("Reports > All user permissions > Retrieve all user permissions")
def create_sample_user_perm(transaction):
    global USER_PERMS
    user_id, group_id = auth.create_sample_users(transaction)
    perm_id = crud.create_sample_perms(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/admin/", f"/{user_id[0]}/")
    rship.add_user_permission(db.session, user_id[0], perm_id, REQUESTER)
    USER_PERMS.append((user_id[0], perm_id))


@hooks.before("Reports > User groups > Retrieve all user groups")
def create_sample_user_group(transaction):
    global USER_GROUP, REQUESTER
    user_id, group_id = auth.create_sample_users(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/admin/", f"/{user_id[0]}/")
    # rship.add_user_group(db.session, user_id[0], group_id[0], REQUESTER)
    USER_GROUP.append((user_id[0], group_id[0]))


@hooks.before("Reports > Group permissions > Retrieve all group permissions")
def create_sample_group_perm(transaction):
    global GROUP_PERMS
    perm_id = crud.create_sample_perms(transaction)
    group_id = crud.create_sample_groups(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/users/", f"/{group_id[0]}/")
    rship.add_group_permission(db.session, group_id[0], perm_id, REQUESTER)
    GROUP_PERMS.append((group_id[0], perm_id))


@hooks.before("Reports > Group users > Retrieve all users from a group")
def create_sample_group_user(transaction):
    global USER_GROUP, REQUESTER
    user_id, group_id = auth.create_sample_users(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/users/", f"/{group_id[0]}/")
    # rship.add_user_group(db.session, user_id[0], group_id[0], REQUESTER)
    USER_GROUP.append((user_id[0], group_id[0]))


@hooks.after("Reports > User direct permissions > Retrieve user direct permissions")
@hooks.after("Reports > All user permissions > Retrieve all user permissions")
@hooks.after("Reports > User groups > Retrieve all user groups")
@hooks.after("Reports > Group permissions > Retrieve all group permissions")
@hooks.after("Reports > Group users > Retrieve all users from a group")
def clean_associations(transaction):

    for user_id, group_id in USER_GROUP:
        try:
            rship.remove_user_group(db.session, user_id, group_id, REQUESTER)
        except HTTPRequestError as e:
            pass
    for group_id, perm_id in GROUP_PERMS:
        try:
            rship.remove_group_permission(db.session, group_id, perm_id, REQUESTER)
        except HTTPRequestError as e:
            pass
    for user_id, perm_id in USER_PERMS:
        try:
            rship.remove_user_permission(db.session, user_id, perm_id, REQUESTER)
        except HTTPRequestError as e:
            pass
