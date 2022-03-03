from celery import Celery, shared_task
from celery.schedules import crontab
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from .zentra import zentraReader
from .gefs import dataBaseWriter
from django.conf import settings
from .GenerateRiverFlows import (
    prepareGEFSdata,
    prepareInitialCondition,
    GenerateRiverFlows,
    prepare_test_Data,
)
from .models import InitialCondition
from datetime import timedelta
import os


app = Celery()

import logging

logger = logging.getLogger(__name__)


@shared_task(name="calculations.hello_celery")
def hello_celery():
    """
    This is an example of a task that can be scheduled via celery.
    """
    logger.info("Hello logging from celery!")


@shared_task(name="calculations.prepareGEFS")
def prepareGEFS():
    """
    This function is developed to extract necessary GEFS forecast data sets
    into Database for running the River Flows model
    """
    # prepare GEFS data
    dt = float(settings.GEFS_TIME_STEP)
    forecastDays = int(settings.GEFS_FORECAST_DAYS)
    dataBaseWriter(dt=dt, forecastDays=forecastDays)


@shared_task(name="calculations.prepareZentra")
def prepareZentra():
    """
    This function is developed to extract necessary Zentra cloud observation data sets
    into Database for running the River Flows model
    """

    # get serial number
    stationSN = settings.STATION_SN

    # save into Data base
    backTime = float(settings.ZENTRA_BACKTIME)

    # prepare Zentra Cloud data
    zentraReader(backTime=backTime, stationSN=stationSN)


@shared_task(name="calculations.runningGenerateRiverFlows")
def runningGenerateRiverFlows(dataDate, dataLocation):
    """
    This function is developed to prepare data and running models for generating river flows,
    and save the next day's initial condition into DB.

    :param dataDate: the date information of input data
    :param dataLocation: the location information of input data
    :return riverFlowData: it is a data tuple, which:
            riverFlowsData[0] ====> Q: River flow (m3/s).
            riverFlowsData[1] ====> qp: Rainfall (mm/day).
            riverFlowsData[2] ====> Ep: Potential evapotranspiration (mm/day).
            riverFlowsData[3] ====> F0: intial condition data for next day.
    """
    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )

    dataFileDirPath = os.path.join(projectPath, "Data")
    parametersFilePath = os.path.join(
        dataFileDirPath, "RainfallRunoffModelParameters.csv"
    )

    gefsData = prepareGEFSdata(date=dataDate, location=dataLocation)
    intialConditionData = prepareInitialCondition(date=dataDate, location=dataLocation)
    riverFlowsData = GenerateRiverFlows(
        gefsData=gefsData,
        F0=intialConditionData,
        parametersFilePath=parametersFilePath,
    )

    # import the next day's initial condition data into DB.
    # save into DB ( 'calculations_initialcondition' table)
    F0 = riverFlowsData[3]  # next day's initial condition
    tomorrow = dataDate + timedelta(days=1)

    for i in range(len(F0[:, 0])):
        nextDayInitialCondition = InitialCondition(
            date=tomorrow,
            location=dataLocation,
            storage_level=F0[i, 0],
            slow_flow_rate=F0[i, 1],
            fast_flow_rate=F0[i, 2],
        )
        nextDayInitialCondition.save()
    return riverFlowsData


testInfo = prepare_test_Data()  # get test data and location
testDate = testInfo[0]
testLocation = testInfo[1]

output = runningGenerateRiverFlows(dataDate=testDate, dataLocation=testLocation)
