"""
 This file purpose is to configure Flask with Alchemy
 Also, some generic HTTP formatter functions are provided
 There is also a generic exception class for HTTP errors
 This code should be kept independent of the other modules
 so it can be reused in any Flask + Alchemy project
"""

import json
import logging
from flask import Flask
from flask import make_response as fmake_response
from flask_sqlalchemy import SQLAlchemy
from logging.handlers import SysLogHandler
import auth.conf as dbconf


# Make the initial flask + alchem configuration
app = Flask(__name__)
app.url_map.strict_slashes = False

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')


# create a logger for our application
print("dbconf: {}".format(json.dumps(dbconf.db_name)))
if dbconf.logMode == 'STDOUT':
    streamLogger = logging.StreamHandler()
    streamLogger.setFormatter(formatter)
    app.logger.addHandler(streamLogger)

elif dbconf.logMode == 'SYSLOG':
    sysLogHandler = SysLogHandler('/dev/log')
    sysLogHandler.setFormatter(formatter)
    app.logger.addHandler(sysLogHandler)

else:
    print('Unknow log mode' + dbconf.logMode + '. Aborting')
    exit(-1)

app.logger.setLevel(logging.DEBUG)

# Select database driver
app.config['SQLALCHEMY_DATABASE_URI'] = "postgres+psycopg2://{}:{}@{}/{}".format(
    dbconf.db_user, dbconf.db_password, dbconf.db_host, dbconf.db_name
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class HTTPRequestError(Exception):
    def __init__(self, error_code, message):
        self.message = message
        self.errorCode = error_code


# Utility function for HTTP responses
def make_response(payload, status):
    resp = fmake_response(payload, status)
    resp.headers['content-type'] = 'application/json'
    return resp


def format_response(status, message=None):
    if message:
        payload = json.dumps({'message': message, 'status': status})
    elif 200 <= status < 300:
        payload = json.dumps({'message': 'ok', 'status': status})
    else:
        payload = json.dumps({'message': 'Request failed', 'status': status})
    return make_response(payload, status)


def load_json_from_request(request):
    if request.mimetype != 'application/json':
        raise HTTPRequestError(400, 'invalid mimetype')

    return request.get_json()


# with this function the logger type is transparent for the application
def log():
    return app.logger
