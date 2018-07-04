"""
This file contains function to create, search, update and
delete Users, groups and permissions
"""
import re
import sqlalchemy.orm.exc as orm_exceptions

import auth.controller.PasswordController as password
from auth.database.Models import Permission, User, Group, PermissionEnum, PermissionTypeEnum
import auth.controller.RelationshipController as rship
from auth.database.Models import UserPermission, GroupPermission, UserGroup
from auth.database.flaskAlchemyInit import HTTPRequestError
from auth.database.inputConf import UserLimits, PermissionLimits, GroupLimits
import auth.database.Cache as cache
import auth.database.historicModels as inactiveTables
import auth.conf as conf
import auth.kongUtils as kongUtils
from auth.database.flaskAlchemyInit import log
from auth.dojot.KafkaPublisher import Publisher
import auth.controller.PasswordController as pwdc
from auth.database.Models import MVUserPermission, MVGroupPermission

from dojot.module import Log

LOGGER = Log().color_log()

def check_user(user):
    """
    Helper function to check if user is valid (regardless where it is used)

    TODO Check whether this function really must return the same user. Wouldn't it be enough to throw exceptions?

    :param user: The user to be checked.
    :return: The same user
    """
    if not user.get('username', ""):
        raise HTTPRequestError(400, "Missing username")

    if len(user['username']) > UserLimits.username:
        raise HTTPRequestError(400, "Username too long")

    if re.match(r'^[a-z]+[a-z0-9_]', user['username']) is None:
        raise HTTPRequestError(400,
                               'Invalid username. Usernames should start with'
                               ' a letter and only lowercase,'
                               ' alphanumeric and underscores are allowed')

    if not user.get('service', ""):
        raise HTTPRequestError(400, "Missing service")
    if len(user['service']) > UserLimits.service:
        raise HTTPRequestError(400, "Service too long")
    if re.match(r'^[a-z0-9_]+$', user['username']) is None:
        raise HTTPRequestError(400,
                               'Invalid username, only alphanumeric'
                               ' and underscores allowed')

    if not user.get('email', ""):
        raise HTTPRequestError(400, "Missing email")
    if len(user['email']) > UserLimits.email:
        raise HTTPRequestError(400, "E-mail too long")
    if re.match(
            r'(^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$)',
            user['email']
    ) is None:
        raise HTTPRequestError(400, "Invalid e-mail address")

    if not user.get('name', ""):
        raise HTTPRequestError(400, "Missing user's name (full name)")
    if len(user['name']) > UserLimits.name:
        raise HTTPRequestError(400, "Name too long")

    return user


