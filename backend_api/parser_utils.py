from decimal import Decimal, ROUND_FLOOR
import re

from backend_api.entities import ReceiptType

def check_sum(paid_sum: Decimal, value: str, receipt_type: ReceiptType, current_tariff):

    if receipt_type.service_name == 'membership_fee' and paid_sum == Decimal('2500.00'):
        return True


    if receipt_type.service_name == 'losses':
        t_price = Decimal(current_tariff.get('t0_tariff'))
        for v in value.split(','):
            if len(re.findall(r'{}'.format('показ'), v.lower())) > 0:
                try:
                    r = int(v.split(' ')[-1])
                    print(value)

                    result_sum = r * t_price * Decimal('0.15')
                    print(r * t_price)
                    print(result_sum.quantize(Decimal("1.00"), ROUND_FLOOR), 'FFFF')
                    print((r * t_price) + result_sum)
                    print(paid_sum, result_sum)
                except ValueError:
                    pass

        #result_sum = consumptions.r1 * t_price
        #result_sum = result_sum * Decimal('0.15')

    print('check_sumcheck_sumcheck_sumcheck_sumcheck_sumcheck_sumcheck_sum 2')
