from util import parse_float


class MajorHolders:

    def __init__(self, pc_held_by_insiders, pc_held_by_institutions):
        self.pc_insiders = parse_float(pc_held_by_insiders)
        self.pc_institutions = parse_float(pc_held_by_institutions)
