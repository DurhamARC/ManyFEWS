from .models import ZentraReading
from .models import ZentraDevice
from zentra.api import ZentraReadings, ZentraToken
from os import getenv
from datetime import timedelta, timezone, datetime
import math


def zentraReader(backTime, stationSN, token):

    """
    This function is used to extract observation climate data from ZENTRA cloud: https://zentracloud.com/,
    and output data sets into a dictionary.

    :param backTime: the back days number you want to extract (unit: day).
    :param stationSN: the serial number of meter station.
    :param token: authentication token.
    :return zentraDataSum: a list of observation data sets.
                          [0: "local date",
                           1: "time stamp",
                           2: "solar radiation",
                           3. "precipitation",
                           4. "wind direction",
                           5. "wind speed",
                           6. "guest speed",
                           7. "vapor pressure",
                           8. "atmospheric pressure",
                           9. "air temperature",
                          10. "max precipitation Rate",
                          11. "RH senor temperature",
                          12. "VPD",
                          13. "Relative Humidity",]

    """

    # obtain start time ( 30 days before) and device's SN
    startTime = datetime.now() - timedelta(days=backTime)

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
    convertedDate = []
    RH = []

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

    # output data sets into a dictionary
    zentraDataSum = [
        convertedDate,
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
        RH,
    ]

    return zentraDataSum


def authZentraCloud():
    """
    This function is used to return authentication token for the Zentra cloud.
    Username & password should be defined as environment parameters.

    :return: authentication token.
    """

    # authentication into the Zentra Cloud API
    token = ZentraToken(username=getenv("zentra_un"), password=getenv("zentra_pw"))

    return token


def dataBaseWriter(sn, backTime):
    """
    This function is used to save data from zentra cloud into
    Database ( calculations_zentrareading table)
    :param sn: met station Serial number
    :param backTime: the back days number you want to extract (unit: day).
    :return: none
    """

    # extract data from met station
    zentraAtmos = zentraReader(backTime, sn, authZentraCloud())

    # import data into DB

    for i in range(len(zentraAtmos[0])):
        zentraData = ZentraReading(
            date=zentraAtmos[0][i],
            device=zentraDevice,
            precipitation=zentraAtmos[3][i],
            relative_humidity=zentraAtmos[13][i],
            air_temperature=zentraAtmos[9][i],
            wind_speed=zentraAtmos[5][i],
            wind_direction=zentraAtmos[4][i],
        )

        zentraData.save()


# get met station's SN
zentraDevice = ZentraDevice.objects.get(device_sn="06-02047")
sn = zentraDevice.device_sn

# save into Data base
backTime = 0.5
dataBaseWriter(sn, backTime)
