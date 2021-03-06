from util import parse_float


class StockPriceHistory:

    def __init__(self, pc_change_52_week, high_52_week,
                 low_52_week, moving_avg_50_days, moving_avg_200_days):
        self.pc_change_52_week = pc_change_52_week
        self.high_52_week = parse_float(high_52_week)
        self.low_52_week = parse_float(low_52_week)
        self.moving_avg_50_days = parse_float(moving_avg_50_days)
        self.moving_avg_200_days = parse_float(moving_avg_200_days)
