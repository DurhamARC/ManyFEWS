"""
Django Bulk Inserts class originally from:
https://www.caktusgroup.com/blog/2019/01/09/django-bulk-inserts/
"""
from collections import defaultdict
from typing import Union

from django.apps import apps


class BulkCreateManager(object):
    """
    This helper class keeps track of ORM objects to be created for multiple
    model classes, and automatically creates those objects with `bulk_create`
    when the number of objects accumulated for a given model class exceeds
    `chunk_size`.
    Upon completion of the loop that's `add()`ing objects, the developer must
    call `done()` to ensure the final set of objects is created for all models.
    """

    def __init__(self, chunk_size: int = 100):
        self._create_queues = defaultdict(list)
        self.chunk_size = chunk_size

    def _commit(self, model_class):
        model_key = model_class._meta.label
        model_class.objects.bulk_create(self._create_queues[model_key])
        self._create_queues[model_key] = []

    def add(self, obj):
        """
        Add an object to the queue to be created, and call bulk_create if we
        have enough objs.
        """
        model_class = type(obj)
        model_key = model_class._meta.label
        self._create_queues[model_key].append(obj)
        if len(self._create_queues[model_key]) >= self.chunk_size:
            self._commit(model_class)

    def done(self):
        """
        Always call this upon completion to make sure the final partial chunk
        is saved.
        """
        for model_name, objs in self._create_queues.items():
            if len(objs) > 0:
                self._commit(apps.get_model(model_name))


class BulkUpdateManager(BulkCreateManager):
    def __init__(self, chunk_size: int = 100, update_fields: list = []):
        super().__init__(chunk_size=chunk_size)
        self.update_fields = update_fields

    def _commit(self, model_class: str):
        model_key = model_class._meta.label
        model_class.objects.bulk_update(
            self._create_queues[model_key], self.update_fields
        )
        self._create_queues[model_key] = []


class BulkCreateUpdateManager(BulkCreateManager):
    """
    Extend BulkCreateManager with the ability to update model records
    """

    def __init__(self, chunk_size: int = 100, fields: Union[list, tuple] = []):
        self._update_queues = defaultdict(list)
        self._fields = fields
        super().__init__(chunk_size)

    def _commit(self, model_class):
        model_key = model_class._meta.label
        model_class.objects.bulk_update(
            self._update_queues[model_key], fields=self._fields
        )
        self._update_queues[model_key] = []

        super()._commit(model_class)

    def update(self, obj):
        """
        Add an object to the queue to be updated, and call bulk_update if we
        have enough objs.
        """
        model_class = type(obj)
        model_key = model_class._meta.label
        self._update_queues[model_key].append(obj)
        if len(self._update_queues[model_key]) >= self.chunk_size:
            self._commit(model_class)

    def done(self):
        for model_name, objs in self._update_queues.items():
            if len(objs) > 0:
                self._commit(apps.get_model(model_name))

        super().done()
