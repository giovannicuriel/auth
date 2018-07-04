import auth.conf as conf
from alarmlibrary.connection import RabbitMqClientConnection
from alarmlibrary.alarm import Alarm, AlarmSeverity
from auth.database.flaskAlchemyInit import log
from auth.database.flaskAlchemyInit import HTTPRequestError

from dojot.module import Log

LOGGER = Log().color_log()

class RabbitManager(object):
    def __init__(self, target=conf.rabbitmq_host):
        self.target = target
        self.client = None

    def getClient(self):
        if self.client is not None:
            return self.client

        if self.target != "":
            try:
                self.client = RabbitMqClientConnection()
                self.client.open(self.target)
                return self.client
            except Exception as error:
                print("failed to create rabbit connection, ignoring alarm {}".format(error))
                return None

rabbit = RabbitManager()

class AlarmError(HTTPRequestError):

    def __init__(self, error_code, message, username, userid=0):
        """
        Publish an alarm for the HTTP2ALARM posible error codes
        """
        super().__init__(error_code, message)

        HTTP2ALARM = {
            401 : "AuthenticationError",
            403 : "AuthorizationError"
        }

        if error_code in HTTP2ALARM:
            alarm = Alarm(namespace="dojot.auth", severity=AlarmSeverity.Minor,
                          domain=HTTP2ALARM[error_code],
                          description=message)
            alarm.add_primary_subject("instance_id", "1")
            alarm.add_primary_subject("module_name", "Authentication Module")
            alarm.add_additional_data("reason", message)
            alarm.add_additional_data("username", username)
            if error_code == 401:
                alarm.add_additional_data("userid", userid)
            rabbit_client = rabbit.getClient()
            if rabbit_client is not None:
                try:
                    rabbit_client.send(alarm)
                except Exception as ex:
                    LOGGER.error("There was a problem with RabbitMQ connection. Error is: {}".format(ex))
                    LOGGER.error("No alarm was sent.")

