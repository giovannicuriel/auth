import dredd_hooks as hooks
import json
import auth.controller.CRUDController as crud
from auth.database.flaskAlchemyInit import db
from auth.database.flaskAlchemyInit import HTTPRequestError
from crud_api_hook import create_sample_groups


@hooks.before("Auth > Known users manipulation > Register a new user")
def create_groups_for_user(transaction):
    create_sample_groups(transaction)


@hooks.before("Auth > Session management > Create session")
def create_sample_users(transaction):

    group_id = create_sample_groups(transaction)

    user = {
        "name": "testadm",
        "username": "testadm",
        "service": "admin",
        "email": "testadm@noemail.com",
        "profile": "testadm"
    }
    requester = {
        "userid": 0,
        "username": "dredd"
    }

    user_id = []

    try:
        results = crud.create_user(db.session, user, requester)
        user_id.append(results["user"]["id"])
        print(f"Results are: {results}")
    except HTTPRequestError as e:
        print(f"Error: {e.message}")

    user = {
        "name": "test",
        "username": "test",
        "service": "test",
        "email": "test@noemail.com",
        "profile": "testuser"
    }

    try:
        results = crud.create_user(db.session, user, requester)
        user_id.append(results["user"]["id"])
        print(f"Results are: {results}")
    except HTTPRequestError as e:
        print(f"Error: {e.message}")
    return user_id, group_id

@hooks.before("Auth > Session management > Create session")
def change_user_password(transaction):
    body = json.loads(transaction['request']['body'])
    body['passwd'] = 'temppwd'
    transaction['request']['body'] = json.dumps(body)


@hooks.before("Auth > Known users manipulation > List known users")
@hooks.before("Auth > Individual user settings > Get user info")
@hooks.before("Auth > Individual user settings > Update user info")
@hooks.before("Auth > Individual user settings > Remove user")
def change_user_id(transaction):
    user_id, group_id = create_sample_users(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace('1', f'{user_id[0]}')


