from django.contrib.gis import admin
from django.forms import ModelForm, FileField
from leaflet.admin import LeafletGeoAdmin

from .models import ZentraDevice, ModelVersion, RiverChannel


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
