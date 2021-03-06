# Generated by Django 4.0.2 on 2022-03-08 08:06

import django.contrib.gis.db.models.fields
import django.contrib.gis.geos.point
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("calculations", "0004_initialcondition"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiverFlowCalculationOutput",
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
                ("prediction_date", models.DateTimeField()),
                ("forecast_time", models.DateTimeField()),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(
                        default=django.contrib.gis.geos.point.Point(0, 0), srid=4326
                    ),
                ),
                ("rain_fall", models.FloatField()),
                ("potential_evapotranspiration", models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name="RiverFlowPrediction",
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
                ("prediction_index", models.IntegerField(default=0)),
                ("river_flow", models.FloatField()),
                (
                    "calculation_output",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="calculations.riverflowcalculationoutput",
                    ),
                ),
            ],
        ),
    ]