def create_user(db_session, user: User, requester):
    """
    Create a new user.
    :param db_session: The postgres db session to be used
    :param user: User The user to be created. This is a simple dictionary with all 'fillable' field
                 listed in Models.User class.
    :param requester: Who is creating this user. This is a dictionary with two keys:
                      "userid" and "username"
    :return: The result of creating this user.
    :raises HTTPRequestError: If username is already in use
    :raises HTTPRequestError: If e-mail is already in use
    :raises HTTPRequestError: If any problem occurs while configuring Kong
    """
    # Drop invalid fields
    user = {k: user[k] for k in user if k in User.fillable}
    LOGGER.debug("Checking user data...")
    check_user(user)
    LOGGER.debug("... user data is OK.")

    if not user.get('profile', ""):
        raise HTTPRequestError(400, "Missing profile")
    if len(user['profile']) > UserLimits.profile:
        raise HTTPRequestError(400, "Profile name too long")

    # Sanity checks
    # Check whether username and e-mail are unique.
    LOGGER.debug("Checking whether user already exist...")
    if db_session.query(User.id).filter_by(username=user['username']).one_or_none():
        LOGGER.warning("User already exists.")
        raise HTTPRequestError(400, f"Username {user['username']} is in use.")
    LOGGER.debug("... user doesn't exist.")

    LOGGER.debug("Checking whether user e-mail is already being used...")
    if db_session.query(User.id).filter_by(email=user['email']).one_or_none():
        LOGGER.warning("User e-mail is already being used.")
        raise HTTPRequestError(400, f"E-mail {user['email']} is in use.")

    LOGGER.debug("... user e-mail is not being used.")

    if conf.emailHost == '':
        user['salt'], user['hash'] = password.create_pwd(conf.temporaryPassword)

    # Last field to be filled automatically, before parsing
    user['created_by'] = requester['userid']

    # User structure is finished.
    LOGGER.debug("Creating user instance...")
    new_user = User(**user)
    LOGGER.debug("... user instance was created.")
    LOGGER.debug(f"User data is: {user['username']} created by {requester['username']}")

    # If no problems occur to create user (no exceptions), configure kong
    LOGGER.debug("Configuring Kong...")
    kong_data = kongUtils.configure_kong(new_user.username)
    if kong_data is None:
        LOGGER.warning("Could not configure Kong.")
        raise HTTPRequestError(500, 'failed to configure verification subsystem')
    LOGGER.debug("... Kong was successfully configured.")
    new_user.secret = kong_data['secret']
    new_user.key = kong_data['key']
    new_user.kongId = kong_data['kongid']

    # Add the new user to the database
    LOGGER.debug("Adding new user to database session...")
    db_session.add(new_user)
    LOGGER.debug("... new user was added to database session.")
    LOGGER.debug("Committing database changes...")
    db_session.commit()
    LOGGER.debug("... database changes were committed.")

    # Configuring groups and user profiles
    group_success = []
    group_failed = []
    LOGGER.debug("Configuring user profile...")
    if 'profile' in user.keys():
        group_success, group_failed = rship. \
            add_user_many_groups(db_session, new_user.id,
                                 user['profile'], requester)
        db_session.commit()
    LOGGER.debug("... user profile was configured.")

    LOGGER.debug("Configuring user password...")
    if conf.emailHost != 'NOEMAIL':
        try:
            pwdc.create_password_set_request(db_session, new_user)
            db_session.commit()
        except Exception as e:
            LOGGER.warning(e)
    LOGGER.debug("... user password was configured.")

    LOGGER.debug("Sending tenant creation message to other components...")
    if count_tenant_users(db_session, new_user.service) == 1:
        LOGGER.info(f"Will emit tenant lifecycle event {new_user.service} - CREATE")
        Publisher.send_notification({"type": 'CREATE', 'tenant': new_user.service})


    LOGGER.debug("... tenant creation message was sent.")
    ret = {
        "user": new_user.safe_dict(),
        "groups": group_success,
        "could not add": group_failed,
        "message": "user created"
    }
    return ret


def search_user(db_session, username: str = None) -> [User]:
    """
    Retrieves all users or only one particular user
    :param db_session: The opened session to postgres
    :param username: String username, if any.
    :return: A list of users currently in the database.
    If any name is provided, the user with that name (if any)
    :raises: HTTPRequestError if there is no users (or no such user)
    currently in the database.
    """
    # order the list of user by Name
    user_query = db_session.query(User).order_by(User.name)

    if username:
        user_query = user_query.filter(User.username.like('%' + username + '%'))

    users = user_query.all()
    if not users:
        raise HTTPRequestError(404, "No results found with these filters")
    return users


def get_user(db_session, user):
    try:
        user = User.get_by_name_or_id(user)
        return user
    except (orm_exceptions.NoResultFound, ValueError):
        raise HTTPRequestError(404, "No user found with this ID")


