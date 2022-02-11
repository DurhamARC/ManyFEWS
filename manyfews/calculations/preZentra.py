from zentra.api import *
from os import getenv
import datetime


def zentraReader(backTime, stationSN, token):

    """
    This function is used to extract observation climate data from ZENTRA cloud: https://zentracloud.com/,
    and output data sets into a dictionary.

    :param backTime: the back days number you want to extract (unit: day).
    :param stationSN: the serial number of meter station.
    :param token: authentication token.
    :return: observation data sets.

    """

    # obtain start time ( 30 days before) and device's SN
    startTime = datetime.datetime.now() - datetime.timedelta(days=backTime)

    # Get the readings for a device
    readings = ZentraReadings().get(
        sn=stationSN, token=token, start_time=int(startTime.timestamp()),
    )
    zentraData = readings.response

    tStamp = []
    solar = []
    precip = []
    wDirection = []
    wSpeed = []
    gustSpeed = []
    vaporPressure = []
    atmosPressure = []
    airTem = []
    maxPrecipRate = []
    rhTemp = []
    VPD = []
    covertDate = []

    print(zentraData["device"]["timeseries"][0]["configuration"]["values"][0][3])

    # Extract time stamp, Precipitation, solar, temperature, and humidity
    for i in range(
        len(zentraData["device"]["timeseries"][0]["configuration"]["values"])
    ):

        tStamp.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][0]
        )  # time stamp data

        solar.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][0][
                "value"
            ]
        )  # solar radiation, 'unit':' W/m²'

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

        vaporPressure.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][8][
                "value"
            ]
        )  # vapor pressure, 'units': ' kPa'

        atmosPressure.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][9][
                "value"
            ]
        )  # Atmospheric Pressure, 'units': 'kPa'

        VPD.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][14][
                "value"
            ]
        )  # VPD, 'units': ' kPa'

        rhTemp.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][13][
                "value"
            ]
        )  # RH Senor Temp, 'units': ' °C'

        gustSpeed.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][6][
                "value"
            ]
        )  # Gust Speed, 'units': ' m/s'

        maxPrecipRate.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][12][
                "value"
            ]
        )  # Max Precip Rate, 'units': ' mm/h'

        # convert time stamp to Date
        ts = zentraData["device"]["timeseries"][0]["configuration"]["values"][i][
            0
        ]  # time stamp
        tz = datetime.timezone(datetime.timedelta(hours=6))  # time zone
        date = datetime.datetime.fromtimestamp(ts, tz)  # convert date
        covertDate.append(date)

    # output data sets into a dictionary
    zentraDataSum = [
        covertDate,
        tStamp,
        solar,
        precip,
        wDirection,
        wSpeed,
        gustSpeed,
        vaporPressure,
        atmosPressure,
        airTem,
        maxPrecipRate,
        rhTemp,
        VPD,
    ]
    zentraDataKeys = [
        "local date",
        "time stamp",
        "solar radiation",
        "precipitation",
        "wind direction",
        "wind speed",
        "guest speed",
        "vapor pressure",
        "atmospheric pressure",
        "air temperature",
        "max precipitation Rate",
        "RH senor temperature",
        "VPD",
    ]

    zentraDataSet = dict(zip(zentraDataKeys, zentraDataSum))

    return zentraDataSet


def authZentraCloud():
    """
    This function is used to return authentication token for the Zentra cloud.
    Username & password should be defined as environment parameters.

    :return: authentication token.
    """

    # authentication into the Zentra Cloud API
    token = ZentraToken(username=getenv("zentra_un"), password=getenv("zentra_pw"))

    return token
