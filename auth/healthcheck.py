from dojot.module.healthcheck import DynamicServiceInfo, HealthChecker, DynamicComponentsDetails, ServiceStatus
import logging
import traceback
LOGGER = logging.getLogger('auth.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)

class AuthHealthCheck:
    def __init__(self):
        self.service_info = DynamicServiceInfo(
            service_id="dojot.auth",
            status=ServiceStatus.systemWarning,
            detail={}
        )
        self.healthChecker = HealthChecker(self.service_info)
        kafka_producer = DynamicComponentsDetails(
            status=ServiceStatus.systemWarning,
            component_name="dojot.auth.kafka.producer",
            measurement_name="status"
        )
        password_compilation = DynamicComponentsDetails(
            status=ServiceStatus.systemWarning,
            component_name="dojot.auth.passwords",
            measurement_name="status"
        )
        redis_connection = DynamicComponentsDetails(
            status=ServiceStatus.systemWarning,
            component_name="dojot.auth.redis",
            measurement_name="status"
        )

        self.kafka_producer_monitor = self.healthChecker.create_monitor(kafka_producer)
        self.password_compilation_monitor = self.healthChecker.create_monitor(password_compilation)
        self.redis_connection_monitor = self.healthChecker.create_monitor(redis_connection)

        self.kafka_producer_monitor.trigger("starting", ServiceStatus.systemWarning)
        self.password_compilation_monitor.trigger("starting", ServiceStatus.systemWarning)
        self.redis_connection_monitor.trigger("starting", ServiceStatus.systemWarning)

    instance = None

    @classmethod
    def getInstance(cls):
        if cls.instance == None:
            cls.instance = AuthHealthCheck()
        return cls.instance

HEALTHCHECK = AuthHealthCheck.getInstance()
