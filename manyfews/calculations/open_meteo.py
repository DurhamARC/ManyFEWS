"""
open_meteo.py -- Fetch weather data from the free, keyless Open-Meteo API
(https://open-meteo.com/) and store it in the shape the rest of the
calculation pipeline expects.

Two data sources are provided, replacing GEFS and Zentra respectively:

``prepareOpenMeteo()``
    Fetches the ensemble forecast endpoint
    (https://ensemble-api.open-meteo.com/v1/ensemble) and stores one
    ``NoaaForecast`` row per 6-hour bucket per ensemble member. This
    replaces the old GEFS download, and unlike GEFS (which only ever used
    the ensemble-mean file) genuinely stores every ensemble member so
    downstream code can propagate real forecast uncertainty.

``prepareOpenMeteoHistorical()``
    Fetches the historical archive endpoint
    (https://archive-api.open-meteo.com/v1/archive) for an arbitrary date
    range and stores one ``AggregatedWeatherReading`` row per 6-hour
    bucket. This replaces Zentra Cloud sensor readings, which were
    previously used to seed/update the model's internal state
    (initial conditions).

Data contract
-------------
``GenerateRiverFlows`` (in generate_river_flows.py) has no notion of dates:
it treats its weather-array input as a flat, strictly-ordered sequence and
reshapes every 4 consecutive rows into one calendar day (dt=0.25 day == 6h
buckets). Both functions in this module therefore always emit rows in
chronological, 6-hour-aligned buckets, and callers must read them back
ordered by ``date`` (never rely on default queryset/insertion order).

``NoaaForecast`` additionally distinguishes:

* ``date``        -- the row's real forecast *valid time*.
* ``issue_date``  -- the nominal "today" this forecast batch was fetched
                      for (a single run writes rows spanning many days into
                      the future, all sharing one issue_date).
* ``ensemble_member`` -- which Open-Meteo ensemble member this row came
                      from (``"control"``, ``"member01"``, ...), so a
                      single run's members can be queried independently
                      instead of being blended together.

Units
-----
Temperatures are stored in Kelvin (matching the existing schema/convention
used by the old GEFS and Zentra pipelines). Wind speed + direction are
decomposed into zonal/meridional components (m/s):

    U = -speed * sin(direction_rad)
    V = -speed * cos(direction_rad)

(negative sign because meteorological convention reports the direction
*from* which the wind blows.)
"""

import math
import logging
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from tenacity import retry, stop_after_attempt, wait_fixed

from .models import AggregatedWeatherReading, NoaaForecast

logger = logging.getLogger(__name__)

_ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

_HOURLY_VARIABLES = [
    "precipitation",
    "temperature_2m",
    "windspeed_10m",
    "winddirection_10m",
    "relativehumidity_2m",
]

_KELVIN_OFFSET = 273.15
_BUCKET_HOURS = 6


def offsetTime(backDays):
    """
    Return the (start, end) UTC datetimes for a calendar day ``backDays``
    days before today: 00:00:00 to 23:55:00.

    :param backDays: number of days before today.
    """
    startDate = datetime.now(tz=timezone.utc) - timedelta(days=backDays)

    startTime = datetime(
        year=startDate.year,
        month=startDate.month,
        day=startDate.day,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=timezone.utc,
    )

    endTime = datetime(
        year=startDate.year,
        month=startDate.month,
        day=startDate.day,
        hour=23,
        minute=55,
        second=0,
        microsecond=0,
        tzinfo=timezone.utc,
    )

    return startTime, endTime


def _kmh_to_ms(speed_kmh: float) -> float:
    """Convert wind speed from km/h to m/s."""
    return speed_kmh / 3.6


def _wind_components(speed_ms: float, direction_deg: float) -> tuple[float, float]:
    """
    Convert wind speed (m/s) and meteorological direction (degrees, *from*)
    to zonal (U) and meridional (V) components in m/s.
    """
    direction_rad = math.radians(direction_deg)
    wind_u = -speed_ms * math.sin(direction_rad)
    wind_v = -speed_ms * math.cos(direction_rad)
    return wind_u, wind_v


@retry(stop=stop_after_attempt(5), wait=wait_fixed(60))
def _fetch_json(url: str, params: dict) -> dict:
    """GET a URL with retries (5 attempts, 60s apart) and return parsed JSON."""
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def _fetch_ensemble_data(
    lat: float, lon: float, model: str, start_date: str, end_date: str
) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_HOURLY_VARIABLES),
        "models": model,
        "start_date": start_date,
        "end_date": end_date,
        "timeformat": "unixtime",
        "timezone": "UTC",
    }
    return _fetch_json(_ENSEMBLE_URL, params)


