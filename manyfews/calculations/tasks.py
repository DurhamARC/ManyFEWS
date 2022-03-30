from datetime import datetime, timedelta, timezone
import os

from celery import Celery, shared_task
from celery.schedules import crontab
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from django.conf import settings

from webapp.alerts import TwilioAlerts
from webapp.models import UserAlert, UserPhoneNumber, AlertType
from .alerts import send_phone_alerts_for_user
from .zentra import zentraReader
from .gefs import dataBaseWriter
from .models import (
    AggregatedDepthPrediction,
    InitialCondition,
    RiverFlowCalculationOutput,
    RiverFlowPrediction,
)
from .generate_river_flows import (
    prepareGEFSdata,
    prepareInitialCondition,
    GenerateRiverFlows,
)

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
    This function is developed to extract daily necessary Zentra cloud observation data sets
    into Database for running the River Flows model.

    For each day: the data is from 00:00 ---> 23:55
    """

    # get serial number
    stationSN = settings.STATION_SN

    # save into Data base
    backDay = float(settings.ZENTRA_BACKTIME)

    # prepare start_time and end_time
    startDate = datetime.now() - timedelta(days=backDay)
    startTime = datetime(
        year=startDate.year,
        month=startDate.month,
        day=startDate.day,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=timezone(timedelta(hours=0)),
    )  # Offset start time to 00:00

    endTime = datetime(
        year=startDate.year,
        month=startDate.month,
        day=startDate.day,
        hour=23,
        minute=55,
        second=0,
        microsecond=0,
        tzinfo=timezone(timedelta(hours=0)),
    )  # Offset start time to 23:55

    # prepare Zentra Cloud data
    zentraReader(startTime=startTime, endTime=endTime, stationSN=stationSN)


@shared_task(name="calculations.runningGenerateRiverFlows")
def runningGenerateRiverFlows(dt, predictionDate, dataLocation):
    """
    This function is developed to prepare data and running models for generating river flows,
    and save the next day's initial condition, River flow, Rainfall, and potential evapotranspiration
    into DB.

    :param dt: time step(unit:day)
    :param beginDate: the date information of input data.
    :param dataLocation: the location information of input data
    :return none.
    """
    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )

    dataFileDirPath = os.path.join(projectPath, "Data")
    parametersFilePath = os.path.join(
        dataFileDirPath, "RainfallRunoffModelParameters.csv"
    )

    # plus time zone information
    predictionDate = datetime.astimezone(
        predictionDate, tz=timezone(timedelta(hours=0))
    )

    # prepare GEFS data for model.
    gefsData = prepareGEFSdata(date=predictionDate, location=dataLocation)

    # prepare initial condition data for model.
    initialConditionData = prepareInitialCondition(
        date=predictionDate, location=dataLocation
    )

    # run model.
    riverFlowsData = GenerateRiverFlows(
        dt=0.25,
        gefsData=gefsData,
        F0=initialConditionData,
        parametersFilePath=parametersFilePath,
    )

    # riverFlowsData[0] ====> Q: River flow (m3/s).
    # riverFlowsData[1] ====> qp: Rainfall (mm/day).
    # riverFlowsData[2] ====> Ep: Potential evapotranspiration (mm/day).
    # riverFlowsData[3] ====> F0: intial condition data for next day.

    riverFlows = riverFlowsData[0]
    qp = riverFlowsData[1]
    Ep = riverFlowsData[2]
    F0 = riverFlowsData[3]  # next day's initial condition

    # import the next day's initial condition data F0 into DB.
    # ('calculations_initialcondition' table)
    nextDay = predictionDate + timedelta(days=1)

    for i in range(len(F0[:, 0])):
        nextDayInitialCondition = InitialCondition(
            date=nextDay,
            location=dataLocation,
            storage_level=F0[i, 0],
            slow_flow_rate=F0[i, 1],
            fast_flow_rate=F0[i, 2],
        )
        nextDayInitialCondition.save()

    for i in range(qp.shape[0]):
        # save qp and Eq and into DB.
        # ( 'calculations_riverflowcalculationoutput' table)
        forecastTime = predictionDate + timedelta(days=i * dt)
        riverFlowCalculationOutputData = RiverFlowCalculationOutput(
            prediction_date=predictionDate,
            forecast_time=forecastTime,
            location=dataLocation,
            rain_fall=qp[i],
            potential_evapotranspiration=Ep[i],
        )
        riverFlowCalculationOutputData.save()

        # save Q into DB.
        # ('calculations_riverflowprediction' table)
        for j in range(riverFlows.shape[1]):
            riverFlowPredictionData = RiverFlowPrediction(
                prediction_index=j,
                calculation_output=riverFlowCalculationOutputData,
                river_flow=riverFlows[i, j],
            )
            riverFlowPredictionData.save()


@shared_task(name="Send user SMS alerts")
def send_user_sms_alerts(user_id, phone_number_id):
    send_phone_alerts_for_user(user_id, phone_number_id, alert_type=AlertType.SMS)


@shared_task(name="Send all alerts")
def send_alerts():
    # Get and send SMS alerts
    # Group by user and phone number, so we can send alerts for multiple locations at once
    sms_alerts = (
        UserAlert.objects.filter(verified=True, alert_type=AlertType.SMS)
        .values("user_id", "phone_number")
        .distinct()
    )
    for alert_details in sms_alerts:
        result = send_user_sms_alerts.delay(
            alert_details["user_id"], alert_details["phone_number"]
        )
