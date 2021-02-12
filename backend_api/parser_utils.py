from decimal import Decimal, ROUND_FLOOR, InvalidOperation
import re

from backend_api.entities import ReceiptType

def check_sum(paid_sum: Decimal, value: str, receipt_type: ReceiptType, current_tariff):

    if receipt_type.service_name == 'membership_fee' and paid_sum == Decimal('2500.00'):
        return True


    if receipt_type.service_name == 'losses':
        t_price = Decimal(current_tariff.get('t0_tariff'))
        for v in value.split(','):
            if len(re.findall(r'{}'.format('расх'), v.lower())) > 0:
                try:
                    r = int(re.findall('\d+', '{}'.format(v.split(' ')[-1]))[-1])
                    result_sum = round((r * t_price) * Decimal('0.15'))

                    if paid_sum == result_sum:
                        return True

                except IndexError:
                    pass

    if receipt_type.service_name == 'electricity':
        r1 = None
        r2 = None
        key_word_found = False

        if receipt_type.counter_type == 2:
            if len(re.findall(r'{}'.format('расх'), value.lower())) > 0:
                for v in value.split(' '):
                    if len(re.findall(r'{}'.format('расх'), v.lower())) > 0:
                        key_word_found = True
                    else:
                        if key_word_found:
                            if r1 == None:
                                print(v, '<--------------------------------')
                                try:
                                    r1 = Decimal(v)
                                except InvalidOperation:
                                    r1 = Decimal('0.00')
                            else:
                                try:
                                    r2 = Decimal(v)
                                except InvalidOperation:
                                    r1 = Decimal('0.00')
                            key_word_found = False



            if r1 and r2:
                t1_sum = r1 * Decimal(current_tariff.get('t1_tariff'))

                t2_sum = r2 * Decimal(current_tariff.get('t2_tariff'))
                result_sum = t1_sum + t2_sum
                r1 = None
                r2 = None
                if result_sum.quantize(Decimal("1.00"), ROUND_FLOOR) == paid_sum:
                    return True

        if receipt_type.counter_type == 1:
            if len(re.findall(r'{}'.format('расх'), value.lower())) > 0:
                for v in value.split(' '):
                    if len(re.findall(r'{}'.format('расх'), v.lower())) > 0:
                        key_word_found = True
                    else:
                        if key_word_found:
                            if len(re.findall('\d+', v)) > 0 and r1 == None:
                                r1 = Decimal(re.findall('\d+', v)[0])

            if r1:
                result_sum = r1 * Decimal(current_tariff.get('t0_tariff'))
                if result_sum.quantize(Decimal("1.00"), ROUND_FLOOR) == paid_sum:
                    return True

