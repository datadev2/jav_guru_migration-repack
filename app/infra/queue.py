from celery import Celery

from app.config import config


queue = Celery(broker=config.REDIS_DSN.unicode_string(), include=["app.infra.worker"])

queue.conf.worker_pool_restarts = True
queue.conf.broker_connection_retry_on_startup = True
queue.conf.broker_heartbeat = 0
