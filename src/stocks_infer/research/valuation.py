"""Explicit five-year FCFF scenarios; assumptions are supplied by the researcher."""

from dataclasses import asdict

from stocks_infer.research.models import Scenario


def discounted_cash_flow(scenario: Scenario, *, revenue: float, net_debt: float, shares: float, price: float, discount_rate: float | None = None) -> dict:
    rate = scenario.discount_rate if discount_rate is None else discount_rate
    if revenue <= 0 or shares <= 0 or price <= 0 or rate <= scenario.terminal_growth:
        raise ValueError("invalid valuation base or discount rate")
    projection = []
    present_value = 0.0
    for year, (growth, margin) in enumerate(zip(scenario.revenue_growth, scenario.operating_margins), 1):
        next_revenue = revenue * (1 + growth)
        operating_income = next_revenue * margin
        # No automatic tax benefit for losses or cash release on shrinking sales.
        nopat = operating_income - max(operating_income, 0) * scenario.tax_rate
        reinvestment = max(next_revenue - revenue, 0) / scenario.sales_to_capital
        cash_flow = nopat - reinvestment
        present_value += cash_flow / (1 + rate) ** year
        projection.append({"year": year, "revenue": next_revenue, "operating_income": operating_income, "nopat": nopat, "reinvestment": reinvestment, "fcff": cash_flow})
        revenue = next_revenue
    terminal_nopat = projection[-1]["nopat"] * (1 + scenario.terminal_growth)
    if terminal_nopat <= 0:
        raise ValueError("terminal profitability must be positive for this framework")
    terminal_cash_flow = terminal_nopat * (1 - scenario.terminal_growth / scenario.terminal_roic)
    terminal_value = terminal_cash_flow / (rate - scenario.terminal_growth)
    discounted_terminal = terminal_value / (1 + rate) ** 5
    enterprise_value = present_value + discounted_terminal
    equity_value = enterprise_value - net_debt
    per_share = max(equity_value, 0) / shares
    return {
        "name": scenario.name, "assumptions": asdict(scenario), "projection": projection,
        "discount_rate_used": rate, "enterprise_value": enterprise_value,
        "equity_value": equity_value, "per_share": per_share,
        "upside": per_share / price - 1,
        "terminal_share_of_enterprise_value": discounted_terminal / enterprise_value if enterprise_value > 0 else None,
        "warnings": ["Constant outstanding shares; future dilution is not modeled.", "Net debt bridge omits preferred equity, minority interests, and other claims; review before relying on valuation.", "Maintenance reinvestment is assumed covered by depreciation; sales-to-capital models incremental investment."],
    }


def value_scenario(scenario: Scenario, **inputs) -> dict:
    result = discounted_cash_flow(scenario, **inputs)
    result["sensitivity"] = [
        {"discount_rate": rate, "per_share": discounted_cash_flow(scenario, discount_rate=rate, **inputs)["per_share"]}
        for rate in (scenario.discount_rate - .01, scenario.discount_rate, scenario.discount_rate + .01)
        if rate > scenario.terminal_growth
    ]
    return result
