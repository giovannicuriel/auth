# This file contains the default configuration values
# and configuration retrieval functions

import logging
import os

LOGGER = logging.getLogger("auth." + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.INFO)

# database related configuration
db_name = os.environ.get("AUTH_DB_NAME", "dojot_auth")
db_user = os.environ.get("AUTH_DB_USER", "kong")
db_password = os.environ.get("AUTH_DB_PWD", "")
db_address = os.environ.get("AUTH_DB_ADDRESS", "postgres")
db_port = os.environ.get("AUTH_DB_PORT", 5432)
db_host = f"{db_address}:{db_port}"
create_database = os.environ.get("AUTH_DB_CREATE", True)


# cache related configuration
cache_name = os.environ.get("AUTH_CACHE_NAME", "redis")
cache_user = os.environ.get("AUTH_CACHE_USER", "redis")
cache_pdw = os.environ.get("AUTH_CACHE_PWD", "")
cache_address = os.environ.get("AUTH_CACHE_ADDRESS", "redis")
cache_port = os.environ.get("AUTH_CACHE_PORT", 6379)
cache_host = f"{cache_address}:{cache_port}"
cache_ttl = int(os.environ.get("AUTH_CACHE_TTL", 720))
cache_database = os.environ.get("AUTH_CACHE_DATABASE", "0")
cache_url = f"redis://{cache_user}:{cache_pdw}@{cache_host}/{cache_database}"

# kong related configuration
kongURL = os.environ.get("KONG_URL", "http://kong:8001")


# JWT token related configuration
tokenExpiration = int(os.environ.get("AUTH_TOKEN_EXP", 420))

# email related configuration
emailHost = os.environ.get("AUTH_SMTP_ADDRESS", "")
emailPort = int(os.environ.get("AUTH_SMTP_PORT", 587))
emailTLS = (os.environ.get("AUTH_SMTP_TLS", "true") in
            ["true", "True", "TRUE"])
emailUsername = os.environ.get("AUTH_SMTP_USER", "")
emailPasswd = os.environ.get("AUTH_SMTP_PASSWD", "")

# if you are using a front end with Auth,
# define this link to point to the password reset view on you FE
resetPwdView = os.environ.get("AUTH_RESET_PWD_VIEW", "")

# if AUTH_SMTP_ADDRESS is set to an empty string a temporary password is given
# to new users
temporaryPassword = os.environ.get("AUTH_USER_TMP_PWD", "temppwd")


# password policies configuration
# time to expire an password reset link in minutes
passwdRequestExpiration = int(os.environ.get("AUTH_PASSWD_REQUEST_EXP", 30))
# how many passwords should be check on the user history
# to enforce no password repetition policy
passwdHistoryLen = int(os.environ.get("AUTH_PASSWD_HISTORY_LEN", 4))

passwdMinLen = int(os.environ.get("AUTH_PASSWD_MIN_LEN", 8))


password_blackList = os.environ.get("AUTH_PASSWD_BLACKLIST",
                                    "password_blacklist.txt")


logMode = os.environ.get("AUTH_SYSLOG", "STDOUT")


# make some configuration checks
# and warn if dangerous configuration is found
if emailHost == "":
    LOGGER.warning("AUTH_SMTP_ADDRESS is not set. This is unsafe"
                   " and there is no way to reset users forgotten password")
else:
    if not emailUsername or not emailPasswd:
        LOGGER.warning("Invalid configuration: No AUTH_SMTP_USER or "
                       "AUTH_SMTP_PASSWD defined although a AUTH_SMTP_ADDRESS "
                       "was defined")

    if not emailTLS:
        LOGGER.warning("Using e-mail without TLS is not safe")

if passwdMinLen < 6:
    LOGGER.warning("Password minlen cannot be less than 6.")
    passwdMinLen = 6

# Kafka configuration
kafka_address = os.environ.get("KAFKA_ADDRESS", "kafka")
kafka_port = os.environ.get("KAFKA_PORT", 9092)
kafka_host = f"{kafka_address}:{kafka_port}"

# Global subject to use when publishing tenancy lifecycle events
dojot_subject_tenancy = os.environ.get("DOJOT_SUBJECT_TENANCY", "dojot.tenancy")

# Global service to use when publishing dojot management events
# such as new tenants
dojot_service_management = os.environ.get("DOJOT_SERVICE_MANAGEMENT",
                                          "dojot-management")


dojot_management_tenant = os.environ.get('DOJOT_MANAGEMENT_TENANT', "dojot-management")
dojot_management_user = os.environ.get('DOJOT_MANAGEMENT_USER', "auth")

# Kafka topic (subject) manager
data_broker_host = os.environ.get("DATA_BROKER_URL", "http://data-broker")

rabbitmq_address = os.environ.get("RABBITMQ_ADDRESS", "rabbitmq")
rabbitmq_port = os.environ.get("RABBITMQ_PORT", 15672)
rabbitmq_host = f"{rabbitmq_address}:{rabbitmq_port}"
