from web_processor import WebProcessor
from file_processor import FileProcessor
from yahoo_finance import Urls, WebParser
from model import StockInfo
from config import config
from datetime import datetime
from repository import StockData
import pandas as pd
import logging
from typing import List

web_processor = WebProcessor()
parser = WebParser()

from lxml.etree import tostring

def get_stock_info(stock, dt_utc_now):
    stock_data = StockInfo()
    try:
        # get summary data
        summary = web_processor.get_body(Urls.summary.format(stock))
        summary_div = web_processor.get_element_by_id(summary, "quote-summary")

        # get statistics data
        stats_content = web_processor.get_body(Urls.key_statistics.format(stock))
        # stats_map = parser.get_map_from_tr_list(
        #     web_processor.get_element_by_data_reactid(stats_content, '11').xpath('//tr'))

        inner_html = tostring(stats_content)
        print(inner_html)

        stats_map = parser.get_map_from_tr_list(
            web_processor.get_element_by_data_reactid(stats_content, '48').xpath('//tr'))

        valuation_measures = parser.get_map_from_tr_list(
            web_processor.get_element_by_data_reactid(stats_content, '48').xpath('//tr'))

        stock_data.name = stock
        stock_data.date_added_utc = str(dt_utc_now.date())

        # print('stats_map:')
        # print(stats_map)

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

        return stock_data

    except Exception as ex:
        # print(ex)
        # todo log exception
        return None


def get_file_data(file_paths: List[str]) -> List:
    stock_symbol_list = []

    for file_path in file_paths:
        data_frame = pd.read_csv(file_path, delimiter=',')
        stock_symbol_list += data_frame['stock'].tolist()

    return stock_symbol_list


def _get_stock_list():
    return ['TRMB', 'TFC', 'TWTR', 'TYL', 'TSN', 'UDR', 'ULTA', 'UAA', 'UA', 'UNP', 'UAL', 'UPS', 'URI', 'UNH', 'UHS',
            'UNM', 'USB', 'VLO', 'VTR', 'VRSN', 'VRSK', 'VZ', 'VRTX', 'VFC', 'VIAC', 'VTRS', 'V', 'VNO', 'VMC', 'WRB',
            'WAB', 'WBA', 'WMT', 'WM', 'WAT', 'WEC', 'WFC', 'WELL', 'WST', 'WDC', 'WU', 'WRK', 'WY', 'WHR', 'WMB',
            'WLTW', 'GWW', 'WYNN', 'XEL', 'XLNX', 'XYL', 'YUM', 'ZBRA', 'ZBH', 'ZION', 'ZTS', 'PEAK', 'HWM', 'J',
            'LUMN', 'MCK', 'NLOK', 'NVR', 'OGN', 'OTIS', 'RTX', 'TT']


def main():
    """

    :return:
    """
    db_stock_data = StockData(config['postgresql']['host'],
                              config['postgresql']['database'])

    # get stock symbols from data file
    # pharma_stocks = file_processor.read_file("lookup_data/pharma_stocks")
    stock_data_list = []
    dt_utc_now = datetime.utcnow()

    # stocks = get_file_data(['../lookup_data/s_p_500.csv'])

    stocks = _get_stock_list()

    invalid_data = []

    # stocks = stocks[100:]

    print('getting data from yahoo . . .')
    for stock in stocks[:10]:
        stock_data = get_stock_info(stock, dt_utc_now)
        if stock_data:
            stock_data_list.append(stock_data)
        else:
            invalid_data.append(stock)

    # file_processor.save_file('data/fortune_500_0.json',str(stock_data_list))

    print('adding to database . . .')
    for stock_data in stock_data_list:
        try:
            db_stock_data.insert_stock_data(stock_data)
        except Exception as ex:
            print(ex)
            # todo log exception
            invalid_data.append(stock_data.name)
            continue

    print('invalid_data:')
    print(invalid_data)

    # ['AET', 'APC', 'ANDV', 'BHGE', 'BBT', 'BF.B', 'CA', 'CSRA', 'DWDP', 'DPS', 'EVHC',
    # 'ESRX', 'GGP', 'HCP', 'LLL', 'LUK', 'KORS', 'MON', 'NFX', 'PX', 'RHT', 'COL',
    # 'SCG', 'SYMC', 'TWX', 'TMK', 'TSS', 'WYN', 'XL']

    # ['AET', 'APC', 'ANDV', 'BHGE', 'BBT', 'BF.B', 'CA', 'CSRA', 'DWDP', 'DPS', 'EVHC',
    # 'ESRX', 'GGP', 'HRS', 'HCP', 'LLL', 'KORS', 'MON', 'NFX', 'PX', 'RHT', 'COL', 'SCG',
    # 'TWX', 'TMK', 'TSS', 'WYN', 'XL', 'BRK.B', 'GD', 'JEC', 'LUK', 'MCK', 'CRM',
    # 'STI', 'SYMC', 'VIAB', 'MCK', 'CRM']

    print('total invalid_data: {0}'.format(len(invalid_data)))
    print('total records added: {0}'.format(len(stock_data_list)))
    # 540


if __name__ == "__main__":
    main()
