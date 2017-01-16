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

import pytest
from django_dynamic_fixture import G
from mock import patch
from braintree import Transaction as BraintreeTransaction

from silver.models import PaymentProcessorManager
from silver.models import Transaction

from silver_braintree.models import BraintreePaymentMethod
from silver_braintree.models import BraintreeTriggered


class TestBraintreeTransactions:
    def setup_method(self):
        BraintreeTriggered._has_been_setup = True
        PaymentProcessorManager.register(BraintreeTriggered,
                                         display_name='Braintree')

        class Object(object):
            pass

        transaction = Object()
        transaction.amount = 1000
        transaction.status = BraintreeTransaction.Status.Settled
        transaction.id = 'beertrain'
        transaction.processor_response_code = 2000
        transaction.payment_instrument_type = 'paypal_account'

        transaction.paypal_details = Object()
        transaction.paypal_details.image_url = 'image_url'
        transaction.paypal_details.payer_email = 'payer_email'
        transaction.paypal_details.token = 'kento'

        transaction.customer_details = Object()
        transaction.customer_details.id = 'braintree_id'

        self.transaction = transaction

        result = Object()
        result.is_success = True
        result.transaction = transaction
        self.result = result

    def teardown_method(self):
        BraintreeTriggered._has_been_setup = False
        PaymentProcessorManager.unregister(BraintreeTriggered)

    def create_braintree_payment_method(self, *args, **kwargs):
        return G(BraintreePaymentMethod, payment_processor=BraintreeTriggered,
                 *args, **kwargs)

    def create_braintree_transaction(self, *args, **kwargs):
        return G(Transaction,
                 payment_method=self.create_braintree_payment_method(),
                 *args, **kwargs)

    @pytest.mark.django_db
    def test_update_status_transaction_settle(self):
        transaction = self.create_braintree_transaction(
            state=Transaction.States.Pending, data={
                'braintree_id': 'beertrain'
            }
        )

        with patch('braintree.Transaction.find') as find_mock:
            find_mock.return_value = self.transaction
            transaction.payment_processor.update_transaction_status(transaction)

            find_mock.assert_called_once_with('beertrain')

            assert transaction.state == transaction.States.Settled

    @pytest.mark.django_db
    def test_update_status_transaction_fail(self):
        self.transaction.status = BraintreeTransaction.Status.ProcessorDeclined
        transaction = self.create_braintree_transaction(
            state=Transaction.States.Pending, data={
                'braintree_id': 'beertrain'
            }
        )
        with patch('braintree.Transaction.find') as find_mock:
            find_mock.return_value = self.transaction
            transaction.payment_processor.update_transaction_status(transaction)

            find_mock.assert_called_once_with('beertrain')

            assert transaction.state == transaction.States.Failed

    @pytest.mark.django_db
    def test_execute_transaction_with_nonce(self):
        transaction = self.create_braintree_transaction()
        payment_method = transaction.payment_method
        payment_method.nonce = 'some-nonce'
        payment_method.is_recurring = True
        payment_method.save()

        with patch('braintree.Transaction.sale') as sale_mock:
            sale_mock.return_value = self.result
            transaction.payment_processor.execute_transaction(transaction)

            sale_mock.assert_called_once_with({
                'customer': {'first_name': payment_method.customer.first_name,
                             'last_name': payment_method.customer.last_name},
                'amount': transaction.amount,
                'billing': {'postal_code': None},
                'options': {'store_in_vault': True,
                            'submit_for_settlement': True},
                'payment_method_nonce': payment_method.nonce
            })

            assert transaction.state == transaction.States.Settled

            payment_method = transaction.payment_method
            assert payment_method.token == self.transaction.paypal_details.token
            assert payment_method.data.get('details') == {
                'image_url': self.transaction.paypal_details.image_url,
                'email': self.transaction.paypal_details.payer_email,
                'type': self.transaction.payment_instrument_type,
            }
            assert payment_method.verified

            customer = transaction.customer
            assert customer.meta.get('braintree_id') == \
                self.transaction.customer_details.id

    @pytest.mark.django_db
    def test_execute_transaction_with_token(self):
        transaction = self.create_braintree_transaction()
        payment_method = transaction.payment_method
        payment_method.token = self.transaction.paypal_details.token
        payment_method.is_recurring = True
        payment_method.save()

        with patch('braintree.Transaction.sale') as sale_mock:
            sale_mock.return_value = self.result
            transaction.payment_processor.execute_transaction(transaction)

            sale_mock.assert_called_once_with({
                'customer_id': transaction.customer.meta['braintree_id'],
                'amount': transaction.amount,
                'billing': {'postal_code': None},
                'options': {'submit_for_settlement': True},
                'payment_method_token': payment_method.token
            })

            assert transaction.state == transaction.States.Settled

            payment_method = transaction.payment_method
            assert payment_method.token == self.transaction.paypal_details.token
            assert payment_method.data.get('details') == {
                'image_url': self.transaction.paypal_details.image_url,
                'email': self.transaction.paypal_details.payer_email,
                'type': self.transaction.payment_instrument_type,
            }
            assert payment_method.verified

            customer = transaction.customer
            assert customer.meta.get('braintree_id') == \
                self.transaction.customer_details.id
