import psycopg2
import psycopg2.extras

class Db:
    def __init__(self, host, db_name):
        self.host = host
        self.db_name = db_name
        self.conn = psycopg2.connect(dbname=self.db_name, host=self.host)

    def __enter__(self):
        cursor = self.conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        return cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is not None:
            self.conn.close()
        return True
