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
from mock import patch, MagicMock
from braintree import Transaction as BraintreeTransaction

from silver.models import Transaction
from silver.payment_processors import get_instance
from silver_braintree.models.customer_data import CustomerData
from silver_braintree.payment_processors import (BraintreeTriggered,
                                                 BraintreeTriggeredRecurring)
from tests.factories import BraintreeTransactionFactory


class TestBraintreeTransactions:
    def setup_method(self):
        BraintreeTriggered._has_been_setup = True
        BraintreeTriggeredRecurring._has_been_setup = True

        transaction = MagicMock()
        transaction.amount = 1000
        transaction.status = BraintreeTransaction.Status.Settled
        transaction.id = 'beertrain'
        transaction.processor_response_code = 2000
        transaction.payment_instrument_type = 'paypal_account'

        transaction.paypal_details = MagicMock()
        transaction.paypal_details.image_url = 'image_url'
        transaction.paypal_details.payer_email = 'payer_email'
        transaction.paypal_details.token = 'kento'

        transaction.credit_card_details = MagicMock()
        transaction.credit_card_details.image_url = 'image_url'
        transaction.credit_card_details.last_4 = '1234'
        transaction.credit_card_details.card_type = 'card_type'
        transaction.credit_card_details.token = 'kento'

        transaction.customer_details = MagicMock()
        transaction.customer_details.id = 'braintree_id'

        self.transaction = transaction

        result = MagicMock()
        result.is_success = True
        result.transaction = transaction
        result.errors = MagicMock()
        result.errors.deep_errors = [MagicMock(code=2001), MagicMock(code=2042)]

        self.result = result

    def teardown_method(self):
        BraintreeTriggered._has_been_setup = False
        BraintreeTriggeredRecurring._has_been_setup = False

    @pytest.mark.django_db
    def test_update_status_transaction_settle(self):
        transaction = BraintreeTransactionFactory.create(
            state=Transaction.States.Pending, data={
                'braintree_id': 'beertrain'
            }
        )

        with patch('braintree.Transaction.find') as find_mock:
            find_mock.return_value = self.transaction
            payment_processor = get_instance(transaction.payment_processor)
            payment_processor.fetch_transaction_status(transaction)

            find_mock.assert_called_once_with('beertrain')

            assert transaction.state == transaction.States.Settled
            assert transaction.data.get('status') == self.result.transaction.status

    @pytest.mark.django_db
    def test_update_status_transaction_fail(self):
        transaction = BraintreeTransactionFactory.create(
            state=Transaction.States.Pending, data={
                'braintree_id': 'beertrain'
            }
        )
        with patch('braintree.Transaction.find') as find_mock:
            find_mock.return_value = self.transaction
            # fail status from braintree
            self.transaction.status = BraintreeTransaction.Status.ProcessorDeclined

            payment_processor = get_instance(transaction.payment_processor)
            payment_processor.fetch_transaction_status(transaction)

            find_mock.assert_called_once_with('beertrain')

            assert transaction.state == transaction.States.Failed
            assert transaction.data.get('status') == self.result.transaction.status

    @pytest.mark.django_db
    def test_execute_transaction_with_nonce_nonrecurring(self):
        transaction = BraintreeTransactionFactory.create()
        payment_method = transaction.payment_method
        payment_method.nonce = 'some-nonce'
        payment_method.save()

        with patch('braintree.Transaction.sale') as sale_mock:
            sale_mock.return_value = self.result
            payment_processor = get_instance(transaction.payment_processor)
            payment_processor.execute_transaction(transaction)

            sale_mock.assert_called_once_with({
                # new customer
                'customer': {'first_name': payment_method.customer.first_name,
                             'last_name': payment_method.customer.last_name},
                'amount': transaction.amount,
                'billing': {'postal_code': None},
                # don't store payment method in vault
                'options': {'store_in_vault': False,
                            'submit_for_settlement': True},
                'payment_method_nonce': payment_method.nonce
            })

            assert transaction.state == transaction.States.Settled

            payment_method.refresh_from_db()
            assert not payment_method.token

            assert payment_method.details == {
                'image_url': self.transaction.paypal_details.image_url,
                'email': self.transaction.paypal_details.payer_email,
                'type': self.transaction.payment_instrument_type,
            }

            assert (payment_method.display_info ==
                    self.transaction.paypal_details.payer_email)

            customer = transaction.customer
            customer_data = CustomerData.objects.filter(customer=customer)
            assert len(customer_data) == 1

            customer_data = customer_data[0]
            assert customer_data.get('id') == self.transaction.customer_details.id

            assert transaction.data.get('status') == self.result.transaction.status

    @pytest.mark.django_db
    def test_execute_transaction_with_token_recurring(self):
        transaction = BraintreeTransactionFactory.create()
        transaction.payment_method.payment_processor = 'BraintreeTriggeredRecurring'
        transaction.payment_method.save()

        payment_method = transaction.payment_method
        payment_method.token = 'kento'
        payment_method.save()

        customer = payment_method.customer
        customer_data = CustomerData.objects.create(
            customer=customer, data={'id': 'somethingelse'}
        )

        with patch('braintree.Transaction.sale') as sale_mock:
            sale_mock.return_value = self.result

            payment_processor = get_instance(transaction.payment_processor)
            payment_processor.execute_transaction(transaction)

            sale_mock.assert_called_once_with({
                # existing customer in vault
                'customer_id': customer_data['id'],
                'amount': transaction.amount,
                'billing': {'postal_code': None},
                'options': {'submit_for_settlement': True},
                # existing token
                'payment_method_token': payment_method.token
            })

            assert transaction.state == transaction.States.Settled

            payment_method.refresh_from_db()
            assert payment_method.token == self.transaction.paypal_details.token
            assert payment_method.details == {
                'image_url': self.transaction.paypal_details.image_url,
                'email': self.transaction.paypal_details.payer_email,
                'type': self.transaction.payment_instrument_type,
            }
            assert payment_method.verified
            assert (payment_method.display_info ==
                    self.transaction.paypal_details.payer_email)

            assert transaction.data.get('status') == self.result.transaction.status

    @pytest.mark.django_db
    def test_execute_transaction_with_nonce_recurring_paypal(self):
        transaction = BraintreeTransactionFactory.create()
        transaction.payment_method.payment_processor = 'BraintreeTriggeredRecurring'
        transaction.payment_method.save()

        nonce = 'some-nonce'
        payment_method = transaction.payment_method
        payment_method.nonce = nonce
        payment_method.save()

        with patch('braintree.Transaction.sale') as sale_mock:
            sale_mock.return_value = self.result

            payment_processor = get_instance(transaction.payment_processor)
            payment_processor.execute_transaction(transaction)

            sale_mock.assert_called_once_with({
                # create new customer in vault
                'customer': {'first_name': payment_method.customer.first_name,
                             'last_name': payment_method.customer.last_name},
                'amount': transaction.amount,
                'billing': {'postal_code': None},
                # store the payment method
                'options': {'store_in_vault': True,
                            'submit_for_settlement': True},
                'payment_method_nonce': nonce
            })

            assert transaction.state == transaction.States.Settled

            payment_method.refresh_from_db()
            assert payment_method.token == self.transaction.paypal_details.token
            assert payment_method.details == {
                'image_url': self.transaction.paypal_details.image_url,
                'email': self.transaction.paypal_details.payer_email,
                'type': self.transaction.payment_instrument_type,
            }
            assert payment_method.verified
            assert not payment_method.nonce
            assert (payment_method.display_info ==
                    self.transaction.paypal_details.payer_email)

            assert transaction.data.get('status') == self.result.transaction.status

            customer = transaction.customer

            customer_data = CustomerData.objects.filter(customer=customer)
            assert len(customer_data) == 1

            customer_data = customer_data[0]
            assert customer_data.get('id') == self.transaction.customer_details.id

    @pytest.mark.django_db
    def test_execute_transaction_with_nonce_recurring_credit_card(self):
        transaction = BraintreeTransactionFactory.create()
        transaction.payment_method.payment_processor = 'BraintreeTriggeredRecurring'
        transaction.payment_method.save()

        nonce = 'some-nonce'
        payment_method = transaction.payment_method
        payment_method.nonce = nonce
        payment_method.save()

        with patch('braintree.Transaction.sale') as sale_mock:
            self.result.transaction.payment_instrument_type = 'credit_card'
            sale_mock.return_value = self.result

            payment_processor = get_instance(transaction.payment_processor)
            payment_processor.execute_transaction(transaction)

            sale_mock.assert_called_once_with({
                # create new customer in vault
                'customer': {'first_name': payment_method.customer.first_name,
                             'last_name': payment_method.customer.last_name},
                'amount': transaction.amount,
                'billing': {'postal_code': None},
                # store the payment method
                'options': {'store_in_vault': True,
                            'submit_for_settlement': True},
                'payment_method_nonce': nonce
            })

            assert transaction.state == transaction.States.Settled

            payment_method.refresh_from_db()
            assert payment_method.token == self.transaction.credit_card_details.token
            assert payment_method.details == {
                'last_4': self.transaction.credit_card_details.last_4,
                'card_type': self.transaction.credit_card_details.card_type,
                'type': self.transaction.payment_instrument_type,
                'image_url': self.transaction.credit_card_details.image_url
            }
            assert payment_method.verified
            assert not payment_method.nonce

            assert transaction.data.get('status') == self.result.transaction.status

            customer = transaction.customer

            customer_data = CustomerData.objects.filter(customer=customer)
            assert len(customer_data) == 1

            customer_data = customer_data[0]

            assert customer_data.get('id') == self.transaction.customer_details.id

    @pytest.mark.django_db
    def test_execute_transaction_with_canceled_payment_method(self):
        transaction = BraintreeTransactionFactory.create(
            payment_processor='BraintreeTriggered'
        )

        nonce = 'some-nonce'
        payment_method = transaction.payment_method
        payment_method.nonce = nonce
        payment_method.canceled = True
        payment_method.save()

        with patch('braintree.Transaction.sale') as sale_mock:
            payment_processor = get_instance(transaction.payment_processor)
            assert payment_processor.execute_transaction(transaction) is False
            assert sale_mock.call_count == 0

    @pytest.mark.django_db
    def test_execute_transaction_with_payment_method_without_nonce_or_token(self):
        transaction = BraintreeTransactionFactory.create(
            payment_processor='BraintreeTriggered'
        )

        with patch('braintree.Transaction.sale') as sale_mock:
            payment_processor = get_instance(transaction.payment_processor)

            assert payment_processor.execute_transaction(transaction) is False
            assert sale_mock.call_count == 0

    @pytest.mark.django_db
    def test_execute_transaction_failed_braintree_response(self):
        transaction = BraintreeTransactionFactory.create(
            payment_processor='BraintreeTriggered'
        )

        nonce = 'some-nonce'
        payment_method = transaction.payment_method
        payment_method.nonce = nonce
        payment_method.save()

        with patch('braintree.Transaction.sale') as sale_mock:
            self.result.is_success = False
            sale_mock.return_value = self.result

            payment_processor = get_instance(transaction.payment_processor)
            assert payment_processor.execute_transaction(transaction) is False
            assert transaction.data.get('error_codes') == [
                error.code for error in self.result.errors.deep_errors
            ]
