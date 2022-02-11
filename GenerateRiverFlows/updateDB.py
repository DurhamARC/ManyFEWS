from manyfews.calculations.models import ZentraReading


zentraData = ZentraReading(
    device="",
    relative_humidity="3",
    air_temperature="4",
    windspeed="5",
    wind_direction="6",
)


zentraData.save()