def update_user(db_session, user: str, updated_info, requester) -> (dict, str):
    """
    Updates all the information about a particular user.
    :param db_session: The postgres session to be used.
    :param user: The user ID to be updated.
    :param updated_info: The new data.
    :param requester: Who is requiring this update.
    :return: The old information (a dictionary containing the old information about the user
             and the old service.
    :raises HTTPRequestError: If the username is different from the original (this field cannot be updated).
    :raises HTTPRequestError: Can't edit service of the admin.
    """
    # Drop invalid fields
    updated_info = {k: updated_info[k] for k in updated_info if k in User.fillable}
    user = User.get_by_name_or_id(user)
    old_user = user.safe_dict()
    old_service = user.service

    if 'username' in updated_info.keys() \
            and updated_info['username'] != user.username:
        raise HTTPRequestError(400, "usernames can't be updated")

    # check_user function needs username.
    updated_info['username'] = user.username
    check_user(updated_info)

    # Verify if the email is in use by another user
    if 'email' in updated_info.keys() and updated_info['email'] != user.email:
        if db_session.query(User).filter_by(email=updated_info['email']).one_or_none():
            raise HTTPRequestError(400, "email already in use")

    LOGGER.info(f"user {user.username} updated by {requester['username']}")
    LOGGER.info({'oldUser': user.safe_dict(), 'newUser': updated_info})

    # the admin cant update service
    if 'service' in updated_info.keys() \
            and 'admin' == user.username and updated_info['service'] != 'admin':
        raise HTTPRequestError(405, "Can't edit service of admin")

    # Update all new data.
    if 'name' in updated_info.keys():
        user.name = updated_info['name']
    if 'service' in updated_info.keys():
        user.service = updated_info['service']
    if 'email' in updated_info.keys():
        user.email = updated_info['email']

    db_session.add(user)
    db_session.commit()

    # Publish messages related to service creation/deletion
    if count_tenant_users(db_session, old_service) == 0:
        LOGGER.info(f"will emit tenant lifecycle event {old_service} - DELETE")
        Publisher.send_notification({"type": 'DELETE', 'tenant': old_service})

    if count_tenant_users(db_session, user.service) == 1:
        LOGGER.info(f"will emit tenant lifecycle event {user.service} - CREATE")
        Publisher.send_notification({"type": 'CREATE', 'tenant': user.service})

    return old_user, old_service


def delete_user(db_session, username: str, requester):
    """
    Deletes an user from the system
    :param db_session: The postgres session to be used
    :param username: String The user to be removed
    :param requester: Who is creating this user. This is a dictionary with two keys:
                      "userid" and "username"
    :return: The removed user
    :raises HTTPRequestError: If the user tries to remove itself.
    :raises HTTPRequestError: Can't delete the admin user.
    :raises HTTPRequestError: If the user is not in the database.
    """
    try:
        user = User.get_by_name_or_id(username)
        if user.id == requester['userid']:
            raise HTTPRequestError(400, "a user can't remove himself")
        elif user.username == 'admin':
            raise HTTPRequestError(405, "Can't delete the admin user")

        db_session.execute(
            UserPermission.__table__.delete(UserPermission.user_id == user.id)
        )
        db_session.execute(
            UserGroup.__table__.delete(UserGroup.user_id == user.id)
        )
        cache.delete_key(userid=user.id)

        # The user is not hardDeleted.
        # it should be copied to inactiveUser table
        inactiveTables.PasswdInactive.createInactiveFromUser(db_session,
                                                             user, )
        inactiveTables.UserInactive.createInactiveFromUser(db_session,
                                                           user,
                                                           requester['userid'])
        password.expire_password_reset_requests(db_session, user.id)
        db_session.delete(user)
        LOGGER.info(f"user {user.username} deleted by {requester['username']}")
        LOGGER.info(user.safe_dict())

        kongUtils.remove_from_kong(user.username)
        MVUserPermission.refresh()
        MVGroupPermission.refresh()
        db_session.commit()

        if count_tenant_users(db_session, user.service) == 0:
            LOGGER.info(f"will emit tenant lifecycle event {user.service} - DELETE")
            Publisher.send_notification({"type": 'DELETE', 'tenant': user.service})

        return user
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No user found with this ID")


# Helper function to check permission fields
def check_perm(perm):
    if 'name' not in perm.keys() or len(perm['name']) == 0:
        raise HTTPRequestError(400, "Missing permission name")
    if len(perm['path']) > PermissionLimits.path:
        raise HTTPRequestError(400, "Path too long")
    if re.match(r'^[a-z]+[a-z0-9_]', perm['name']) is None:
        raise HTTPRequestError(400,
                               'Invalid name. permission names should start'
                               ' with a letter and only lowercase,'
                               ' alhpanumeric and underscores are allowed')

    if 'permission' in perm.keys():
        if perm['permission'] not in [p.value for p in PermissionEnum]:
            raise HTTPRequestError(400,
                                   "An access control rule can not return '"
                                   + perm['permission']
                                   + "'")
    else:
        # Default value if permission is omitted
        perm['permission'] = 'permit'

    if 'path' not in perm.keys() or len(perm['path']) == 0:
        raise HTTPRequestError(400, "Missing permission Path")
    if len(perm['path']) > PermissionLimits.path:
        raise HTTPRequestError(400, "Path too long")

    if 'method' not in perm.keys() or len(perm['method']) == 0:
        raise HTTPRequestError(400, "Missing permission method")
    if len(perm['method']) > PermissionLimits.method:
        raise HTTPRequestError(400, "Method too long")

    try:
        re.match(r'(^' + perm['method'] + ')', "")
    except re.error:
        raise HTTPRequestError(400, perm['method']
                               + " is not a valid regular expression.")

    try:
        re.match(r'(^' + perm['path'] + ')', "")
    except re.error:
        raise HTTPRequestError(400, perm['method']
                               + " is not a valid regular expression.")


