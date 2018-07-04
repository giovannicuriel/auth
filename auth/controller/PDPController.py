import re

from auth.database.Models import PermissionEnum, UserGroup
from auth.database.Models import MVUserPermission, MVGroupPermission
from auth.database.flaskAlchemyInit import HTTPRequestError
from auth.controller.AuthenticationController import get_jwt_payload
import auth.database.Cache as cache
from auth.database.flaskAlchemyInit import log
from dojot.module import Log

LOGGER = Log().color_log()


# Helper function to check request fields
def check_request(pdp_request):
    if 'action' not in pdp_request.keys() or len(pdp_request['action']) == 0:
        raise HTTPRequestError(400, "Missing action")

    if 'jwt' not in pdp_request.keys() or len(pdp_request['jwt']) == 0:
        raise HTTPRequestError(400, "Missing JWT")

    if 'resource' not in pdp_request.keys() or len(pdp_request['resource']) == 0:
        raise HTTPRequestError(400, "Missing resource")


def pdp_main(db_session, pdp_request):
    check_request(pdp_request)
    jwt_payload = get_jwt_payload(pdp_request['jwt'])
    user_id = jwt_payload['userid']

    # try to retrieve the veredict from cache
    cached_veredict = cache.get_key(user_id, pdp_request['action'],
                                    pdp_request['resource'])
    # Return the cached answer if it exist
    if cached_veredict:
        LOGGER.info('user ' + str(user_id) + ' '
                   + cached_veredict + ' to ' + pdp_request['action']
                   + ' on ' + pdp_request['resource'] + ' from cache')
        return cached_veredict


    user_groups = [g.group_id for g in UserGroup.query.filter_by(user_id=user_id).all()]

    veredict = iterate_permissions(user_id,
                                   user_groups,
                                   pdp_request['action'],
                                   pdp_request['resource'])
    # Registry this veredict on cache
    cache.set_key(user_id,
                  pdp_request['action'],
                  pdp_request['resource'],
                  veredict)

    LOGGER.info('user ' + str(user_id) + ' '
               + veredict + ' to ' + pdp_request['action']
               + ' on ' + pdp_request['resource'] + ' registered on cache')
    return veredict


def iterate_permissions(user_id, groups_list, action, resource):
    permit = False

    # check user direct permissions
    for p in MVUserPermission.query.filter_by(user_id=user_id):
        LOGGER.info('checking for user permissions')
        granted = make_decision(p, action, resource)
        # user permissions have precedence over group permissions
        if granted != PermissionEnum.notApplicable:
            return granted.value

    # check user group permissions
    for g in groups_list:
        for p in MVGroupPermission.query.filter_by(group_id=g):
            LOGGER.info('checking for group permissions')
            granted = make_decision(p, action, resource)
            # deny have precedence over permits
            if granted == PermissionEnum.deny:
                return granted.value
            elif granted == PermissionEnum.permit:
                permit = True

    if permit:
        return PermissionEnum.permit.value
    else:
        return PermissionEnum.deny.value


# Receive a Permissions and try to match the Given
# path + method with it. Return 'permit' or 'deny' if succed matching.
# return 'notApplicable' otherwise
def make_decision(permission, method, path):
    # if the Path and method Match
    if re.match(r'(^' + permission.path + ')', path) is not None:
        if re.match(r'(^' + permission.method + ')', method):
            return permission.permission
    return PermissionEnum.notApplicable
