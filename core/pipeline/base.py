from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from core.pipeline.models import WorkflowContext


class PipelineStep(ABC):
    """Contrato base para os passos do pipeline."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, context: WorkflowContext) -> None:
        """Executa o passo, podendo atualizar o contexto."""


class Pipeline:
    """Executa uma sequência ordenada de passos."""

    def __init__(self, steps: Iterable[PipelineStep]):
        self.steps: List[PipelineStep] = list(steps)

    def run(self, context: WorkflowContext) -> WorkflowContext:
        for step in self.steps:
            step.run(context)
        return context

