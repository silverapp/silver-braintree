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

from django_fsm import TransitionNotAllowed
from django.http import HttpResponse, HttpResponseBadRequest

from silver.views import GenericTransactionView
from silver.utils.payments import get_payment_complete_url


class BraintreeTransactionView(GenericTransactionView):
    def get_context_data(self):
        context_data = super(BraintreeTransactionView, self).get_context_data()
        context_data.update(
            {
                'client_token': self.transaction.payment_processor.client_token(
                    self.transaction.customer
                ),
                'complete_url': get_payment_complete_url(self.transaction,
                                                         self.request)
            }
        )

        return context_data
