-- Table Definition ----------------------------------------------

CREATE TABLE stock_data (
    id SERIAL PRIMARY KEY,
    date_added_utc timestamp without time zone NOT NULL,
    symbol character varying(10) NOT NULL,
    name text,
    data jsonb
);

-- Indices -------------------------------------------------------

CREATE UNIQUE INDEX stock_data_pkey ON stock_data(id int4_ops);
CREATE INDEX symbol_idx ON stock_data(symbol text_ops);