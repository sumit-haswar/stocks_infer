import json
from util import json_converter


class Company:

    def __init__(self):
        self.id = None
        self.stock = None
        self.name = None
        self.industry = None
        self.exchange = None

    def to_json(self):
        return json.dumps(self, default=json_converter, sort_keys=False)
