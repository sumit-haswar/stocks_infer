from web_processor import *
from file_processor import *
from yahoo_finance import *
from stock_data import *
from postgres_processor import *
from config import *

web_processor = WebProcessor()
file_processor = FileProcessor("")
parser = WebParser()
postgres = PostgresProcessor(config['postgresql']['host'],
                             config['postgresql']['database'])

# get stock symbols from data file
pharma_stocks = file_processor.read_file("lookup_data/pharma_stocks")
stock_data_list = []
dt_utc_now = datetime.utcnow()

for stock in pharma_stocks:
    stock_data = StockInfo()

    #get summary data
    summary = web_processor.get_body(Urls.summary.format(stock))
    summary_div = web_processor.get_element_by_id(summary, "quote-summary")

    #get statistics data
    stats_content = web_processor.get_body(Urls.key_statistics.format(stock))
    stats_map = parser.get_map_from_tr_list(
        web_processor.get_element_by_data_reactid(stats_content, '11').xpath('//tr'))

    stock_data.Summary = parser.get_summary(summary_div.xpath('//tr'))
    stock_data.ValuationMeasures = parser.get_valuation_measures(stats_map)
    stock_data.Profitability = parser.get_profitability(stats_map)
    stock_data.ManagementEffectiveness = parser.get_mgmt_effectiveness(stats_map)
    stock_data.IncomeStatement = parser.get_income_stmt(stats_map)
    stock_data.BalanceSheet = parser.get_balance_sheet(stats_map)
    stock_data.CashFlowStatement = parser.get_cash_flow_stmt(stats_map)
    stock_data.Dividends = parser.get_dividends(stats_map)
    stock_data.MajorHolders = parser.get_major_holders(stats_map)
    stock_data.ShareStatistics = parser.get_share_stats(stats_map)
    stock_data.Splits = parser.get_split(stats_map)
    stock_data.StockPriceHistory = parser.get_stock_price_history(stats_map)

    stock_data_list.append({'date_added_utc': dt_utc_now,
                            'symbol': stock,
                            'name': '',
                            'data': stock_data.to_json()})


postgres.insert_stock_data_list(stock_data_list)
