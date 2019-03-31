from web_processor import WebProcessor
from file_processor import FileProcessor
from yahoo_finance import *
from stock_data import *
from postgres_processor import PostgresProcessor
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

    stock_data.summary = parser.get_summary(summary_div.xpath('//tr'))
    stock_data.valuation_measures = parser.get_valuation_measures(stats_map)
    stock_data.profitability = parser.get_profitability(stats_map)
    stock_data.management_effectiveness = parser.get_mgmt_effectiveness(stats_map)
    stock_data.income_statement = parser.get_income_stmt(stats_map)
    stock_data.balance_sheet = parser.get_balance_sheet(stats_map)
    stock_data.cash_flow_statement = parser.get_cash_flow_stmt(stats_map)
    stock_data.dividends = parser.get_dividends(stats_map)
    stock_data.major_holders = parser.get_major_holders(stats_map)
    stock_data.share_statistics = parser.get_share_stats(stats_map)
    stock_data.splits = parser.get_split(stats_map)
    stock_data.stock_price_history = parser.get_stock_price_history(stats_map)

    stock_data_list.append({'date_added_utc': dt_utc_now,
                            'symbol': stock,
                            'name': '',
                            'data': stock_data.to_json()})


postgres.insert_stock_data_list(stock_data_list)
