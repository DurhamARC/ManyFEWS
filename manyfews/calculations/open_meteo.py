"""
open_meteo.py – Fetch ensemble weather forecasts from the Open-Meteo API
(https://ensemble-api.open-meteo.com/v1/ensemble) and store them in the
NoaaForecast table so the rest of the pipeline can consume them unchanged.

The Open-Meteo ensemble API is free, requires no API key, and provides
multiple ensemble members for several global NWP models (GFS, ICON, ECMWF …).

Variables requested
-------------------
precipitation          mm  (hourly accumulation)
temperature_2m_max     °C  (daily max; only available at daily resolution in the
                            ensemble endpoint, so we request hourly
                            temperature_2m and derive min/max per day)
temperature_2m_min     °C
windspeed_10m          km/h
winddirection_10m      °   (meteorological convention: 0 = wind from North)
relativehumidity_2m    %

Wind components
---------------
The NoaaForecast model stores ``wind_u`` and ``wind_v`` (zonal / meridional
m s⁻¹).  We decompose wind speed + direction into these components:

    U = -speed * sin(direction_rad)
    V = -speed * cos(direction_rad)

(negative sign because meteorological convention reports *from* direction)
"""

import math
import logging
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from tenacity import retry, stop_after_attempt, wait_fixed

from .models import NoaaForecast

logger = logging.getLogger(__name__)

# Base URL for the Open-Meteo ensemble forecast API
_BASE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

# Hourly variables to request from the API
_HOURLY_VARIABLES = [
    "precipitation",
    "temperature_2m",
    "windspeed_10m",
    "winddirection_10m",
    "relativehumidity_2m",
]


def _kmh_to_ms(speed_kmh: float) -> float:
    """Convert wind speed from km/h to m/s."""
    return speed_kmh / 3.6


def _wind_components(speed_ms: float, direction_deg: float) -> tuple[float, float]:
    """
    Convert wind speed (m/s) and meteorological direction (degrees, *from*)
    to zonal (U) and meridional (V) components in m/s.

    :param speed_ms: wind speed in m/s
    :param direction_deg: wind direction in degrees (meteorological, 0 = from N)
    :return: (wind_u, wind_v) tuple
    """
    direction_rad = math.radians(direction_deg)
    wind_u = -speed_ms * math.sin(direction_rad)
    wind_v = -speed_ms * math.cos(direction_rad)
    return wind_u, wind_v


