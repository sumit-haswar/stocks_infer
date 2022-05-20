from repository import Db, DbWrite


# noinspection SqlNoDataSourceInspection
class StockData:

    insert_sql = 'INSERT INTO stock_data (name, ' \
                  'week_range_52, ' \
                  'eps_ttm, ' \
                  'pc_return_on_equity_ttm, ' \
                  'pc_return_on_assets_ttm, ' \
                  'pc_change_52_week, ' \
                  'market_cap, ' \
                  'ent_val, ' \
                  'trailing_pe, ' \
                  'forward_pe, ' \
                  'pc_profit_margin, ' \
                  'pc_operating_margin_ttm, ' \
                  'revenue_ttm, ' \
                  'revenue_per_share_ttm, ' \
                  'q_revenue_growth, ' \
                  'gross_profit_ttm, ' \
                  'total_cash, ' \
                  'total_cash_per_share, ' \
                  'total_debt, ' \
                  'total_debt_per_equity, ' \
                  'operating_cash_flow_ttm, ' \
                  'levered_cash_flow_ttm, ebitda, pe_ratio_ttm, q_earnings_growth, shares_outstanding, book_val_per_share ) ' \
                  'VALUES (%(name)s, %(week_range_52)s, %(eps_ttm)s, %(pc_return_on_equity_ttm)s, ' \
                  '%(pc_return_on_assets_ttm)s, %(pc_change_52_week)s, %(market_cap)s, %(ent_val)s, %(trailing_pe)s, ' \
                  '%(forward_pe)s, ' \
                  '%(pc_profit_margin)s, %(pc_operating_margin_ttm)s, %(revenue_ttm)s, %(revenue_per_share_ttm)s, ' \
                  '%(q_revenue_growth)s, %(gross_profit_ttm)s, ' \
                  '%(total_cash)s, %(total_cash_per_share)s, %(total_debt)s, %(total_debt_per_equity)s, ' \
                  '%(operating_cash_flow_ttm)s, %(levered_cash_flow_ttm)s, %(ebitda)s, %(pe_ratio_ttm)s, ' \
                  '%(q_earnings_growth)s, %(shares_outstanding)s, %(book_val_per_share)s)'

    def __init__(self, host, db_name):
        self.db_name = db_name
        self.host = host

    def get_stock_data(self):
        sql = "SELECT DISTINCT ON (name) * " \
              "FROM stock_data " \
              "WHERE pc_return_on_assets_ttm IS NOT NULL AND ent_val > 0 AND ebitda > 0"

        with Db(self.host, self.db_name) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [row for row in rows]

    def get_stock_data_by_eps_ttm(self):
        sql = "SELECT DISTINCT ON (name) * " \
              "FROM stock_data " \
              "WHERE eps_ttm IS NOT NULL"

        with Db(self.host, self.db_name) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [row for row in rows]

    def get_stock_data_by_return_on_equity(self):
        sql = "SELECT DISTINCT ON (name) * " \
              "FROM stock_data " \
              "WHERE pc_return_on_equity_ttm IS NOT NULL "

        with Db(self.host, self.db_name) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [row for row in rows]

    def insert_stock_data(self, stock_info) :
        with DbWrite(self.host, self.db_name) as cur:
            cur.execute(self.insert_sql, {'name': stock_info.name,
                                          'week_range_52': stock_info.summary.week_range_52,
                                          'pc_return_on_equity_ttm': stock_info.management_effectiveness.pc_return_on_equity_ttm,
                                          'pc_return_on_assets_ttm': stock_info.management_effectiveness.pc_return_on_assets_ttm,
                                          'pc_change_52_week': stock_info.stock_price_history.pc_change_52_week,
                                          'market_cap': stock_info.valuation_measures.market_cap,
                                          'ent_val': stock_info.valuation_measures.ent_val,
                                          'trailing_pe': stock_info.valuation_measures.trailing_pe,
                                          'forward_pe': stock_info.valuation_measures.forward_pe,
                                          'pc_profit_margin': stock_info.profitability.pc_profit_margin,
                                          'pc_operating_margin_ttm': stock_info.profitability.pc_operating_margin_ttm,
                                          'revenue_ttm': stock_info.income_statement.revenue_ttm,
                                          'revenue_per_share_ttm': stock_info.income_statement.revenue_per_share_ttm,
                                          'q_revenue_growth': stock_info.income_statement.q_revenue_growth,
                                          'gross_profit_ttm': stock_info.income_statement.gross_profit_ttm,
                                          'total_cash': stock_info.balance_sheet.total_cash,
                                          'total_cash_per_share': stock_info.balance_sheet.total_cash_per_share,
                                          'total_debt': stock_info.balance_sheet.total_debt,
                                          'total_debt_per_equity': stock_info.balance_sheet.total_debt_per_equity,
                                          'operating_cash_flow_ttm': stock_info.cash_flow_statement.operating_cash_flow_ttm,
                                          'levered_cash_flow_ttm': stock_info.cash_flow_statement.levered_cash_flow_ttm,
                                          'ebitda': stock_info.income_statement.ebitda,
                                          'pe_ratio_ttm': stock_info.summary.pe_ratio_ttm,
                                          'q_earnings_growth': stock_info.income_statement.q_earnings_growth,
                                          'shares_outstanding': stock_info.share_statistics.shares_outstanding,
                                          'book_val_per_share': stock_info.balance_sheet.book_val_per_share,
                                          'eps_ttm': stock_info.income_statement.diluted_eps_ttm
                                          })

    def insert_stock_data_list(self, stock_data_list):
        with DbWrite(self.host, self.db_name) as cur:
            cur.executemany(self.insert_sql, stock_data_list)
