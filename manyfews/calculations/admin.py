from django.contrib.gis import admin
from leaflet.admin import LeafletGeoAdmin

from .models import ZentraDevice


@admin.register(ZentraDevice)
class LocationAdmin(LeafletGeoAdmin):
    # TODO: change admin interface to retrieve settings from Zentra
    list_display = ("device_sn", "device_name", "height")
    display_raw = True
