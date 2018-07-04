import sqlalchemy.orm.exc as orm_exceptions

from auth.database.Models import Permission, User, Group
from auth.database.Models import UserPermission, GroupPermission, UserGroup
from auth.database.flaskAlchemyInit import HTTPRequestError
import auth.database.Cache as cache
from auth.database.flaskAlchemyInit import log
from auth.database.Models import MVUserPermission, MVGroupPermission

from dojot.module import Log

LOGGER = Log().color_log()

def add_user_group(db_session, user, group, requester):
    try:
        user = User.get_by_name_or_id(user)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, f"No user found with this ID or name: {user}")
    try:
        group = Group.get_by_name_or_id(group)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, f"No group found with this ID or name: {group}")

    if db_session.query(UserGroup).filter_by(
                                                user_id=user.id,
                                                group_id=group.id
                                             ).one_or_none():
        raise HTTPRequestError(409, "User is already a member of the group")

    r = UserGroup(user_id=user.id, group_id=group.id)
    db_session.add(r)
    cache.delete_key(userid=user.id)

    user.reset_token()
    db_session.add(user)

    LOGGER.info(f"user {user.username} added to group {group.name} by {requester['username']}")

    db_session.commit()


def remove_user_group(db_session, user, group, requester):
    try:
        user = User.get_by_name_or_id(user)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No user found with this ID or name")
    try:
        group = Group.get_by_name_or_id(group)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No group found with this ID or name")
    try:
        relation = db_session.query(UserGroup) \
            .filter_by(user_id=user.id, group_id=group.id).one()
        db_session.delete(relation)
        cache.delete_key(userid=user.id)

        user.reset_token()
        db_session.add(user)

        LOGGER.info(f"user {user.username} removed from {group.name} by {requester['username']}")
        db_session.commit()
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "User is not a member of the group")


# add a user to a list of groups
def add_user_many_groups(db_session, user, groups, requester):
    success = []
    failed = []

    # if a single group was given. convert to a one element list
    if not isinstance(groups, list):
        groups = [groups]

    for g in groups:
        try:
            add_user_group(db_session, user, g, requester)
            success.append(g)
        except HTTPRequestError:
            failed.append(g)
    return success, failed


def add_group_permission(db_session, group, permission, requester):
    try:
        group = Group.get_by_name_or_id(group)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No group found with this ID or name")
    try:
        perm = Permission.get_by_name_or_id(permission)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No permission found with this ID or name")

    if db_session.query(GroupPermission) \
            .filter_by(group_id=group.id, permission_id=perm.id).one_or_none():
        raise HTTPRequestError(409, "Group already have this permission")

    r = GroupPermission(group_id=group.id, permission_id=perm.id)
    db_session.add(r)
    cache.delete_key(action=perm.method,
                     resource=perm.path)
    LOGGER.info(f"permission {perm.name} added to group {group.name} by {requester['username']}")
    MVGroupPermission.refresh()
    db_session.commit()


def remove_group_permission(db_session, group, permission, requester):
    try:
        group = Group.get_by_name_or_id(group)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No group found with this ID or name")
    try:
        perm = Permission.get_by_name_or_id(permission)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No permission found with this ID")
    try:
        relation = db_session.query(GroupPermission) \
            .filter_by(group_id=group.id, permission_id=perm.id).one()
        db_session.delete(relation)
        cache.delete_key(action=perm.method,
                         resource=perm.path)
        LOGGER.info(f"permission {perm.name} removed from group {group.name} by {requester['username']}")
        MVGroupPermission.refresh()
        db_session.commit()
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "Group does not have this permission")


def add_user_permission(db_session, user, permission, requester):
    try:
        user = User.get_by_name_or_id(user)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No user found with this ID or name")
    try:
        perm = Permission.get_by_name_or_id(permission)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No permission found with this ID")

    if db_session.query(UserPermission) \
            .filter_by(user_id=user.id, permission_id=perm.id).one_or_none():
        raise HTTPRequestError(409, "User already have this permission")

    r = UserPermission(user_id=user.id, permission_id=perm.id)
    db_session.add(r)
    cache.delete_key(userid=user.id,
                     action=perm.method,
                     resource=perm.path)
    MVUserPermission.refresh()
    db_session.commit()
    LOGGER.info(f"user {user.username} received permission {perm.name} by {requester['username']}")


def remove_user_permission(db_session, user, permission, requester):
    try:
        user = User.get_by_name_or_id(user)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No user found with this ID or name")
    try:
        perm = Permission.get_by_name_or_id(permission)
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No permission found with this ID")
    try:
        relation = db_session.query(UserPermission) \
            .filter_by(user_id=user.id, permission_id=perm.id).one()
        db_session.delete(relation)
        cache.delete_key(userid=user.id,
                         action=perm.method,
                         resource=perm.path)
        LOGGER.info(f"permission {perm.name} for user {user.username} was revoked by {requester['username']}")
        MVUserPermission.refresh()
        db_session.commit()
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "User does not have this permission")
