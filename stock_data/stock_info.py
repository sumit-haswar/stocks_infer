import json
import datetime

class StockInfo:

    def __init__(self):
        self.Summary  = None
        self.ValuationMeasures = None
        self.Profitability = None
        self.ManagementEffectiveness = None
        self.IncomeStatement = None
        self.BalanceSheet = None
        self.CashFlowStatement = None
        self.Dividends = None
        self.MajorHolders = None
        self.ShareStatistics = None
        self.Splits = None
        self.StockPriceHistory = None


    def to_json(self):
        return json.dumps(self, default=self.json_converter, sort_keys=True)

    def json_converter(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        else:
            return obj.__dict__