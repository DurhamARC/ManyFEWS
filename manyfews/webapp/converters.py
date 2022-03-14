from django.contrib.gis.geos import Polygon


class BoundingBoxUrlParameterConverter:
    """Class to convert GIS coordinates representing a bounding box into a Polygon"""

    regex = r"(\-?[0-9]+(\.?[0-9]+)?,){3}\-?[0-9]+(\.?[0-9]+)?"

    def to_python(self, value):
        vals = value.split(",")
        if len(vals) != 4:
            raise ValueError(f"Invalid coordinates {value}")

        try:
            bounding_box = Polygon.from_bbox((float(val) for val in vals))
        except:
            raise ValueError(f"Invalid coordinates {value}")

        return bounding_box

    def to_url(self, value):
        return str(value)