def create_perm(db_session, permission, requester):
    """
    Creates a new permission
    :param db_session: The postgres session to be used
    :param permission: The new permission
    :param requester: Who is creating this user. This is a dictionary with two keys:
                      "userid" and "username"
    :return: The new permission
    """
    # Drop invalid fields
    permission = {k: permission[k] for k in permission if k in Permission.fillable}
    check_perm(permission)
    permission['created_by'] = requester['userid']
    perm = Permission(**permission)
    LOGGER.info(f"permission {perm.name} create by {requester['username']}")
    LOGGER.info(perm.safe_dict())

    db_session.add(perm)
    db_session.commit()
    return perm


def search_perm(db_session, path=None, method=None, permission=None, type=None):
    """
    Retrieves a set of permissions from database.
    :param db_session: The postgres session to be used.
    :param path: Permission path, if any.
    :param method: Permission allowed methods, if any.
    :param permission: Permission verb (permit or deny), if any.
    :return:
    """
    perm_query = db_session.query(Permission)

    if path:
        perm_query = perm_query.filter(Permission.path.like(f"%{path}%"))

    if method:
        perm_query = perm_query.filter(
            Permission.method.like(f"%{method}%"))

    if permission:
        if permission not in [p.value for p in PermissionEnum]:
            raise HTTPRequestError(400, f"Invalid filter. Permission can't be {permission}")
        perm_query = perm_query.filter_by(permission=permission)

    if type:
        if type not in [p.value for p in PermissionTypeEnum]:
            raise HTTPRequestError(400, f"Invalid filter. Permission type can't be {type}")
        perm_query = perm_query.filter_by(type=type)

    perms = perm_query.all()
    if not perms:
        raise HTTPRequestError(404, "No results found with these filters")
    return perms


def get_perm(db_session, permission):
    try:
        perm = Permission.get_by_name_or_id(permission)
        return perm
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No permission found with this ID")


def update_perm(db_session, permission: str, perm_data, requester):
    """
    Updates all information about a permission (excluding name and ID, of course).
    :param db_session: The postgres session to be used.
    :param permission: String The permission name or ID.
    :param perm_data: New information for this permission.
    :param requester: Who is creating this user. This is a dictionary with two keys:
                      "userid" and "username".
    :return:
    :raises HTTPRequestError: Can't edit a system permission.
    """
    perm_data = {k: perm_data[k] for k in perm_data if k in Permission.fillable}

    check_perm(perm_data)
    try:
        perm = Permission.get_by_name_or_id(permission)
        if perm.type == PermissionTypeEnum.api:
            if 'name' in perm_data.keys() and perm.name != perm_data['name']:
                raise HTTPRequestError(400, "permission name can't be changed")
            for key, value in perm_data.items():
                setattr(perm, key, value)
            db_session.add(perm)
            LOGGER.info(f"permission {perm.name} updated by {requester['username']}")
            LOGGER.info(perm_data)

            db_session.commit()
        else:
            raise HTTPRequestError(405, "Can't edit a system permission ")
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No permission found with this ID")


