from .models import ZentraReading
from zentra.api import ZentraReadings, ZentraToken
from datetime import timedelta, timezone, datetime
from django.conf import settings
from .models import ZentraDevice
import math


def zentraReader(startTime, endTime, stationSN):

    """
    This function is used to extract observation climate data from ZENTRA cloud: https://zentracloud.com/,
    and output data sets into Database ( calculations_zentrareading table)

    :param startTime: the start time you want to extract (unit: day).
    :param endTime: the end time you want to extract (unit: day).
    :param stationSN: the serial number of meter station.
    :param token: authentication token.
    :return none

    """
    # return authentication token for the Zentra cloud
    token = ZentraToken(username=settings.ZENTRA_UN, password=settings.ZENTRA_PW)

    # Get the readings for a device
    readings = ZentraReadings().get(
        sn=stationSN,
        token=token,
        start_time=int(startTime.timestamp()),
        end_time=int(endTime.timestamp()),
    )
    zentraData = readings.response

    precip = []
    wDirection = []
    wSpeed = []
    airTem = []
    convertedDate = []
    RH = []

    # Extract time stamp, Precipitation, solar, temperature, and humidity
    for i in range(
        len(zentraData["device"]["timeseries"][0]["configuration"]["values"])
    ):

        precip.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][1][
                "value"
            ]
        )  # Precipitation, 'unit':' mm'

        airTem.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][7][
                "value"
            ]
        )  # air temperature, 'unit'=' °C'

        wDirection.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][4][
                "value"
            ]
        )  # Wind Direction, 'units': ' °'

        wSpeed.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][5][
                "value"
            ]
        )  # wind speed, 'units': ' m/s'

        # convert time stamp to Date
        ts = zentraData["device"]["timeseries"][0]["configuration"]["values"][i][
            0
        ]  # time stamp
        date = datetime.fromtimestamp(
            ts, tz=timezone.utc
        )  # change time stamp to UTC time.
        convertedDate.append(date)

        # calculate RH by: esTair = 0.611*EXP((17.502*Tc)/(240.97+Tc))
        #                  RH = VP / esTair
        #                 which:Tc is the Air Temperature
        #                       VP is the Vapour Pressure
        #                       RH is the Relative Humidity between zero and one.

        Tempair = zentraData["device"]["timeseries"][0]["configuration"]["values"][i][
            3
        ][7]["value"]

        vapPressure = zentraData["device"]["timeseries"][0]["configuration"]["values"][
            i
        ][3][8]["value"]
        rh = vapPressure / (0.611 * (math.exp((17.502 * Tempair) / (240.97 + Tempair))))

        if rh > 1:
            rh = 1
        elif rh < 0:
            rh = 0

        RH.append(rh)

    zentraDevice = ZentraDevice.objects.get(device_sn=stationSN)

    # converting string 'None' to None by strNoneToNone method.
    precip = list(map(strNoneToNone, precip))
    RH = list(map(strNoneToNone, RH))
    airTem = list(map(strNoneToNone, airTem))
    wSpeed = list(map(strNoneToNone, wSpeed))
    wDirection = list(map(strNoneToNone, wDirection))

    # import data into DB
    for i in range(len(convertedDate)):
        zentraData = ZentraReading(
            date=convertedDate[i],
            device=zentraDevice,
            precipitation=precip[i],
            relative_humidity=RH[i],
            air_temperature=airTem[i],
            wind_speed=wSpeed[i],
            wind_direction=wDirection[i],
        )

        zentraData.save()


def strNoneToNone(x):
    """
    create a method for converting string type to None Type
    """

    if type(x) == str:
        x = None

    return x
