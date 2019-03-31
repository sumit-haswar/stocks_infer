from util import parse_float

class Summary:

    def __init__(self, prev_close, open, bid, ask, days_range, week_range_52,
                 volume, avg_volume, market_cap, beta, pe_ratio_ttm,eps_ttm,
                 earning_date, frwd_div_and_yield,ex_div_date, one_yr_target):
        self.previous_close = parse_float(prev_close)
        self.open = parse_float(open)
        self.bid = bid
        self.ask = ask
        self.days_range = days_range
        self.week_range_52 = week_range_52
        self.volume = parse_float(volume)
        self.avg_volume = parse_float(avg_volume)
        self.market_cap = market_cap
        self.beta = parse_float(beta)
        self.pe_ratio_ttm = parse_float(pe_ratio_ttm)
        self.eps_ttm = parse_float(eps_ttm)
        self.earning_date = earning_date
        self.frwd_div_and_yield = frwd_div_and_yield
        self.ex_div_date = ex_div_date
        self.one_yr_target = parse_float(one_yr_target)