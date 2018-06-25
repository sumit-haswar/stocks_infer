class Dividends:

    def __init__(self, frwd_annual_rate, frwd_annual_yield,
                 trail_annual_rate, trail_annual_div_yield, five_yr_avg_yield,
                 payout_ratio, date, ex_date):
        self.frwd_annual_rate = frwd_annual_rate
        self.frwd_annual_yield = frwd_annual_yield
        self.trail_annual_rate = trail_annual_rate
        self.trail_annual_div_yield = trail_annual_div_yield
        self.five_yr_avg_yield = five_yr_avg_yield
        self.payout_ratio = payout_ratio
        self.date = date
        self.ex_date = ex_date