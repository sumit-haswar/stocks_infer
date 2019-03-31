from util import parse_float

class BalanceSheet:

    def __init__(self, total_cash, total_cash_per_share, total_debt,
                 total_debt_per_equity, curr_ratio, book_val_per_share):
        self.total_cash = total_cash
        self.total_cash_per_share = parse_float(total_cash_per_share)
        self.total_debt = total_debt
        self.total_debt_per_equity = parse_float(total_debt_per_equity)
        self.curr_ratio = parse_float(curr_ratio)
        self.book_val_per_share = parse_float(book_val_per_share)
