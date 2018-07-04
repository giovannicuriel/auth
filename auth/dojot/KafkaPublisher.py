import base64
import requests
import logging
import json
from conf import kafka_subject, kafka_host, data_broker_host, dojot_management_tenant
from dojot.module import Messenger, Config, Log
import threading
import time

LOGGER = Log().color_log()

class Publisher(threading.Thread):
    messenger = None

    @classmethod
    def send_notification(cls, event):
        if cls.messenger is None:
            return

        LOGGER.debug("Publishing event: " + kafka_host + ", " + kafka_subject + ": " + json.dumps(event))
        try:
            cls.messenger.publish(kafka_subject, "dojot-management", event)
        except Exception as e:
            LOGGER.debug("Caught: " + str(e))
        finally:
            LOGGER.debug("data published")

    @classmethod
    def init(cls):
        if cls.messenger is not None:
            return

        LOGGER.debug("Initializing dojot.module")
        config = Config({
            "auth" : {
                "url": "http://localhost:5000",
                "connection_retries": 3,
                "timeout_sleep": 5
            }
        })

        LOGGER.debug("Config is:  " + json.dumps(config.auth))
        cls.messenger = Messenger("dojot.auth", config)
        LOGGER.debug(f"Creating tenant {dojot_management_tenant}...")
        LOGGER.debug(f"Current tenants are: {cls.messenger.tenants}.")
        cls.messenger.process_new_tenant(dojot_management_tenant, json.dumps({"tenant" : dojot_management_tenant}))
        LOGGER.debug("... tenant created.")
        LOGGER.debug("Creating channel " + kafka_subject)
        cls.messenger.create_channel(kafka_subject, "w")
        LOGGER.debug("... channel created.")
        LOGGER.debug("Initializing messenger")
        cls.messenger.init()
        LOGGER.debug("... messenger initialized.")

    def run(self):
        self.init()
