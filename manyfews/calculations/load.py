import csv

from django.contrib.gis.geos import Point, Polygon

from geotiff import GeoTiff
import numpy as np

from .models import FloodModelParameters

PARAM_CSV_FIELDNAMES = [
    "x",
    "y",
    "size",
    "beta0",
    "beta1",
    "beta2",
    "beta3",
    "beta4",
    "beta5",
    "beta6",
    "beta7",
    "beta8",
    "beta9",
    "beta10",
    "beta11",
]


def load_dummy_params_from_tiff():
    """Script to create dummy parameters from a GeoTIff file - for dev use only"""
    geo_tiff = GeoTiff("../Run1Geo.tif")
    data = geo_tiff.read()
    coords00 = geo_tiff.get_coords(0, 0)
    coords01 = geo_tiff.get_coords(0, 1)
    coords10 = geo_tiff.get_coords(1, 0)
    size_x = coords01[0] - coords00[0]
    size_y = coords10[1] - coords00[1]
    print(size_x)
    print(size_y)
    with open("params.csv", "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=PARAM_CSV_FIELDNAMES)
        writer.writeheader()

        for i, row in enumerate(data):
            for j, val in enumerate(row):
                if val > 0:
                    coords = geo_tiff.get_coords(i, j)
                    print(f"non-zero val at {i}, {j}: x:{coords[0]} y:{coords[1]}")
                    beta0 = val
                    beta1 = val * np.random.rand()
                    param = FloodModelParameters(
                        bounding_box=Polygon.from_bbox(
                            (
                                coords[0] - size_x / 2,
                                coords[1] - size_y / 2,
                                coords[0] + size_x / 2,
                                coords[1] + size_y / 2,
                            )
                        ),
                        beta0=beta0,
                        beta1=beta1,
                    )
                    param.save()
                    writer.writerow(
                        {
                            "x": coords[0],
                            "y": coords[1],
                            "size": size_x,
                            "beta0": beta0,
                            "beta1": beta1,
                        }
                    )
