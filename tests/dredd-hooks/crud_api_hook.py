import dredd_hooks as hooks
import json
import auth.controller.CRUDController as crud
from auth.database.flaskAlchemyInit import db
from auth.database.flaskAlchemyInit import HTTPRequestError


@hooks.before("CRUD Permissions and Group > Permissions creation and search > Search permission")
def create_sample_perms(transaction):
    permission = {
        "path": "/devices/info/\\*",
        "method": "POST",
        "permission": "permit",
        "name": "sample_permission"
    }
    requester = {
        "userid": 0,
        "username": "dredd"
    }

    perm_id = 0
    try:
        results = crud.create_perm(db.session, permission, requester)
        perm_id = results.id
        print(f"Results: {results.safe_dict()}")
    except HTTPRequestError as e:
        print(f"Error: {e.message}")

    permission = {
        "path": "/auth/user",
        "method": "\\*",
        "permission": "deny",
        "name": "deny_user_access"
    }

    try:
        results = crud.create_perm(db.session, permission, requester)
        print(f"Results: {results.safe_dict()}")
    except HTTPRequestError as e:
        print(f"Error: {e.message}")
    return perm_id


@hooks.before("CRUD Permissions and Group > Permissions management > Get a permission")
@hooks.before("CRUD Permissions and Group > Permissions management > Update a permission")
@hooks.before("CRUD Permissions and Group > Permissions management > Remove a permission")
def create_sample_perms_with_references(transaction):
    perm_id = create_sample_perms(transaction)
    transaction["fullPath"] = transaction["fullPath"].replace("1", f"{perm_id}")


@hooks.before("CRUD Permissions and Group > Group creation > Search Groups")
def create_sample_groups(transaction):
    requester = {
        "userid": 0,
        "username": "dredd"
    }
    group = {
        "name": "testadm",
        "description": "admin"
    }

    group_id = []
    try:
        results = crud.create_group(db.session, group, requester)
        group_id.append(results.id)
        print(f"Results are: {results.safe_dict()}")
    except HTTPRequestError as e:
        print(f"Error: {e.message}")

    group = {
        "name": "commontest",
        "description": "Group for common users"
    }

    try:
        results = crud.create_group(db.session, group, requester)
        group_id.append(results.id)
        print(f"Results are: {results.safe_dict()}")
    except HTTPRequestError as e:
        print(f"Error: {e.message}")

    group = {
        "name": "testnew",
        "description": "Group for common users"
    }

    try:
        results = crud.create_group(db.session, group, requester)
        group_id.append(results.id)
        print(f"Results are: {results.safe_dict()}")
    except HTTPRequestError as e:
        print(f"Error: {e.message}")

    return group_id


@hooks.before("CRUD Permissions and Group > Group management > Get a group")
@hooks.before("CRUD Permissions and Group > Group management > Update a group")
@hooks.before("CRUD Permissions and Group > Group management > Remove a group")
def create_sample_groups_with_reference(transaction):
    group_id = create_sample_groups(transaction)
    transaction["fullPath"] = transaction["fullPath"].replace("1", f"{group_id[0]}")
