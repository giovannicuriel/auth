# Redis cache configuration
# powered by flask-redis: https://github.com/underyx/flask-redis

from flask_redis import FlaskRedis
import redis
import logging

import conf
from .flaskAlchemyInit import app

from auth.healthcheck import HEALTHCHECK, ServiceStatus

LOGGER = logging.getLogger('auth.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.INFO)


if conf.cacheName == 'redis':
    REDIS_URL = ('redis://' + conf.cacheUser + ':' + conf.cachePdw
                 + '@' + conf.cacheHost + ':6379/' + conf.cacheDatabase)
    app.config['DBA_URL'] = REDIS_URL
    redis_store = FlaskRedis(app, config_prefix='DBA', strict=False,
                             encoding="utf-8", socket_keepalive=True,
                             charset="utf-8", decode_responses=True)
    HEALTHCHECK.redis_connection_monitor.trigger("connected", ServiceStatus.systemOk)

elif conf.cacheName == 'NOCACHE':
    LOGGER.warning("Warning. Cache policy set to NOCACHE."
                   "This may degrade PDP performance.")
    redis_store = None
    HEALTHCHECK.redis_connection_monitor.trigger("not used", ServiceStatus.systemOk)

else:
    LOGGER.error("Currently, there is no support for cache policy "
                 + conf.dbName)
    HEALTHCHECK.redis_connection_monitor.trigger("not supported", ServiceStatus.systemFail, f"no support for {conf.dbName}")
    exit(-1)


# create a cache key
def generate_key(userid, action, resource):
    # add a prefix to every key, to avoid colision with others aplications
    key = 'PDP;'
    key += str(userid) + ';' + action + ';' + resource
    return key


# utility function to get a value on redis
# return None if the value can't be found
def get_key(userid, action, resource):
    if redis_store:
        try:
            return redis_store.get(generate_key(userid, action, resource))
        except redis.exceptions.ConnectionError:
            LOGGER.warning("Failed to connect to redis")
            return None


def set_key(userid, action, resource, veredict):
    try:
       redis_store.setex(generate_key(
                                        userid,
                                        action,
                                        resource
                                      ),
                          conf.cacheTtl,   # time to live
                          str(veredict)
                          )
    except redis.exceptions.ConnectionError:
        LOGGER.warning("Failed to connect to redis")


# invalidate a key. may use regex patterns
def delete_key(userid='*', action='*', resource='*'):
    if redis_store:
        # python-RE and Redis use different wildcard representations
        action = action.replace('(.*)', '*')
        resource = resource.replace('(.*)', '*')
        # TODO: put the cache update on a worker thread
        key = generate_key(userid, action, resource)
        try:
            for dkey in redis_store.scan_iter(key):
                redis_store.delete(dkey)
        except redis.exceptions.ConnectionError:
            LOGGER.warning("Failed to connect to redis")
