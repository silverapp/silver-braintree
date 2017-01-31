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

import braintree as sdk
from braintree.exceptions import NotFoundError

from silver.models import PaymentMethod


class BraintreePaymentMethod(PaymentMethod):
    """
        data field structure
        {
            'nonce': 'some-nonce', (encrypted, deleted if token exists)
            'token': 'some-token', (encrypted)
            'braintree_id': 'transaction-id-given-by-braintree',
            'status': 'status-given-by-braintree' (does not exist if
                                                   Transaction.state is Initial)
            'details': {
                - common -
                'type': Types.PayPal | Types.CreditCard,
                'image_url': 'payment-processor-icon-url-given-by-braintree',
                - PayPal -
                'email': 'some@ema.il' (PayPal account email)
                - CreditCard -
                'last_4': '1234' (last 4 digits from the credit card number)
                'card_type': e.g. 'Visa',
                'postal_code': '41234Y' (if provided from template)
            }
        }
    """
    class Meta:
        proxy = True

    class Types:
        PayPal = 'paypal_account'
        CreditCard = 'credit_card'

    @property
    def braintree_transaction(self):
        try:
            return sdk.Transaction.find(self.braintree_id)
        except NotFoundError:
            return None

    @property
    def braintree_id(self):
        return self.data.get('braintree_id')

    @property
    def token(self):
        return self.decrypt_data(self.data.get('token'))

    @token.setter
    def token(self, value):
        self.data['token'] = self.encrypt_data(value)

    @property
    def nonce(self):
        return self.decrypt_data(self.data.get('nonce'))

    @nonce.setter
    def nonce(self, value):
        self.data['nonce'] = self.encrypt_data(value)

    def update_details(self, details):
        if 'details' not in self.data:
            self.data['details'] = details
        else:
            self.data['details'].update(details)

    @property
    def details(self):
        return self.data.get('details')

    @property
    def public_data(self):
        return self.data.get('details')
