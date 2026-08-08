from django.db import migrations, models
import django.contrib.gis.db.models.fields
import django.contrib.gis.geos.point


class Migration(migrations.Migration):
    """
    Replaces Zentra Cloud (sensor station readings) and NOAA GEFS with
    Open-Meteo as the sole weather data source.

    This DROPS the ZentraDevice, ZentraReading and AggregatedZentraReading
    tables and all data in them - there is no data-preserving path for this
    migration, per an explicit decision that historical Zentra readings did
    not need to be retained. AggregatedWeatherReading replaces
    AggregatedZentraReading, populated from Open-Meteo's historical archive
    API instead of Zentra sensor readings.
    """

    dependencies = [
        ("calculations", "0003_riverchannel"),
    ]

    operations = [
        migrations.CreateModel(
            name="AggregatedWeatherReading",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateTimeField()),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(
                        default=django.contrib.gis.geos.point.Point(0, 0), srid=4326
                    ),
                ),
                ("precipitation", models.FloatField()),
                ("min_temperature", models.FloatField()),
                ("max_temperature", models.FloatField()),
                ("wind_u", models.FloatField()),
                ("wind_v", models.FloatField()),
                ("relative_humidity", models.FloatField(default=0)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="noaaforecast",
            name="issue_date",
            field=models.DateTimeField(db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="noaaforecast",
            name="ensemble_member",
            field=models.CharField(db_index=True, default="control", max_length=20),
        ),
        # ZentraReading's table must be dropped before ZentraDevice's, since it
        # holds a foreign key referencing ZentraDevice.
        migrations.DeleteModel(
            name="AggregatedZentraReading",
        ),
        migrations.DeleteModel(
            name="ZentraReading",
        ),
        migrations.DeleteModel(
            name="ZentraDevice",
        ),
    ]
