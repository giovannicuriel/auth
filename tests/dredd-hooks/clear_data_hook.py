import dredd_hooks as hooks
import auth.controller.CRUDController as crud
from auth.database.Models import PermissionTypeEnum
from auth.database.flaskAlchemyInit import db
from auth.database.flaskAlchemyInit import HTTPRequestError

@hooks.before_all
def auth_clear_permissions_and_groups(transaction):
    requester = {
        "userid": 0,
        "username": "dredd"
    }
    try:
        users = crud.search_user(db.session, None)
        # Delete all users
        for user in users:
            if user.username != 'admin':
                crud.delete_user(db.session, user.username, requester)
    except HTTPRequestError:
        pass

    try:
        permissions = crud.search_perm(db.session)
        for permission in permissions:
            if permission.type != PermissionTypeEnum.system:
                crud.delete_perm(db.session, permission.name, requester)
    except HTTPRequestError as e:
        pass

    try:
        groups = crud.search_group(db.session)
        for group in groups:
            if group.name != 'admin':
                crud.delete_group(db.session, group.name, requester)
    except HTTPRequestError as e:
        pass


@hooks.after_each
def auth_clear_everything_hook(transaction):
    requester = {
        "userid": 0,
        "username": "dredd"
    }
    try:
        users = crud.search_user(db.session, None)
        # Delete all users
        for user in users:
            if user.username != 'admin':
                crud.delete_user(db.session, user.username, requester)
    except HTTPRequestError:
        pass

    try:
        permissions = crud.search_perm(db.session)
        for permission in permissions:
            if permission.type != PermissionTypeEnum.system:
                crud.delete_perm(db.session, permission.name, requester)
    except HTTPRequestError as e:
        pass

    try:
        groups = crud.search_group(db.session)
        for group in groups:
            if group.name != 'admin':
                crud.delete_group(db.session, group.name, requester)
    except HTTPRequestError as e:
        pass