def _fetch_historical_data(
    lat: float, lon: float, start_date: str, end_date: str
) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_HOURLY_VARIABLES),
        "start_date": start_date,
        "end_date": end_date,
        "timeformat": "unixtime",
        "timezone": "UTC",
    }
    return _fetch_json(_ARCHIVE_URL, params)


def _member_suffixes(hourly: dict) -> list[str]:
    """
    Identify ensemble member suffixes present in an Open-Meteo ensemble
    hourly response. Keys look like ``precipitation`` (control run) and
    ``precipitation_member01``, ``precipitation_member02``, ...
    """
    suffixes = []
    for key in hourly:
        if key == "precipitation":
            suffixes.append("")
        elif key.startswith("precipitation_member"):
            suffixes.append(key[len("precipitation") :])
    return suffixes


def _bucket_to_6h(hourly: dict, suffix: str = "") -> list[dict]:
    """
    Aggregate one member/variant's native hourly Open-Meteo data into
    6-hour buckets aligned to the data's own start time.

    Only full (6-hour) buckets are emitted; a trailing partial day is
    dropped rather than guessed at.

    :param hourly: the raw ``"hourly"`` dict from an Open-Meteo response.
    :param suffix: ensemble member suffix, e.g. ``""`` or ``"_member01"``.
    :return: list of dicts with time/precipitation/min_temperature/
        max_temperature/wind_u/wind_v/relative_humidity (temperatures in K).
    """
    times = hourly.get("time", [])
    precip = hourly.get(f"precipitation{suffix}", [])
    temp = hourly.get(f"temperature_2m{suffix}", [])
    wspd = hourly.get(f"windspeed_10m{suffix}", [])
    wdir = hourly.get(f"winddirection_10m{suffix}", [])
    rh = hourly.get(f"relativehumidity_2m{suffix}", [])

    buckets = []
    full_buckets_end = len(times) - (len(times) % _BUCKET_HOURS)

    for start in range(0, full_buckets_end, _BUCKET_HOURS):
        idxs = range(start, start + _BUCKET_HOURS)

        bucket_precip = [
            precip[i] for i in idxs if i < len(precip) and precip[i] is not None
        ]
        bucket_temp = [temp[i] for i in idxs if i < len(temp) and temp[i] is not None]
        bucket_rh = [rh[i] for i in idxs if i < len(rh) and rh[i] is not None]
        bucket_uv = [
            _wind_components(_kmh_to_ms(wspd[i]), wdir[i])
            for i in idxs
            if i < len(wspd)
            and i < len(wdir)
            and wspd[i] is not None
            and wdir[i] is not None
        ]

        if not (bucket_precip and bucket_temp and bucket_rh and bucket_uv):
            logger.warning(
                "Skipping incomplete 6h bucket starting at index %d (suffix=%r)",
                start,
                suffix,
            )
            continue

        buckets.append(
            {
                "time": datetime.fromtimestamp(times[start], tz=timezone.utc),
                "precipitation": sum(bucket_precip),
                "min_temperature": min(bucket_temp) + _KELVIN_OFFSET,
                "max_temperature": max(bucket_temp) + _KELVIN_OFFSET,
                "wind_u": sum(u for u, v in bucket_uv) / len(bucket_uv),
                "wind_v": sum(v for u, v in bucket_uv) / len(bucket_uv),
                "relative_humidity": sum(bucket_rh) / len(bucket_rh),
            }
        )

    return buckets


