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
import braintree

import django
from django.conf import settings


settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
        }
    },
    PAYMENT_METHOD_SECRET=b'MOW_x1k-ayes3KqnFHNZUxvKipC8iLjxiczEN76TIEA=',
    PAYMENT_PROCESSORS={
        'BraintreeTriggered': {
            'setup_data': {
                'environment': braintree.Environment.Sandbox,
                'merchant_id': "your-merchand-id-here",
                'public_key': "your-public-id-here",
                'private_key': "your-private-id-here"
            },
            'class': 'silver_braintree.payment_processors.BraintreeTriggered',
        },
        'BraintreeTriggeredRecurring': {
            'setup_data': {
                'environment': braintree.Environment.Sandbox,
                'merchant_id': "your-merchand-id-here",
                'public_key': "your-public-id-here",
                'private_key': "your-private-id-here"
            },
            'class': 'silver_braintree.payment_processors.BraintreeTriggeredRecurring'
        },
        'Manual': {
            'class': 'silver.models.payment_processors.manual.ManualProcessor'
        }
    },
    INSTALLED_APPS=(
                    'dal',
                    'dal_select2',
                    'django.contrib.auth',
                    'django.contrib.contenttypes',
                    'django.contrib.sessions',
                    'django.contrib.staticfiles',
                    'django.contrib.admin',
                    'silver',
                    'silver_braintree',),
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
            'LOCATION': 'unique-snowflake',
        }
    },
    USE_TZ=True,
    STATIC_URL='/static/'
)

django.setup()
