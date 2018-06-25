import re

def get_number_from_currency(val):
    """
    gets numeric value for string currency
    :param val: example: "23.4B" "10.5B" or "12000"
    :return: float/int representation of "23.4M"
    """
    fl_val = re.findall("\d+\.\d+", val)[0]
    factor = 1;
    suffix = next((i for i in val if i.isalpha()), '')
    if suffix == 'M':
        factor = 1000000
    elif suffix == 'B':
        factor = 1000000000

    return fl_val * factor


def parse_float(val):
    return float(''.join(i for i in val if i.isnumeric() or i == '.') or 0)