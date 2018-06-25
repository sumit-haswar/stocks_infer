from web_processor import *
from file_processor import *
from yahoo_finance import *
from datetime import *
from stock_data import *

web_processor = WebProcessor()
file_processor = FileProcessor("")
parser = WebParser()

# get stock symbols from data file

pharma_stocks = ['ABT'] #file_processor.read_file("data/pharma_stocks")

data = []
currDt = datetime.now()

for stock in pharma_stocks:
    stock_data = StockInfo()

    #summary
    summary = web_processor.get_body(Urls.summary.format(stock))
    summary_div = web_processor.get_element_by_id(summary, "quote-summary")
    stock_data.Summary = parser.get_summary(summary_div.xpath('//tr'))

    #statistics
    # stats_content = web_processor.get_body(Urls.key_statistics.format(stock))
    # stats_div = web_processor.get_element_by_data_reactid(stats_content, '11')
    # stats_map = parser.get_map_from_tr_list(stats_div.xpath('//tr'))
    #
    # stock_data.ValuationMeasures = parser.get_valuation_measures(stats_map)
    # stock_data.Profitability = parser.get_profitability(stats_map)

    file_name = currDt.strftime("%b-%d-%Y_%H:%M") + "_" + stock
    file_processor.save_file(file_name, stock_data.to_json())


#page_content = web_processor.get_element_by_id("https://finance.yahoo.com/quote/ABT/", "quote-summary")
#page_content = web_processor.get_element_by_id("https://finance.yahoo.com/quote/ABT/", "quote-summary")

#page_content = web_processor.get_body("https://finance.yahoo.com/quote/ABT/")
#summary_div = web_processor.get_element_by_id(page_content[0], "quote-summary")

# stats_content = web_processor.get_body("https://finance.yahoo.com/quote/ABT/key-statistics")
# val_measures_div = web_processor.get_element_by_data_reactid(stats_content, '11')
#
# list = []
# # for elem in page_content.xpath('//tr'):
# #     #foreach tr get first and second td:
# #     list.append(html.tostring(elem, pretty_print=True))
# tr_list = val_measures_div.xpath('//tr')
# #summary = parser.get_summary_from_tr_list(tr_list)
# #print(json.dumps(summary.__dict__))
#
# for tr in tr_list:
#     #foreach tr get first and second td:
#     list.append({ "key": next(tr.getiterator('span')).text_content(),
#                   "value": tr.getchildren()[1].text_content()
#                   })
#
# print(list)