@retry(stop=stop_after_attempt(5), wait=wait_fixed(60))
def _fetch_ensemble_data(lat: float, lon: float, model: str) -> dict:
    """
    Fetch raw ensemble forecast JSON from Open-Meteo.

    Retried up to 5 times with a 60-second wait between attempts to handle
    transient network errors.

    :param lat: latitude of the forecast location
    :param lon: longitude of the forecast location
    :param model: Open-Meteo ensemble model identifier (e.g. ``"gfs_seamless"``)
    :return: parsed JSON response dict
    :raises requests.HTTPError: if the API returns a non-2xx status
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_HOURLY_VARIABLES),
        "models": model,
        "timeformat": "unixtime",
        "timezone": "UTC",
    }
    response = requests.get(_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _parse_ensemble_members(data: dict) -> dict[str, list]:
    """
    Split the flat hourly response into a dict keyed by member suffix.

    The Open-Meteo ensemble endpoint returns variables with names like
    ``precipitation_member01``, ``temperature_2m_member01`` …  plus a
    ``precipitation`` key for the control / deterministic run.  We group
    all timesteps for each member into a list of dicts.

    :param data: raw JSON response from the API
    :return: dict mapping member label → list of hourly data dicts
    """
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    if not times:
        raise ValueError("Open-Meteo response contained no hourly time steps")

    # Identify all member suffixes present in the response
    # Keys look like: "precipitation", "precipitation_member01", …
    member_suffixes: list[str] = []
    for key in hourly:
        if key.startswith("precipitation"):
            suffix = key[len("precipitation"):]  # "" for control, "_member01" etc.
            member_suffixes.append(suffix)

    if not member_suffixes:
        raise ValueError(
            "Open-Meteo response contained no precipitation data columns"
        )

    members: dict[str, list] = {}
    for suffix in member_suffixes:
        label = suffix.lstrip("_") or "control"
        rows = []
        for i, ts in enumerate(times):
            rows.append(
                {
                    "time": ts,
                    "precipitation": hourly.get(f"precipitation{suffix}", [None])[i],
                    "temperature_2m": hourly.get(f"temperature_2m{suffix}", [None])[
                        i
                    ],
                    "windspeed_10m": hourly.get(f"windspeed_10m{suffix}", [None])[i],
                    "winddirection_10m": hourly.get(
                        f"winddirection_10m{suffix}", [None]
                    )[i],
                    "relativehumidity_2m": hourly.get(
                        f"relativehumidity_2m{suffix}", [None]
                    )[i],
                }
            )
        members[label] = rows

    return members


def _rows_to_noaa_forecasts(
    members: dict[str, list], lat: float, lon: float
) -> list[NoaaForecast]:
    """
    Convert parsed ensemble member rows into unsaved ``NoaaForecast`` instances.

    Temperature from Open-Meteo is in °C; the existing GEFS pipeline stores
    temperatures in K (converted from GRIB).  We keep the same units here:
    values are stored in K to remain consistent with the existing schema and
    downstream model code.

    Wind speed arrives in km/h and is converted to m/s before decomposition.

    :param members: dict mapping member label → list of hourly row dicts
    :param lat: latitude
    :param lon: longitude
    :return: list of ``NoaaForecast`` objects (not yet saved to the DB)
    """
    KELVIN_OFFSET = 273.15
    location = Point(lat, lon)
    forecasts: list[NoaaForecast] = []

    for member_label, rows in members.items():
        # We need per-day min/max temperature from hourly data.
        # Group rows by calendar date first.
        from collections import defaultdict

        daily_temps: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            if row["temperature_2m"] is not None:
                day_key = datetime.fromtimestamp(
                    row["time"], tz=timezone.utc
                ).strftime("%Y-%m-%d")
                daily_temps[day_key].append(row["temperature_2m"])

        daily_min: dict[str, float] = {
            d: min(temps) for d, temps in daily_temps.items()
        }
        daily_max: dict[str, float] = {
            d: max(temps) for d, temps in daily_temps.items()
        }

        for row in rows:
            # Skip rows with missing core values
            if any(
                row[v] is None
                for v in (
                    "precipitation",
                    "windspeed_10m",
                    "winddirection_10m",
                    "relativehumidity_2m",
                )
            ):
                logger.warning(
                    "Skipping row with missing values for member %s at time %s",
                    member_label,
                    row["time"],
                )
                continue

            forecast_dt = datetime.fromtimestamp(row["time"], tz=timezone.utc)
            day_key = forecast_dt.strftime("%Y-%m-%d")

            speed_ms = _kmh_to_ms(row["windspeed_10m"])
            wind_u, wind_v = _wind_components(speed_ms, row["winddirection_10m"])

            # Use daily min/max from hourly temps; fall back to current hour temp
            temp_c = row["temperature_2m"]
            min_temp_k = (daily_min.get(day_key, temp_c) + KELVIN_OFFSET) if temp_c is not None else None
            max_temp_k = (daily_max.get(day_key, temp_c) + KELVIN_OFFSET) if temp_c is not None else None

            if min_temp_k is None or max_temp_k is None:
                logger.warning(
                    "Skipping row with missing temperature for member %s at time %s",
                    member_label,
                    row["time"],
                )
                continue

            forecasts.append(
                NoaaForecast(
                    location=location,
                    date=forecast_dt,
                    precipitation=row["precipitation"],
                    min_temperature=min_temp_k,
                    max_temperature=max_temp_k,
                    wind_u=wind_u,
                    wind_v=wind_v,
                    relative_humidity=row["relativehumidity_2m"],
                )
            )

    return forecasts


def prepareOpenMeteo() -> None:
    """
    Fetch ensemble weather forecasts from Open-Meteo and save them to the
    ``NoaaForecast`` table.

    Configuration is read from Django settings:

    ``LAT_VALUE``
        Latitude of the forecast point (degrees, WGS-84).
    ``LON_VALUE``
        Longitude of the forecast point (degrees, WGS-84).
    ``OPEN_METEO_MODEL``
        Open-Meteo ensemble model to use (default: ``"gfs_seamless"``).
    ``OPEN_METEO_ENSEMBLE_MEMBERS``
        Maximum number of ensemble members to keep (0 = keep all).

    This function mirrors ``prepareGEFS()`` and is a drop-in replacement for
    the daily weather-data step in ``dailyModelUpdate()``.
    """
    lat = settings.LAT_VALUE
    lon = settings.LON_VALUE
    model = getattr(settings, "OPEN_METEO_MODEL", "gfs_seamless")
    max_members = getattr(settings, "OPEN_METEO_ENSEMBLE_MEMBERS", 0)

    logger.info(
        "Fetching Open-Meteo ensemble forecast: model=%s lat=%s lon=%s",
        model,
        lat,
        lon,
    )

    raw = _fetch_ensemble_data(lat=lat, lon=lon, model=model)
    members = _parse_ensemble_members(raw)

    if max_members and max_members > 0:
        # Keep only the requested number of members (plus control if present)
        selected = dict(list(members.items())[:max_members])
        members = selected

    logger.info("Parsed %d ensemble members from Open-Meteo response", len(members))

    forecasts = _rows_to_noaa_forecasts(members=members, lat=lat, lon=lon)

    logger.info("Saving %d NoaaForecast records to database", len(forecasts))
    NoaaForecast.objects.bulk_create(forecasts, batch_size=500)
    logger.info("Open-Meteo ensemble forecast data saved successfully")
