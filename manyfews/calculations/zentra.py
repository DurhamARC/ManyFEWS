from .models import ZentraReading
from .models import ZentraDevice
from zentra.api import ZentraReadings, ZentraToken
from datetime import timedelta, timezone, datetime
from django.conf import settings
import math


def zentraReader(backTime, stationSN):

    """
    This function is used to extract observation climate data from ZENTRA cloud: https://zentracloud.com/,
    and output data sets into Database ( calculations_zentrareading table)

    :param backTime: the back days number you want to extract (unit: day).
    :param stationSN: the serial number of meter station.
    :param token: authentication token.
    :return none

    """

    # obtain start time ( 30 days before) and device's SN
    startTime = datetime.now() - timedelta(days=backTime)

    # return authentication token for the Zentra cloud
    token = ZentraToken(username=settings.ZENTRA_UN, password=settings.ZENTRA_PW)

    # Get the readings for a device
    readings = ZentraReadings().get(
        sn=stationSN, token=token, start_time=int(startTime.timestamp()),
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


# get met station's SN
zentraDevice = ZentraDevice.objects.get(device_sn="06-02047")
sn = zentraDevice.device_sn

# save into Data base
backTime = 0.5
zentraReader(backTime=backTime, stationSN=sn)
