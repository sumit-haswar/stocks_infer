from util import parse_float


class ValuationMeasures:

    def __init__(self, market_cap, ent_val, trailing_pe, forward_pe,
                 peg_ratio,price_per_sales_ttm, price_per_book_mrq,
                 ent_val_per_revenue, ent_val_per_ebitda):
        self.market_cap = market_cap
        self.ent_val = ent_val
        self.trailing_pe = parse_float(trailing_pe)
        self.forward_pe = parse_float(forward_pe)
        self.peg_ratio = parse_float(peg_ratio)
        self.price_per_sales_ttm = parse_float(price_per_sales_ttm)
        self.price_per_book_mrq = parse_float(price_per_book_mrq)
        self.ent_val_per_revenue = parse_float(ent_val_per_revenue)
        self.ent_val_per_ebitda = parse_float(ent_val_per_ebitda)



