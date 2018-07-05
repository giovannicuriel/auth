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


@hooks.before("Relationship management "
              "> Manage relationships between users and groups "
              "> Add user to group")
def create_sample_group_user(transaction):
    global USER_GROUP
    user_id, group_id = auth.create_sample_users(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/1/", f"/{user_id[0]}/")
    transaction['fullPath'] = transaction['fullPath'].replace("/101", f"/{group_id[2]}")
    USER_GROUP.append((user_id[0], group_id[2]))


@hooks.before("Relationship management "
              "> Manage relationships between users and groups "
              "> Remove a user from group")
def create_sample_associated_group_user(transaction):
    global USER_GROUP, REQUESTER
    user_id, group_id = auth.create_sample_users(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/1/", f"/{user_id[0]}/")
    transaction['fullPath'] = transaction['fullPath'].replace("/101", f"/{group_id[2]}")
    rship.add_user_group(db.session, user_id[0], group_id[2], REQUESTER)
    USER_GROUP.append((user_id[0], group_id[1]))


@hooks.before("Relationship management "
              "> Manage relationships between users and permissions "
              "> Give a permission to a user")
def create_sample_user_perm(transaction):
    global USER_PERMS
    user_id, group_id = auth.create_sample_users(transaction)
    perm_id = crud.create_sample_perms(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/1/", f"/{user_id[0]}/")
    transaction['fullPath'] = transaction['fullPath'].replace("/201", f"/{perm_id}")
    USER_PERMS.append((user_id[0], perm_id))


@hooks.before("Relationship management "
              "> Manage relationships between users and permissions "
              "> Revoke a user permission")
def create_sample_associated_user_perm(transaction):
    global USER_PERMS, REQUESTER
    user_id, group_id = auth.create_sample_users(transaction)
    perm_id = crud.create_sample_perms(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/1/", f"/{user_id[0]}/")
    transaction['fullPath'] = transaction['fullPath'].replace("/201", f"/{perm_id}")
    rship.add_user_permission(db.session, user_id[0], perm_id, REQUESTER)
    USER_PERMS.append((user_id[0], perm_id))


@hooks.before("Relationship management "
              "> Manage relationships between group and permissions "
              "> Give a permission to a group")
def create_sample_group_perm(transaction):
    global GROUP_PERMS
    perm_id = crud.create_sample_perms(transaction)
    group_id = crud.create_sample_groups(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/101/", f"/{group_id[0]}/")
    transaction['fullPath'] = transaction['fullPath'].replace("/201", f"/{perm_id}")
    GROUP_PERMS.append((group_id[0], perm_id))


@hooks.before("Relationship management "
              "> Manage relationships between group and permissions "
              "> Revoke a group permission")
def create_sample_associated_group_perm(transaction):
    global GROUP_PERMS
    perm_id = crud.create_sample_perms(transaction)
    group_id = crud.create_sample_groups(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace("/101/", f"/{group_id[0]}/")
    transaction['fullPath'] = transaction['fullPath'].replace("/201", f"/{perm_id}")
    rship.add_group_permission(db.session, group_id[0], perm_id, REQUESTER)
    GROUP_PERMS.append((group_id[0], perm_id))


@hooks.after("Relationship management "
             "> Manage relationships between users and groups "
             "> Add user to group")
@hooks.after("Relationship management "
             "> Manage relationships between users and groups "
             "> Remove a user from group")
@hooks.after("Relationship management "
             "> Manage relationships between users and permissions "
             "> Give a permission to a user")
@hooks.after("Relationship management "
             "> Manage relationships between users and permissions "
             "> Revoke a user permission")
@hooks.after("Relationship management "
             "> Manage relationships between group and permissions "
             "> Give a permission to a group")
@hooks.after("Relationship management "
             "> Manage relationships between group and permissions "
             "> Revoke a group permission")
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
