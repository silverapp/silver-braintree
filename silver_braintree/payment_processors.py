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

import logging

import braintree
from braintree.exceptions import (AuthenticationError, AuthorizationError,
                                  DownForMaintenanceError, ServerError,
                                  UpgradeRequiredError)
from django_fsm import TransitionNotAllowed


from silver.payment_processors import PaymentProcessorBase, get_instance
from silver.payment_processors.forms import GenericTransactionForm
from silver.payment_processors.mixins import TriggeredProcessorMixin

from silver_braintree.models import BraintreePaymentMethod
from silver_braintree.models.customer_data import CustomerData
from silver_braintree.views import BraintreeTransactionView


logger = logging.getLogger(__name__)


class BraintreeTriggeredBase(PaymentProcessorBase, TriggeredProcessorMixin):
    payment_method_class = BraintreePaymentMethod
    transaction_view_class = BraintreeTransactionView
    form_class = GenericTransactionForm
    template_slug = 'braintree'

    _has_been_setup = False

    def is_payment_method_recurring(self, payment_method):
        raise NotImplementedError

    def __init__(self, name, *args, **kwargs):
        super(BraintreeTriggeredBase, self).__init__(name)

        if self._has_been_setup:
            return

        environment = kwargs.pop('environment', None)
        braintree.Configuration.configure(environment, **kwargs)

        BraintreeTriggeredBase._has_been_setup = True

    def client_token(self, customer):
        customer_data = CustomerData.objects.get_or_create(customer=customer)[0]
        customer_braintree_id = customer_data.get('id')

        try:
            return braintree.ClientToken.generate(
                {'customer_id': customer_braintree_id}
            )
        except (AuthenticationError, AuthorizationError, DownForMaintenanceError,
                ServerError, UpgradeRequiredError) as e:
            logger.warning(
                'Couldn\'t obtain Braintree client_token %s', {
                    'customer_id': customer_braintree_id,
                    'exception': str(e)
                }
            )

    def refund_transaction(self, transaction, payment_method=None):
        pass

    def void_transaction(self, transaction, payment_method=None):
        pass

    def _update_payment_method(self, payment_method, result_details,
                               instrument_type):
        """
        :param payment_method: A BraintreePaymentMethod.
        :param result_details: A (part of) braintreeSDK result(response)
                               containing payment method information.
        :param instrument_type: The type of the instrument (payment method);
                                see BraintreePaymentMethod.Types.
        :description: Updates a given payment method's data with data from a
                      braintreeSDK result payment method.
        """
        payment_method_details = {
            'type': instrument_type,
            'image_url': result_details.image_url,
        }

        if instrument_type == payment_method.Types.PayPal:
            payment_method_details['email'] = result_details.payer_email
        elif instrument_type == payment_method.Types.CreditCard:
            payment_method_details.update({
                'card_type': result_details.card_type,
                'last_4': result_details.last_4,
            })

        payment_method.update_details(payment_method_details)

        if self.is_payment_method_recurring(payment_method):
            if result_details.token:
                payment_method.token = result_details.token
                payment_method.data.pop('nonce', None)
                payment_method.verified = True

        payment_method.save()

    def _update_transaction_status(self, transaction, result_transaction):
        """
        :param transaction: A Transaction.
        :param result_transaction: A transaction from a braintreeSDK
                                   result(response).
        :description: Updates a given transaction's data with data from a
                      braintreeSDK result payment method.
        :returns True if transaction is on the happy path, False otherwise.
        """
        if not transaction.data:
            transaction.data = {}

        transaction.external_reference = result_transaction.id
        status = result_transaction.status

        transaction.data['status'] = status

        target_state = None
        try:
            if status in [braintree.Transaction.Status.AuthorizationExpired,
                          braintree.Transaction.Status.SettlementDeclined,
                          braintree.Transaction.Status.Failed,
                          braintree.Transaction.Status.GatewayRejected,
                          braintree.Transaction.Status.ProcessorDeclined]:
                target_state = transaction.States.Failed
                if transaction.state != target_state:
                    fail_code = self._get_silver_fail_code(result_transaction)
                    fail_reason = self._get_braintree_fail_code(result_transaction)
                    transaction.fail(fail_code=fail_code, fail_reason=fail_reason)
                    return False

            elif status == braintree.Transaction.Status.Voided:
                target_state = transaction.States.Canceled
                if transaction.state != target_state:
                    transaction.cancel()
                    return False

            elif status in [braintree.Transaction.Status.Settling,
                            braintree.Transaction.Status.SettlementPending,
                            braintree.Transaction.Status.Settled]:
                target_state = transaction.States.Settled
                if transaction.state != target_state:
                    transaction.settle()
                    return True
            else:
                return True
        except TransitionNotAllowed as e:
            logger.warning('Braintree Transaction couldn\'t transition locally: '
                           '%s' % {
                               'initial_state': transaction.state,
                               'target_state': target_state,
                               'transaction_id': transaction.id,
                               'transaction_uuid': transaction.uuid
                           })
            raise e
        finally:
            transaction.save()

    def _update_customer(self, customer, result_details):
        customer_data = CustomerData.objects.get_or_create(customer=customer)[0]
        if 'id' not in customer_data:
            customer_data['id'] = result_details.id
            customer_data.save()

    def _get_errors(self, result):
        return [
            error.code for error in result.errors.deep_errors
        ] if result.errors else None

    def _get_braintree_fail_code(self, result_transaction):
        if result_transaction.status in (
                braintree.Transaction.Status.ProcessorDeclined,
                braintree.Transaction.Status.AuthorizationExpired
        ):
            return result_transaction.processor_response_code,

        elif result_transaction.status in (
                braintree.Transaction.Status.SettlementDeclined,
                braintree.Transaction.Status.SettlementFailed
        ):
            return result_transaction.processor_settlement_response_code,

    def _get_silver_fail_code(self, result_transaction):
        braintree_fail_code = self._get_braintree_fail_code(result_transaction)

        if not braintree_fail_code:
            return 'default'

        if braintree_fail_code in [2001]:
            return 'insufficient_funds'
        elif braintree_fail_code in [2022]:
            return 'expired_payment_method'
        elif braintree_fail_code in [2004, 2022]:
            return 'expired_card'
        elif braintree_fail_code in [2071, 2072, 2073]:
            return 'invalid_payment_method'
        elif braintree_fail_code in [2005, 2006]:
            return 'invalid_card'
        elif braintree_fail_code in [2002, 2003, 2086]:
            return 'limit_exceeded'
        elif braintree_fail_code in [2000, 2010, 2019, 2038, 2046, 2061, 2062,
                                     2064]:
            return 'transaction_declined_by_bank'
        elif braintree_fail_code in [2075, 2076, 2077]:
            return 'transaction_hard_declined'
        elif braintree_fail_code in [2012, 2013, 2014, 2074]:
            return 'transaction_hard_declined_by_bank'

        return 'default'

    def _charge_transaction(self, transaction):
        """
        :param transaction: The transaction to be charged. Must have a useable
                            payment_method.
        :return: True on success, False on failure.
        """
        payment_method = transaction.payment_method

        if payment_method.canceled:
            try:
                transaction.fail(fail_reason='Payment method was canceled.')
                transaction.save()
            finally:
                return False

        # prepare payload
        options = {
            'submit_for_settlement': True,
        }

        if payment_method.token:
            payload = {'payment_method_token': payment_method.token}
        elif payment_method.nonce:
            options.update({
                "store_in_vault": self.is_payment_method_recurring(payment_method)
            })
            payload = {'payment_method_nonce': payment_method.nonce}
        else:
            logger.warning('Token or nonce not found when charging '
                           'BraintreePaymentMethod: %s', {
                               'payment_method_id': payment_method.id
                           })

            try:
                transaction.fail(fail_reason='Payment method has no token or nonce.')
                transaction.save()
            finally:
                return False

        payload.update({
            'amount': transaction.amount,
            'billing': {
                'postal_code': payment_method.data.get('postal_code')
            },
            # TODO check how firstname and lastname can be obtained (for both
            # credit card and paypal)
            'options': options
        })

        customer = transaction.customer
        customer_data = CustomerData.objects.get_or_create(customer=customer)[0]

        if 'id' in customer_data:
            payload.update({
                'customer_id': customer_data['id']
            })
        else:
            payload.update({
                'customer': {
                    'first_name': customer.first_name,
                    'last_name': customer.last_name
                }
            })

        # send transaction request
        result = braintree.Transaction.sale(payload)

        # handle response
        if not result.is_success or not result.transaction:
            errors = self._get_errors(result)
            logger.warning('Couldn\'t charge Braintree transaction.: %s', {
                'message': result.message,
                'errors': errors,
                'customer_id': customer.id,
                'card_verification': (result.credit_card_verification if errors
                                      else None)
            })

            transaction.data['error_codes'] = errors
            try:
                fail_code = self._get_silver_fail_code(result.transaction)
                transaction.fail(fail_code=fail_code, fail_reason=errors)
            finally:
                transaction.save()

                return False

        self._update_customer(customer, result.transaction.customer_details)

        instrument_type = result.transaction.payment_instrument_type

        if instrument_type == payment_method.Types.PayPal:
            details = result.transaction.paypal_details
        elif instrument_type == payment_method.Types.CreditCard:
            details = result.transaction.credit_card_details
        else:
            # Only PayPal and CreditCard are currently handled
            try:
                transaction.fail(fail_code='invalid_payment_method',
                                 fail_reason='Not a supported instrument_type')
                transaction.save()
            finally:
                return False

        self._update_payment_method(
            payment_method, details, instrument_type
        )

        try:
            return self._update_transaction_status(transaction,
                                                   result.transaction)
        except TransitionNotAllowed:
            # ToDo handle this
            return False

    def execute_transaction(self, transaction):
        """
        :param transaction: A Braintree transaction in Initial state.
        :return: True on success, False on failure.
        """

        payment_processor = get_instance(transaction.payment_processor)
        if not payment_processor == self:
            return False

        if transaction.state != transaction.States.Initial:
            return False

        try:
            transaction.process()
            transaction.save()
        except TransitionNotAllowed:
            return False

        return self._charge_transaction(transaction)

    def fetch_transaction_status(self, transaction):
        """
        :param transaction: A Braintree transaction in Initial or Pending state.
        :return: True on success, False on failure.
        """

        payment_processor = get_instance(transaction.payment_processor)
        if not payment_processor == self:
            return False

        if transaction.state != transaction.States.Pending:
            return False

        if not transaction.data.get('braintree_id'):
            logger.warning('Found pending Braintree transaction with no '
                           'braintree_id: %s', {
                                'transaction_id': transaction.id,
                                'transaction_uuid': transaction.uuid
                           })

            return False

        try:
            result_transaction = braintree.Transaction.find(
                transaction.data['braintree_id']
            )
            return self._update_transaction_status(transaction,
                                                   result_transaction)
        except braintree.exceptions.NotFoundError:
            logger.warning('Couldn\'t find Braintree transaction from '
                           'Braintree %s', {
                                'braintree_id': transaction.data['braintree_id'],
                                'transaction_id': transaction.id,
                                'transaction_uuid': transaction.uuid
                           })
            return False
        except TransitionNotAllowed:
            return False
            # ToDo handle this

    def handle_transaction_response(self, transaction, request):
        payment_method_nonce = request.POST.get('payment_method_nonce')

        payment_method = transaction.payment_method
        if not payment_method_nonce:
            try:
                transaction.fail(fail_reason='payment_method_nonce was not provided.')
                transaction.save()
            except TransitionNotAllowed:
                pass
            finally:
                return

        if payment_method.nonce:
            try:
                transaction.fail(fail_reason='Payment method already has a nonce.')
                transaction.save()
            except TransitionNotAllowed:
                pass
            finally:
                return

        # initialize the payment method
        details = {
            'postal_code': request.POST.get('postal_code')
        }

        payment_method.nonce = payment_method_nonce
        payment_method.update_details(details)
        payment_method.save()

        # manage the transaction
        payment_processor = get_instance(payment_method.payment_processor)

        if not payment_processor.execute_transaction(transaction):
            try:
                transaction.fail()
                transaction.save()
            except TransitionNotAllowed:
                pass
            finally:
                return


class BraintreeTriggered(BraintreeTriggeredBase):
    def is_payment_method_recurring(self, payment_method):
        return False


class BraintreeTriggeredRecurring(BraintreeTriggeredBase):
    def is_payment_method_recurring(self, payment_method):
        return True
