-- Table Definition ----------------------------------------------

create table public.company
(
	id bigserial not null
		constraint company_pk
			primary key,
	stock varchar(10) not null,
	company_name varchar(100),
	industry varchar(30),
	exchange varchar(20)
);

create table public.stock_data
(
	id bigserial not null
		constraint stock_data_pk
			primary key,
	name varchar not null,
	week_range_52 varchar,
	eps_ttm double precision,
	pc_return_on_equity_ttm double precision,
	pc_return_on_assets_ttm double precision,
	pc_change_52_week real,
	inserted_on date default CURRENT_DATE not null,
	market_cap bigint,
	ent_val bigint,
	trailing_pe real,
	forward_pe real,
	pc_profit_margin real,
	pc_operating_margin_ttm real,
	revenue_ttm bigint,
	revenue_per_share_ttm real,
	q_revenue_growth real,
	gross_profit_ttm bigint,
	total_cash bigint,
	total_cash_per_share real,
	total_debt bigint,
	total_debt_per_equity real,
	operating_cash_flow_ttm bigint,
	levered_cash_flow_ttm bigint,
	ebitda bigint,
	pe_ratio_ttm real,
	q_earnings_growth real,
	shares_outstanding bigint,
	book_val_per_share real
);

-- Indices -------------------------------------------------------
create unique index company_id_uindex
	on public.company (id);

CREATE UNIQUE INDEX stock_data_pkey ON stock_data(id int4_ops);
CREATE INDEX symbol_idx ON stock_data(symbol text_ops);