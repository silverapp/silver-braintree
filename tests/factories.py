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

from silver_braintree.models import BraintreeTriggered

from silver.models import PaymentProcessorManager
from silver.tests.factories import TransactionFactory, PaymentMethodFactory


class BraintreePaymentMethodFactory(PaymentMethodFactory):
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        kwargs['payment_processor'] = PaymentProcessorManager.get_instance(
            BraintreeTriggered.reference
        )

        return super(BraintreePaymentMethodFactory, cls)._create(
            model_class, *args, **kwargs
        )


class BraintreeTransactionFactory(TransactionFactory):
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # overriding the payment_method field didn't work
        kwargs['payment_method'] = BraintreePaymentMethodFactory.create()

        return super(BraintreeTransactionFactory, cls)._create(
            model_class, *args, **kwargs
        )
