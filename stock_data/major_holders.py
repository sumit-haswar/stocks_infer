import util

class MajorHolders:

    def __init__(self, pc_held_by_insiders, pc_held_by_institutions):
        self.pc_insiders = util.get_float_from_string(pc_held_by_insiders)
        self.pc_institutions = util.get_float_from_string(pc_held_by_institutions)
        # self.pc_float_institutions = pc_float_held_by_institutions
        # self.number_of_institutions_holding = number_of_institutions_holding
