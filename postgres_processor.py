import psycopg2
from datetime import datetime

class PostgresProcessor:


    def __init__(self, host, db_name):
        self.db_name = db_name
        self.host = host


    def insert_stock_data(self, symbol, name, json_data):

        sql = "INSERT INTO stock_data (date_added_utc, symbol, name, data) " \
              "VALUES (%(date_added_utc)s, %(symbol)s, %(name)s, %(data)s)"
        conn = None
        try:
            conn = psycopg2.connect(dbname=self.db_name, host=self.host)
            cur = conn.cursor()
            cur.execute(sql, {'date_added_utc': datetime.utcnow(),
                              'symbol': symbol,
                              'name': name,
                              'data': json_data})
            conn.commit()
            cur.close()
        except Exception as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()


    def insert_stock_data_list(self, stock_data_list):

        sql = "INSERT INTO stock_data (date_added_utc, symbol, name, data) " \
              "VALUES (%(date_added_utc)s, %(symbol)s, %(name)s, %(data)s)"

        conn = None

        try:
            conn = psycopg2.connect(dbname=self.db_name, host=self.host)
            cur = conn.cursor()
            cur.executemany(sql, stock_data_list)
            conn.commit()
            cur.close()
        except Exception as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()
