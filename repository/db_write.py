import psycopg2


class DbWrite:
    def __init__(self, host, db_name):
        self.host = host
        self.db_name = db_name
        self.conn = psycopg2.connect(dbname=self.db_name, host=self.host)

    def __enter__(self):
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.conn.commit()
            self.cursor.close()
        except Exception as error:
            raise error
        finally:
            if self.conn is not None:
                self.conn.close()
        return False
