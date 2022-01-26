from django.contrib.gis.db import models


class AccumulatedRisk(models.Model):
    cat = models.BigIntegerField()
    value = models.FloatField()
    geom = models.MultiPointField(srid=4362)


# Auto-generated `LayerMapping` dictionary for AccumulatedRisk model
accumulatedrisk_mapping = {
    'cat': 'cat',
    'value': 'value',
    'geom': 'MULTIPOINT',
}


class Stream(models.Model):
    cat = models.BigIntegerField()
    value = models.BigIntegerField()
    label = models.CharField(max_length=10, null=True)
    geom = models.MultiLineStringField(srid=4362)


# Auto-generated `LayerMapping` dictionary for Stream model
stream_mapping = {
    'cat': 'cat',
    'value': 'value',
    'label': 'label',
    'geom': 'MULTILINESTRING',
}
