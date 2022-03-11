from .models import ZentraReading, AggregatedZentraReading


# extract data from ZentraReading table.
beginTime = datetime(
    year=2021,
    month=3,
    day=12,
    hour=0,
    minute=0,
    second=0,
    microsecond=0,
    tzinfo=timezone(timedelta(hours=0)),
)

endTime = datetime(
    year=2021,
    month=3,
    day=12,
    hour=23,
    minute=55,
    second=0,
    microsecond=0,
    tzinfo=timezone(timedelta(hours=0)),
)

sn = "06-02047"


aggregateZentraData(stationSN=sn, beginTime=beginTime, endTime=endTime)
