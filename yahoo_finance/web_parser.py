from stock_data import *
from util import parse_pc, get_number_from_currency

class WebParser:

    def get_map_from_tr_list(self, tr_list):
        map = {}
        for tr in tr_list:
            map[next(tr.getiterator('span')).text_content()] = tr.getchildren()[1].text_content()
        return map;


    def get_summary(self, tr_list):
        map = self.get_map_from_tr_list(tr_list)
        return Summary(map['Previous Close'],
                       map['Open'],
                       map['Bid'],
                       map['Ask'],
                       map["Day's Range"],
                       map['52 Week Range'],
                       map['Volume'],
                       map['Avg. Volume'],
                       get_number_from_currency(map.get('Market Cap', None)),
                       map.get('Beta', None),
                       map['PE Ratio (TTM)'],
                       map['EPS (TTM)'],
                       map['Earnings Date'],
                       map['Forward Dividend & Yield'],
                       map['Ex-Dividend Date'],
                       map['1y Target Est'])


    def get_valuation_measures(self, stats_map):
        return ValuationMeasures(get_number_from_currency(stats_map.get('Market Cap (intraday)', None)),
                                 get_number_from_currency(stats_map['Enterprise Value']),
                                 stats_map['Trailing P/E'],
                                 stats_map['Forward P/E'],
                                 stats_map['PEG Ratio (5 yr expected)'],
                                 stats_map['Price/Sales'],
                                 stats_map['Price/Book'],
                                 stats_map['Enterprise Value/Revenue'],
                                 stats_map['Enterprise Value/EBITDA'])


    def get_profitability(self, stats_map):
        return Profitability(parse_pc(stats_map['Profit Margin']),
                             parse_pc(stats_map['Operating Margin']))


    def get_mgmt_effectiveness(self, stats_map):
        return MgmtEffectiveness(parse_pc(stats_map.get('Return on Assets', None)),
                                 parse_pc(stats_map.get('Return on Equity', None)))


    def get_income_stmt(self, stats_map):
        return IncomeStatement(revenue_ttm=get_number_from_currency(stats_map['Revenue']),
                               revenue_per_share_ttm=stats_map['Revenue Per Share'],
                               q_revenue_growth=parse_pc(stats_map['Quarterly Revenue Growth']),
                               gross_profit_ttm=get_number_from_currency(stats_map['Gross Profit']),
                               ebitda=get_number_from_currency(stats_map['EBITDA']),
                               net_income_avi_to_common_ttm=stats_map['Net Income Avi to Common'],
                               diluted_eps_ttm=stats_map['Diluted EPS'],
                               q_earnings_growth=parse_pc(stats_map['Quarterly Earnings Growth']))


    def get_balance_sheet(self, stats_map):
        return BalanceSheet(total_cash=get_number_from_currency(stats_map['Total Cash']),
                            total_cash_per_share=stats_map['Total Cash Per Share'],
                            total_debt= get_number_from_currency(stats_map['Total Debt']),
                            total_debt_per_equity=stats_map['Total Debt/Equity'],
                            curr_ratio=stats_map['Current Ratio'],
                            book_val_per_share=stats_map['Book Value Per Share'])


    def get_cash_flow_stmt(self, stats_map):
        return CashFlowStmt(operating_cash_flow_ttm=get_number_from_currency(stats_map.get('Operating Cash Flow', None)),
                            levered_cash_flow_ttm=get_number_from_currency(stats_map.get('Levered Free Cash Flow', None)))


    def get_stock_price_history(self, stats_map):
        return StockPriceHistory(parse_pc(stats_map.get('52-Week Change', None)),
                                 stats_map['52 Week High'],
                                 stats_map['52 Week Low'],
                                 stats_map['50-Day Moving Average'],
                                 stats_map['200-Day Moving Average'])


    def get_share_stats(self, stats_map):
        return ShareStats(avg_vol_3_day=stats_map['Avg Vol (3 month)'],
                          avg_vol_10_day=stats_map['Avg Vol (10 day)'],
                          shares_outstanding=get_number_from_currency(stats_map['Shares Outstanding']),
                          shares_float=stats_map['Float'],
                          shares_short=stats_map.get('Shares Short', None),
                          short_ratio=stats_map.get('Short Ratio', None),
                          short_pc_of_float=stats_map.get('Short % of Float', None),
                          shares_short_prior_month=stats_map.get('Shares Short (prior month)', None))


    def get_dividends(self, stats_map):
        return Dividends(stats_map['Forward Annual Dividend Rate'],
                         stats_map['Forward Annual Dividend Yield'],
                         stats_map['Trailing Annual Dividend Rate'],
                         stats_map['Trailing Annual Dividend Yield'],
                         stats_map['5 Year Average Dividend Yield'],
                         stats_map['Payout Ratio'],
                         stats_map['Dividend Date'],
                         stats_map['Ex-Dividend Date'])


    def get_split(self, stats_map):
        return Split(stats_map['Last Split Factor'],
                     stats_map['Last Split Date'])


    def get_major_holders(self, stats_map):
        return MajorHolders(stats_map['% Held by Insiders'],
                            stats_map['% Held by Institutions'])