from celery import Celery, shared_task
from celery.schedules import crontab
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from .zentra import zentraReader
from .gefs import dataBaseWriter
from .models import ZentraDevice
from django.conf import settings

app = Celery()


import logging

logger = logging.getLogger(__name__)


@shared_task(name="calculations.hello_celery")
def hello_celery():
    """
    This is an example of a task that can be scheduled via celery.
    """
    logger.info("Hello logging from celery!")


# prepare GEFS data
dt = float(settings.GEFS_TIME_STEP)
forecastDays = int(settings.GEFS_FORECAST_DAYS)
dataBaseWriter(dt=dt, forecastDays=forecastDays)

# prepare Zentra Cloud data
stationSN = settings.STATION_SN
zentraDevice = ZentraDevice.objects.get(device_sn=stationSN)
sn = zentraDevice.device_sn

# save into Data base
backTime = float(settings.ZENTRA_BACKTIME)

zentraReader(backTime=backTime, stationSN=sn)
