class ShareStats:

    def __init__(self, avg_vol_3_day, avg_vol_10_day, shares_outstanding,
                 shares_float, shares_short, short_ratio, short_pc_of_float, shares_short_prior_month):
        self.avg_vol_3_day = avg_vol_3_day
        self.avg_vol_10_day = avg_vol_10_day
        self.shares_outstanding = shares_outstanding
        self.shares_float = shares_float
        self.shares_short = shares_short
        self.short_ratio = float(short_ratio)
        self.short_pc_of_float = short_pc_of_float
        self.shares_short_prior_month = shares_short_prior_month