from stock_data import *

class WebParser:

    def get_map_from_tr_list(self, tr_list):
        map = {}
        for tr in tr_list:
            map[next(tr.getiterator('span')).text_content()] = tr.getchildren()[1].text_content()
        return map;


    def get_summary(self, tr_list):
        map = self.get_map_from_tr_list(tr_list)
        return Summary(map['Previous Close'], map['Open'], map['Bid'], map['Ask'],
                      map["Day's Range"],map['52 Week Range'],map['Volume'],map['Avg. Volume'],
                      map['Market Cap'], map['Beta'], map['PE Ratio (TTM)'], map['EPS (TTM)'],
                      map['Earnings Date'], map['Forward Dividend & Yield'],
                      map['Ex-Dividend Date'],map['1y Target Est'])


    def get_valuation_measures(self, stats_map):
        return ValuationMeasures(stats_map['Market Cap (intraday)'],
                                 stats_map['Enterprise Value'],
                                 stats_map['Trailing P/E'],
                                 stats_map['Forward P/E'],
                                 stats_map['PEG Ratio (5 yr expected)'],
                                 stats_map['Price/Sales'],
                                 stats_map['Price/Book'],
                                 stats_map['Enterprise Value/Revenue'],
                                 stats_map['Enterprise Value/EBITDA'])


    def get_profitability(self, stats_map):
        return Profitability(stats_map['Profit Margin'],
                             stats_map['Operating Margin'])


    def get_mgmt_effectiveness(self, stats_map):
        return MgmtEffectiveness(stats_map['Return on Assets'],
                                 stats_map['Return on Equity'])


    def get_income_stmt(self, stats_map):
        return IncomeStatement(stats_map['Revenue'],
                               stats_map['Revenue Per Share'],
                               stats_map['Quarterly Revenue Growth'],
                               stats_map['Gross Profit'],
                               stats_map['EBITDA'],
                               stats_map['Net Income Avi to Common'],
                               stats_map['Diluted EPS'],
                               stats_map['Quarterly Earnings Growth'])


    def get_balance_sheet(self, stats_map):
        return BalanceSheet(stats_map['Total Cash'],
                            stats_map['Total Cash Per Share'],
                            stats_map['Total Debt'],
                            stats_map['Total Debt/Equity'],
                            stats_map['Current Ratio'],
                            stats_map['Book Value Per Share'])


    def get_cash_flow_stmt(self, stats_map):
        return CashFlowStmt(stats_map['Operating Cash Flow'],
                            stats_map['Levered Free Cash Flow'])


    def get_stock_price_history(self, stats_map):
        return StockPriceHistory(stats_map['52-Week Change'],
                                 stats_map['52 Week High'],
                                 stats_map['52 Week Low'],
                                 stats_map['50-Day Moving Average'],
                                 stats_map['200-Day Moving Average'])


    def get_share_stats(self, stats_map):
        return ShareStats(stats_map['Avg Vol (3 month)'],
                          stats_map['Avg Vol (10 day)'],
                          stats_map['Shares Outstanding'],
                          stats_map['Float'],
                          stats_map['Shares Short'],
                          stats_map['Short Ratio'],
                          stats_map['Short % of Float'],
                          stats_map['Shares Short (prior month)'])


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
        return Split(stats_map['Last Split Factor (new per old)'],
                     stats_map['Last Split Date'])


    def get_major_holders(self, stats_map):
        return MajorHolders(stats_map['% Held by Insiders'],
                            stats_map['% Held by Institutions'])