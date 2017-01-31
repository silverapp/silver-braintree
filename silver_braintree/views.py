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

from silver.payment_processors import get_instance
from silver.payment_processors.views import GenericTransactionView


class BraintreeTransactionView(GenericTransactionView):
    def get_context_data(self):
        context_data = super(BraintreeTransactionView, self).get_context_data()
        payment_processor = get_instance(self.transaction.payment_processor)
        context_data['client_token'] = payment_processor.client_token(
                self.transaction.customer
        )
        context_data['is_recurring'] = payment_processor.is_payment_method_recurring(
            self.transaction.payment_method
        )

        return context_data
