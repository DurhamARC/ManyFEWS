from django.contrib.gis import admin
from django.forms import ModelForm, FileField
from leaflet.admin import LeafletGeoAdmin

from .models import (
    ZentraDevice,
    ModelVersion,
    RiverChannel,
    RiverFlowPrediction,
    FloodModelParameters,
)


@admin.register(FloodModelParameters)
class FloodModelParametersAdmin(admin.ModelAdmin):
    list_display = ["id", "model_version_id"] + [f"beta{i}" for i in range(12)]


@admin.register(RiverFlowPrediction)
class RiverFlowPredictionAdmin(admin.ModelAdmin):
    list_display = ("prediction_index", "forecast_time", "river_flow")

    def forecast_time(self, obj):
        return obj.calculation_output.forecast_time


@admin.register(ZentraDevice)
class LocationAdmin(LeafletGeoAdmin):
    # TODO: change admin interface to retrieve settings from Zentra
    list_display = ("device_sn", "device_name", "height")
    display_raw = True


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):

    # form = ModelVersionForm
    list_display = ("version_name", "date_created", "is_current")

    actions = ["delete_model"]

    def get_readonly_fields(self, request, obj=None):
        # Disallow editing of param file
        if obj:  # obj is not None, so this is an edit
            return [
                "param_file",
            ]
        else:  # This is an addition
            return []

    def delete_queryset(self, request, queryset):
        queryset.delete()
        self._update_current()

    def delete_model(self, request, obj):
        obj.delete()
        self._update_current()

    def _update_current(self):
        if not ModelVersion.objects.filter(is_current=True).count():
            # Find most recent model version and make it current
            current = ModelVersion.objects.latest("date_created")
            if current:
                current.is_current = True
                current.save()


@admin.register(RiverChannel)
class RiverChannelAdmin(LeafletGeoAdmin):
    display_raw = True
