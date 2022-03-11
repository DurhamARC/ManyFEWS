from django.contrib.gis.geos import Polygon


class BoundingBoxUrlParameterConverter:
    regex = (
        "\-?[0-9]+\.?[0-9]+,\-?[0-9]+\.?[0-9]+,\-?[0-9]+\.?[0-9]+,\-?[0-9]+\.?[0-9]+"
    )

    def to_python(self, value):
        print(value)
        vals = value.split(",")
        bounding_box = Polygon.from_bbox((float(val) for val in vals))
        print(bounding_box)
        return bounding_box

    def to_url(self, value):
        return str(value)
