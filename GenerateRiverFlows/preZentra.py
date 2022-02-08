from zentra.api import *
from os import getenv
import datetime


# authentication into the Zentra Cloud API
token = ZentraToken(username=getenv("zentra_un"), password=getenv("zentra_pw"))


# Get the readings for a device
readings = ZentraReadings().get(
    sn="06-02047",
    token=token,
    start_time=int(datetime.datetime(year=2022, month=2, day=6).timestamp()),
)

a = readings.response
print(a.keys())
print(len(a["device"]))
