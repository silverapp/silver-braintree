from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from silver.models import Customer

from django.core.exceptions import ValidationError
from django.db.models import Model, ForeignKey, CASCADE


class CustomerData(Model):
    customer = ForeignKey(Customer, on_delete=CASCADE)
    data = models.JSONField(default=dict, null=True, blank=True, encoder=DjangoJSONEncoder)

    def clean(self):
        super(CustomerData, self).clean()

        if not isinstance(self.data, dict):
            raise ValidationError('Field "data" must be a dict.')

    def __repr__(self):
        return '%s Braintree data' % self.customer

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __contains__(self, item):
        return item in self.data

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, data):
        return self.data.update(data)

    def pop(self, key, default=None):
        return self.data.pop(key, default)