def prepareOpenMeteo() -> None:
    """
    Fetch the Open-Meteo ensemble forecast and save it to the
    ``NoaaForecast`` table, one row per 6-hour bucket per ensemble member.

    Configuration is read from Django settings:

    ``LAT_VALUE`` / ``LON_VALUE``
        Location of the forecast point (degrees, WGS-84).
    ``OPEN_METEO_MODEL``
        Open-Meteo ensemble model identifier (default ``"gfs_seamless"``).
    ``OPEN_METEO_FORECAST_DAYS``
        Forecast horizon in days (default 16, matching the old GEFS setup).
    ``OPEN_METEO_ENSEMBLE_MEMBERS``
        Maximum number of ensemble members to keep (0 = keep all available;
        the control/deterministic run is always kept first).
    """
    lat = settings.LAT_VALUE
    lon = settings.LON_VALUE
    model = settings.OPEN_METEO_MODEL
    forecast_days = settings.OPEN_METEO_FORECAST_DAYS
    max_members = settings.OPEN_METEO_ENSEMBLE_MEMBERS

    issue_date, _ = offsetTime(backDays=0)
    end_date = issue_date + timedelta(days=forecast_days - 1)

    logger.info(
        "Fetching Open-Meteo ensemble forecast: model=%s lat=%s lon=%s days=%s",
        model,
        lat,
        lon,
        forecast_days,
    )

    raw = _fetch_ensemble_data(
        lat=lat,
        lon=lon,
        model=model,
        start_date=issue_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )
    hourly = raw.get("hourly", {})

    suffixes = _member_suffixes(hourly)
    if not suffixes:
        raise ValueError("Open-Meteo response contained no precipitation data columns")

    # Control run (suffix "") always first, then members in ascending order.
    suffixes = sorted(suffixes, key=lambda s: (s != "", s))
    if max_members and max_members > 0:
        suffixes = suffixes[:max_members]

    location = Point(lon, lat)
    forecasts = []
    for suffix in suffixes:
        label = f"member{suffix[len('_member'):]}" if suffix else "control"
        buckets = _bucket_to_6h(hourly, suffix)
        for bucket in buckets:
            forecasts.append(
                NoaaForecast(
                    location=location,
                    date=bucket["time"],
                    issue_date=issue_date,
                    ensemble_member=label,
                    precipitation=bucket["precipitation"],
                    min_temperature=bucket["min_temperature"],
                    max_temperature=bucket["max_temperature"],
                    wind_u=bucket["wind_u"],
                    wind_v=bucket["wind_v"],
                    relative_humidity=bucket["relative_humidity"],
                )
            )

    logger.info(
        "Parsed %d ensemble members (%d rows) from Open-Meteo response",
        len(suffixes),
        len(forecasts),
    )

    NoaaForecast.objects.bulk_create(forecasts, batch_size=500)
    logger.info("Open-Meteo ensemble forecast data saved successfully")


def prepareOpenMeteoHistorical(start_date: datetime, end_date: datetime) -> None:
    """
    Fetch observed historical weather from Open-Meteo's archive API for
    ``[start_date, end_date]`` (inclusive) and save it to the
    ``AggregatedWeatherReading`` table, one row per 6-hour bucket.

    Replaces Zentra Cloud sensor readings as the source of "actual past
    weather" used to seed/update the model's internal state.

    Raises ``RuntimeError`` if Open-Meteo's archive hasn't fully ingested
    the requested range yet (it typically lags real-time by about a day),
    rather than silently interpolating or falling back to defaults.
    """
    lat = settings.LAT_VALUE
    lon = settings.LON_VALUE
    location = Point(lon, lat)

    num_days = (end_date.date() - start_date.date()).days + 1
    logger.info(
        "Fetching Open-Meteo historical data: lat=%s lon=%s %s to %s (%d days)",
        lat,
        lon,
        start_date.date(),
        end_date.date(),
        num_days,
    )

    raw = _fetch_historical_data(
        lat=lat,
        lon=lon,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )
    hourly = raw.get("hourly", {})
    buckets = _bucket_to_6h(hourly)

    expected_buckets = num_days * (24 // _BUCKET_HOURS)
    if len(buckets) < expected_buckets:
        raise RuntimeError(
            f"Open-Meteo historical data incomplete for {start_date.date()}..{end_date.date()}: "
            f"expected {expected_buckets} 6-hour buckets, got {len(buckets)}. "
            "The archive API may not have ingested the most recent day(s) yet."
        )

    readings = [
        AggregatedWeatherReading(
            location=location,
            date=bucket["time"],
            precipitation=bucket["precipitation"],
            min_temperature=bucket["min_temperature"],
            max_temperature=bucket["max_temperature"],
            wind_u=bucket["wind_u"],
            wind_v=bucket["wind_v"],
            relative_humidity=bucket["relative_humidity"],
        )
        for bucket in buckets
    ]

    AggregatedWeatherReading.objects.bulk_create(readings, batch_size=500)
    logger.info(
        "Saved %d AggregatedWeatherReading rows from Open-Meteo historical data",
        len(readings),
    )
