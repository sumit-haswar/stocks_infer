class IncomeStatement:

    def __init__(self, revenue_ttm, revenue_per_share_ttm, q_revenue_growth,
                 gross_profit_ttm, ebitda, net_income_avi_to_common_ttm,
                 diluted_eps_ttm, q_earnings_growth):
        self.revenue_ttm = revenue_ttm
        self.revenue_per_share_ttm = revenue_per_share_ttm
        self.q_revenue_growth = q_revenue_growth
        self.gross_profit_ttm = gross_profit_ttm
        self.ebitda = ebitda
        self.net_income_avi_to_common_ttm = net_income_avi_to_common_ttm
        self.diluted_eps_ttm = diluted_eps_ttm
        self.q_earnings_growth = q_earnings_growth