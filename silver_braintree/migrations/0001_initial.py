# Copyright (c) 2017 Presslabs SRL
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import jsonfield
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('silver', '0032_auto_20170201_1342'),
    ]

    operations = [
        migrations.CreateModel(
            name='BraintreePaymentMethod',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('silver.paymentmethod',),
        ),
        migrations.CreateModel(
            name='CustomerData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('data', jsonfield.fields.JSONField(default={}, null=True, blank=True)),
                ('customer', models.ForeignKey(to='silver.Customer')),
            ],
        ),
    ]