def delete_perm(db_session, permission: str, requester):
    """
    Removes a permission from the system
    :param db_session: The postgres session to be used.
    :param permission: String The permission to be removed (name or ID).
    :param requester: Who is creating this user. This is a dictionary with two keys:
                      "userid" and "username".
    :return:
    :raises HTTPRequestError: Can't delete a system permission.
    """
    try:
        perm = Permission.get_by_name_or_id(permission)
        if perm.type == PermissionTypeEnum.api:
            db_session.execute(
                UserPermission.__table__.delete(UserPermission.permission_id == perm.id)
            )
            db_session.execute(
                GroupPermission.__table__.delete(GroupPermission.permission_id == perm.id)
            )
            cache.delete_key(action=perm.method, resource=perm.path)
            LOGGER.info(f"permission {perm.name} deleted by {requester['username']}")
            LOGGER.info(perm.safe_dict())
            db_session.delete(perm)
            db_session.commit()
            MVUserPermission.refresh()
            MVGroupPermission.refresh()
        else:
            raise HTTPRequestError(405, "Can't delete a system permission")
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No permission found with this ID or name")


def check_group(group):
    if not group.get('name', ""):
        raise HTTPRequestError(400, 'Missing group name')
    if len(group['name']) > GroupLimits.name:
        raise HTTPRequestError(400, "Group name too long")

    if re.match(r'^[a-zA-Z0-9]+$', group['name']) is None:
        raise HTTPRequestError(400,
                               'Invalid group name, only alphanumeric allowed')

    if 'desc' in group.keys() and len(group['desc']) > GroupLimits.description:
        raise HTTPRequestError(400, "Group description is too long")


def create_group(db_session, group_data, requester):
    """
    Create a new group
    :param db_session: The postgres session to be used.
    :param group_data: The group data. This is a simple dictionary with "name" and
                       "description" keys.
    :param requester: Who is creating this user. This is a dictionary with two keys:
                      "userid" and "username".
    :return: The new group.
    """
    group_data = {k: group_data[k] for k in group_data if k in Group.fillable}
    check_group(group_data)

    if db_session.query(Group.name).filter_by(name=group_data['name']).one_or_none():
        raise HTTPRequestError(400, f"Group name {group_data['name']} is in use.")

    group_data['created_by'] = requester['userid']
    group = Group(**group_data)
    LOGGER.info(f"group {group.name} created by {requester['username']}")
    LOGGER.info(group.safe_dict())
    db_session.add(group)
    db_session.commit()
    return group


def search_group(db_session, name=None):
    """
    Searches a particular group or a set of groups.
    :param db_session:
    :param name: Group name
    :return:
    """
    # Order by Name
    group_query = db_session.query(Group).order_by(Group.name)
    if name:
        group_query = group_query.filter(Group.name.like('%' + name + '%'))

    groups = group_query.all()
    if not groups:
        raise HTTPRequestError(404, "No results found with these filters")

    return groups


def get_group(db_session, group):
    try:
        group = Group.get_by_name_or_id(group)
        return group
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No group found with this ID")


def update_group(db_session, group, group_data, requester):
    group_data = {k: group_data[k] for k in group_data if k in Group.fillable}
    check_group(group_data)
    try:
        group = Group.get_by_name_or_id(group)

        if group.name == 'admin':
            raise HTTPRequestError(405, "Can't edit admin group")

        for key, value in group_data.items():
            setattr(group, key, value)
        db_session.add(group)
        LOGGER.info('group ' + group.name + ' updated by '
                   + requester['username'],
                   group_data)
        db_session.commit()
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No group found with this ID")


def delete_group(db_session, group, requester):
    try:
        group = Group.get_by_name_or_id(group)

        if group.name == 'admin':
            raise HTTPRequestError(405, "Can't delete admin group")

        db_session.execute(
            GroupPermission.__table__.delete(GroupPermission.group_id == group.id)
        )
        db_session.execute(
            UserGroup.__table__.delete(UserGroup.group_id == group.id)
        )
        cache.delete_key()
        LOGGER.info('group ' + group.name + ' deleted by '
                   + requester['username'],
                   group.safe_dict())
        db_session.delete(group)
        MVGroupPermission.refresh()
        db_session.commit()
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No group found with this ID")


def count_tenant_users(db_session, tenant):
    try:
        return db_session.query(User).filter(User.service == tenant).count()
    except orm_exceptions.NoResultFound:
        return 0


def list_tenants(db_session):
    try:
        tenants = []
        for tenant in db_session.query(User.service).distinct():
            tenants.append(tenant[0])
        return tenants
    except orm_exceptions.NoResultFound:
        raise HTTPRequestError(404, "No registered tenants found")
