from repository import DbWrite


class Company:

    def __init__(self, host, db_name):
        self.host = host
        self.db_name = db_name

    def add_company(self, company):
        sql = 'INSERT INTO company (stock, company_name, industry, exchange) ' \
              'VALUES (%(stock)s, %(company_name)s, %(industry)s, %(exchange)s)'

        with DbWrite(self.host, self.db_name) as cur:
            cur.execute(sql, {'stock': company.stock,
                              'company_name': company.name,
                              'industry': company.industry,
                              'exchange': company.exchange})

    def add_company_list(self, companies):
        pass

