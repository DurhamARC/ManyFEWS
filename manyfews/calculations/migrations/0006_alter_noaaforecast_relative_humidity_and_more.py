# Generated by Django 4.0.2 on 2022-03-08 12:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calculations", "0005_riverflowcalculationoutput_riverflowprediction"),
    ]

    operations = [
        migrations.AlterField(
            model_name="noaaforecast",
            name="relative_humidity",
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name="zentrareading",
            name="air_temperature",
            field=models.FloatField(null=True),
        ),
        migrations.AlterField(
            model_name="zentrareading",
            name="precipitation",
            field=models.FloatField(null=True),
        ),
        migrations.AlterField(
            model_name="zentrareading",
            name="relative_humidity",
            field=models.FloatField(null=True),
        ),
        migrations.AlterField(
            model_name="zentrareading",
            name="wind_direction",
            field=models.FloatField(null=True),
        ),
        migrations.AlterField(
            model_name="zentrareading",
            name="wind_speed",
            field=models.FloatField(null=True),
        ),
    ]
