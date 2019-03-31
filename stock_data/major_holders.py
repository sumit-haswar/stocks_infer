from util import parse_float

class MajorHolders:

    def __init__(self, pc_held_by_insiders, pc_held_by_institutions):
        self.pc_insiders = parse_float(pc_held_by_insiders)
        self.pc_institutions = parse_float(pc_held_by_institutions)
        # self.pc_float_institutions = pc_float_held_by_institutions
        # self.number_of_institutions_holding = number_of_institutions_holding
