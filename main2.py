from web_processor import WebProcessor
from file_processor import FileProcessor
from yahoo_finance import Urls, WebParser
from config import config
from datetime import datetime
from repository import StockData
import pandas as pd
import logging


def _create_row(stock):
    # earnings_yield = 1 / stock['trailing_pe']

    # roc = net-income/(debt+equity)
    # ROC = ROE * (1 - DTC)

    # book formula
    earnings_yield = stock['ebitda'] / stock['ent_val']
    # roc = ebit / (net working capital + net fixed assets)

    return {
        'name': stock['name'],
        'earnings_yield': earnings_yield,
        'eps_ttm': stock['eps_ttm'],
        'trailing_pe': stock['trailing_pe'],

        'pc_return_on_equity_ttm': stock['pc_return_on_equity_ttm'],
        'pc_return_on_assets_ttm': stock['pc_return_on_assets_ttm'],

        'market_cap': stock['market_cap'],
        'ent_val': stock['ent_val'],

        'pc_profit_margin': stock['pc_profit_margin'],
        'pc_operating_margin_ttm': stock['pc_operating_margin_ttm'],

        'total_cash': stock['total_cash'],
        'total_debt': stock['total_debt'],

        'q_revenue_growth': stock['q_revenue_growth'],
        'q_earnings_growth': stock['q_earnings_growth']
    }


db_stock_data = StockData(config['postgresql']['host'],
                          config['postgresql']['database'])

list_stocks = db_stock_data.get_stock_data()

# list_return_on_equity = db_stock_data.get_stock_data_by_return_on_equity()

list_eps_ttm \
    = sorted([_create_row(row) for row in list_stocks], key=lambda row: row.get('earnings_yield'), reverse=True)

list_return_on_equity \
    = sorted([_create_row(row) for row in list_stocks], key=lambda row: row.get('pc_return_on_assets_ttm'),
             reverse=True)

# assign rank:
eps_rank = 1
for row in list_eps_ttm:
    row['rank'] = eps_rank
    # ranked_list_eps_ttm.append(row)
    eps_rank = eps_rank + 1

roe_rank = 1
for row in list_return_on_equity:
    row['rank'] = roe_rank
    roe_rank = roe_rank + 1

# print(list_eps_ttm)
# print(list_return_on_equity)

# combine rank
ranked_map = {}
#
for stock in list_eps_ttm:
    ranked_map[stock['name']] = {
        'name': stock['name'],
        'rank': stock['rank'],
        'eps_ttm': stock['eps_ttm'],
        'earnings_yield': stock['earnings_yield'],
        # 'pc_return_on_equity_ttm': stock['pc_return_on_equity_ttm'],
        # 'name': stock['name'],
        # 'eps_ttm': stock['eps_ttm'],
        'trailing_pe': stock['trailing_pe'],
        'pc_return_on_equity_ttm': stock['pc_return_on_equity_ttm'],
        'pc_return_on_assets_ttm': stock['pc_return_on_assets_ttm'],

        'market_cap': stock['market_cap'],
        'ent_val': stock['ent_val'],

        'pc_profit_margin': stock['pc_profit_margin'],
        'pc_operating_margin_ttm': stock['pc_operating_margin_ttm'],

        'total_cash': stock['total_cash'],
        'total_debt': stock['total_debt'],

        'q_revenue_growth': stock['q_revenue_growth'],
        'q_earnings_growth': stock['q_earnings_growth']
    }
#
#
for stock in list_return_on_equity:
    name = stock['name']
    roe_rank = stock['rank']

    # find in map
    stock_entry = ranked_map.get(name, None)
    if stock_entry:
        stock_entry['rank'] = stock['rank'] + roe_rank
    # update rank

# print(ranked_map)

final_list = [val for key, val in ranked_map.items()]

# print(final_list)

rank_sorted_list = sorted(final_list, key=lambda item: item['rank'])

# print(json.dumps(rank_sorted_list))
with open('data/output_0.csv', 'a') as out_file:
    out_file.write('name,'
                   'earnings_yield,'
                   'eps_ttm,'
                   'trailing_pe,'
                   'pc_return_on_equity_ttm,'
                   'pc_return_on_assets_ttm,'
                   'market_cap,'
                   'ent_val,'
                   'pc_profit_margin,'
                   'pc_operating_margin_ttm,'
                   'total_cash,'
                   'total_debt,'
                   'q_revenue_growth,'
                   'q_earnings_growth,' + '\n')

for e in rank_sorted_list:
    line = "{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11},{12},{13}". \
        format(e['name'],
               e['earnings_yield'],
               e['eps_ttm'],
               e['trailing_pe'],
               e['pc_return_on_equity_ttm'],
               e['pc_return_on_assets_ttm'],
               e['market_cap'],
               e['ent_val'],
               e['pc_profit_margin'],
               e['pc_operating_margin_ttm'],
               e['total_cash'],
               e['total_debt'],
               e['q_revenue_growth'],
               e['q_earnings_growth'])

    with open('data/output_0.csv', 'a') as out_file:
        out_file.write(line + '\n')

# import json
# print(json.dumps(ranked_map))

# generate new ranked
