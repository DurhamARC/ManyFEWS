import os
from webapp.models import (
    stream_mapping,
    Stream,
    AccumulatedRisk,
    accumulatedrisk_mapping,
)
from django.contrib.gis.utils import LayerMapping

shapefile_dir = os.path.join(os.path.dirname(os.getcwd()), "Data/shapefiles")

lm = LayerMapping(
    Stream, os.path.join(shapefile_dir, "Durham_stream.shp"), stream_mapping
)
lm.save()

lm = LayerMapping(
    AccumulatedRisk,
    os.path.join(shapefile_dir, "Durham_channel_accumulated_risk.shp"),
    accumulatedrisk_mapping,
)
lm.save()
