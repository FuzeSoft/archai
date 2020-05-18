from typing import Type

from overrides import overrides

from archai.nas.exp_runner import ExperimentRunner
from archai.nas.arch_trainer import TArchTrainer
from .gs_cell_builder import GsCellBuilder
from .gs_arch_trainer import GsArchTrainer

class GsExperimentRunner(ExperimentRunner):
    @overrides
    def cell_builder(self)->GsCellBuilder:
        return GsCellBuilder()

    @overrides
    def trainer_class(self)->TArchTrainer:
        return GsArchTrainer