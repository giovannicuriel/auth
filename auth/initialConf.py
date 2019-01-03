#!/usr/bin/python3
# This script creates the initial groups, permissions and users

import binascii
import os
from time import sleep
from pbkdf2 import crypt

from sqlalchemy import exc as sqlalchemy_exceptions
import psycopg2

from database.flaskAlchemyInit import db
from database.Models import *
from database.historicModels import *
from database.materialized_view_factory import *
import conf as CONFIG

import kongUtils as kong

from auth.healthcheck import HEALTHCHECK, ServiceStatus

def create_users():
    predef_users = [
        {
            "name": "Admin (superuser)",
            "username": "admin",
            "service": "admin",
            "email": "admin@noemail.com",
            "profile": "admin",
            "passwd": "admin"
        }
    ]

    for user in predef_users:
        # check if the user already exists
        # if the user exist, chances are this scrip has been run before
        print("Querying database for user {}".format(user))
        another_user = db.session.query(User.id) \
                                .filter_by(username=user['username']) \
                                .one_or_none()
        if another_user:
            print("This is not the first container run. Skipping")
            exit(0)
        print("Database access returned.")

        # mark the user as automatically created
        user['created_by'] = 0

        # hash the password
        user['salt'] = str(binascii.hexlify(os.urandom(8)), 'ascii')
        user['hash'] = crypt(user['passwd'],
                             user['salt'],
                             1000).split('$').pop()
        del user['passwd']
        print("Creating a new instance of this user.")
        new_user = User(**user)
        print("New instance created.")

        # configure kong shared secret
        kong_data = kong.configure_kong(new_user.username)
        if kong_data is None:
            print('failed to configure verification subsystem')
            exit(-1)
        new_user.secret = kong_data['secret']
        new_user.key = kong_data['key']
        new_user.kongId = kong_data['kongid']
        db.session.add(new_user)
    db.session.commit()


def create_groups():
    predef_groups = [
        {
            "name": "admin",
            "description": "Group with the highest access privilege"
        },
        {
            "name": "user",
            "description": "This groups can do anything, except manage users"
        }
    ]
    for g in predef_groups:
        # mark the group as automatically created
        g['created_by'] = 0
        group = Group(**g)
        db.session.add(group)
    db.session.commit()


# A utility function to create a permission dict
# so the List 'predefPerms' get less verbose
def permission_dict_helper(name, path, method, permission=PermissionEnum.permit, type_perm=PermissionTypeEnum.system):
    return {
        "name": name,
        "path":  path,
        "method": method,
        "permission": permission,
        "type": type_perm,
        "created_by": 0
    }


def create_permissions():
    predef_perms = [
        permission_dict_helper('all_all', "/(.*)", "(.*)"),
        permission_dict_helper('all_template', "/template/(.*)", "(.*)"),
        permission_dict_helper('ro_template', "/template/(.*)", "GET"),
        permission_dict_helper('all_device', "/device/(.*)", "(.*)"),
        permission_dict_helper('ro_device', "/device/(.*)", "GET"),
        permission_dict_helper('all_flows', "/flows/(.*)", "(.*)"),
        permission_dict_helper('ro_flows', "/flows/(.*)", "GET"),
        permission_dict_helper('all_history', "/history/(.*)", "(.*)"),
        permission_dict_helper('ro_history', "/history/(.*)", "GET"),
        permission_dict_helper('all_metric', "/metric/(.*)", "(.*)"),
        permission_dict_helper('ro_metric', "/metric/(.*)", "GET"),
        permission_dict_helper('all_user', "/auth/user/(.*)", "(.*)"),
        permission_dict_helper('ro_user', "/auth/user/(.*)", "GET"),
        permission_dict_helper('all_pap', "/pap/(.*)", "(.*)"),
        permission_dict_helper('ro_pap', "/pap/(.*)", "GET"),
        permission_dict_helper('ro_ca', "/ca/(.*)", "GET"),
        permission_dict_helper('wo_sign', "/sign/(.*)", "POST"),
        permission_dict_helper('ro_socketio', "/stream/socketio/", "GET"),
        permission_dict_helper('ro_import', "/import/(.*)", "GET"),
        permission_dict_helper('all_import', "/import/(.*)", "(.*)"),
        permission_dict_helper('ro_export', "/export/(.*)", "GET"),
        permission_dict_helper('all_export', "/export/(.*)", "(.*)"),
        permission_dict_helper('ro_image', "/fw-image/(.*)", "GET"),
        permission_dict_helper('all_image', "/fw-image/(.*)", "(.*)")
    ]

    for p in predef_perms:
        perm = Permission(**p)
        db.session.add(perm)
    db.session.commit()


def add_user_groups():
    predef_user_group = [
        {
            "name": "admin",
            "groups": ["admin"]
        },
    ]

    for user in predef_user_group:
        user_id = User.get_by_name_or_id(user['name']).id
        for group_name in user['groups']:
            r = UserGroup(user_id=user_id,
                          group_id=Group.get_by_name_or_id(group_name).id)
            db.session.add(r)
    db.session.commit()


def add_permissions_group():
    predef_group_perm = [
        {
            "name": "admin",
            "permission": [
                'all_all'
            ]
        },
        {
            "name": "user",
            "permission": [
                'all_template',
                'all_device',
                'all_flows',
                'all_history',
                'all_metric',
                'ro_ca',
                'wo_sign',
                "ro_socketio",
                "all_import",
                "all_export",
                "all_image"
            ]
        }
    ]

    for group in predef_group_perm:
        group_id = Group.get_by_name_or_id(group['name']).id
        for perm in group['permission']:
            perm_id = Permission.get_by_name_or_id(perm).id
            r = GroupPermission(group_id=group_id, permission_id=perm_id)
            db.session.add(r)

    db.session.commit()


def populate():
    print("Creating initial user and permission...")
    try:
        print("Creating users")
        create_users()
        print("Creating groups")
        create_groups()
        print("Creating permissions")
        create_permissions()
        print("Adding permissions to groups")
        add_permissions_group()
        print("Adding users to groups")
        add_user_groups()
    except sqlalchemy_exceptions.DBAPIError as err:
        print("Could not connect to the database.")
        print(err)
        exit(-1)

    # refresh views
    MVUserPermission.refresh()
    MVGroupPermission.refresh()
    db.session.commit()
    print("Success")

def create_database(num_retries=10, interval=3):
    connection = None

    attempt = 0
    while attempt < num_retries:
        try:
            connection = psycopg2.connect(user=CONFIG.dbUser, password=CONFIG.dbPdw, host=CONFIG.dbHost)
            print ("postgres ok")
            break
        except Exception as e:
            print("Failed to connect to database")

        attempt += 1
        sleep(interval)

    if connection is None:
        print("Database took too long to boot. Giving up.")
        exit(1)

    if CONFIG.createDatabase:
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute("select true from pg_database where datname = '%s';" % CONFIG.dbName)
        if len(cursor.fetchall()) == 0:
            print("will attempt to create database")
            cursor.execute("CREATE database %s;" % CONFIG.dbName)
            print("creating schema")
            db.create_all()
        else:
            print("Database already exists")


create_database()
populate()