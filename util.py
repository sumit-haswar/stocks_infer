import re
from re import sub
from decimal import Decimal
import datetime


def get_number_from_currency(val):
    """
    gets numeric value for string currency
    :param val: example: "23.4B" "10.5B" or "12000"
    :return: float/int representation of "23.4M"
    """
    number = None
    try:
        number = Decimal(sub(r'[^\d\-.]', '', val))
    except:
        return number

    factor = 1
    suffix = next((i for i in val if i.isalpha()), '')
    if suffix == 'M':
        factor = 1000000
    elif suffix == 'B':
        factor = 1000000000
    elif suffix == 'T':
        factor = 1000000000000

    return number * factor


def get_currency_from_number(val):
    """
    gets readable currency value in string for numbers
    :param val: number (example: 24670000000, 140100000000)
    :return: currency rep. of numbers in the form "24.67B", "23.4M"
    """
    if 1000 > val / 1000000000000 > 1:  # T
        return "{0}T".format(val / 1000000000000)
    elif 1000 > val / 1000000000 > 1:    # B
        return "{0}B".format(val / 1000000000)
    elif 1000 > val / 1000000 > 1:       # M
        return "{0}M".format(val / 1000000)
    else:
        return "{0}".format(val)


def parse_float(val):
    return float(''.join(i for i in val if i.isnumeric() or i == '.') or 0) if val else None


def parse_pc(val):
    fl_val = re.findall("\d+\.\d+", val)
    return fl_val[0] if fl_val else None


def json_converter(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return str(obj)
    else:
        return obj.__dict__
