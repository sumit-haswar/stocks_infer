import json
import datetime
from decimal import Decimal
from util import json_converter


class StockInfo:

    def __init__(self):
        self.summary = None
        self.valuation_measures = None
        self.profitability = None
        self.management_effectiveness = None
        self.income_statement = None
        self.balance_sheet = None
        self.cash_flow_statement = None
        self.dividends = None
        self.major_holders = None
        self.share_statistics = None
        self.splits = None
        self.stock_price_history = None

    def to_json(self):
        return json.dumps(self, default=json_converter, sort_keys=False)
