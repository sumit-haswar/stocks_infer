from web_processor import WebProcessor
from file_processor import FileProcessor
from yahoo_finance import Urls, WebParser
from stock_data import StockInfo
from config import config
from datetime import datetime
from repository import StockData
import pandas as pd
import logging


web_processor = WebProcessor()
file_processor = FileProcessor("")
parser = WebParser()


db_stock_data = StockData(config['postgresql']['host'],
                          config['postgresql']['database'])

# get stock symbols from data file
# pharma_stocks = file_processor.read_file("lookup_data/pharma_stocks")

fortune_500_0_stocks = file_processor.read_file("lookup_data/fortune_500_0")

s_p_500_data = pd.read_csv("lookup_data/s_p_500.csv", delimiter=',')
s_p_500_data_stocks = s_p_500_data['stock'].tolist()

stock_data_list = []
dt_utc_now = datetime.utcnow()

stocks = s_p_500_data_stocks + fortune_500_0_stocks

invalid_data = []

print('getting data from yahoo . . .')
for stock in stocks:

    stock_data = StockInfo()

    try:
        # get summary data
        summary = web_processor.get_body(Urls.summary.format(stock))
        summary_div = web_processor.get_element_by_id(summary, "quote-summary")

        # get statistics data
        stats_content = web_processor.get_body(Urls.key_statistics.format(stock))
        stats_map = parser.get_map_from_tr_list(
            web_processor.get_element_by_data_reactid(stats_content, '11').xpath('//tr'))

        stock_data.name = stock
        stock_data.date_added_utc = str(dt_utc_now.date())

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

    except Exception as error:
        invalid_data.append(stock)
        continue

    stock_data_list.append(stock_data)


# file_processor.save_file('data/fortune_500_0.json',str(stock_data_list))
# print('adding to database . . .')
# for stock_data in stock_data_list:
#     try:
#         db_stock_data.insert_stock_data(stock_data)
#     except Exception as error:
#         invalid_data.append(stock_data.name)
#         continue

print('invalid_data:')
print(invalid_data)
# ['AET', 'APC', 'ANDV', 'BHGE', 'BBT', 'BF.B', 'CA', 'CSRA', 'DWDP', 'DPS', 'EVHC',
# 'ESRX', 'GGP', 'HCP', 'LLL', 'LUK', 'KORS', 'MON', 'NFX', 'PX', 'RHT', 'COL',
# 'SCG', 'SYMC', 'TWX', 'TMK', 'TSS', 'WYN', 'XL']

# ['AET', 'APC', 'ANDV', 'BHGE', 'BBT', 'BF.B', 'CA', 'CSRA', 'DWDP', 'DPS', 'EVHC',
# 'ESRX', 'GGP', 'HRS', 'HCP', 'LLL', 'KORS', 'MON', 'NFX', 'PX', 'RHT', 'COL', 'SCG',
# 'TWX', 'TMK', 'TSS', 'WYN', 'XL', 'BRK.B', 'GD', 'JEC', 'LUK', 'MCK', 'CRM',
# 'STI', 'SYMC', 'VIAB', 'MCK', 'CRM']

print('total records added: {0}'.format(len(stock_data_list)))
# 540