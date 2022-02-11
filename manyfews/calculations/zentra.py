from .models import ZentraReading
from .models import ZentraDevice
from django.utils import timezone
from .preZentra import zentraReader
from .preZentra import authZentraCloud

now = timezone.now()
zentraDevice = ZentraDevice.objects.get(device_sn="06-02047")
sn = zentraDevice.device_sn

# extract data from met station
zentraAtmos = zentraReader(1, sn, authZentraCloud())

# import data into DB
for i in range(len(zentraAtmos["local date"])):
    zentraData = ZentraReading(
        date=zentraAtmos["local date"][i],
        device=zentraDevice,
        precipitation=zentraAtmos["precipitation"][i],
        relative_humidity=zentraAtmos["RH senor temperature"][i],
        air_temperature=zentraAtmos["air temperature"][i],
        wind_speed=zentraAtmos["wind speed"][i],
        wind_direction=zentraAtmos["wind direction"][i],
    )

    zentraData.save()
