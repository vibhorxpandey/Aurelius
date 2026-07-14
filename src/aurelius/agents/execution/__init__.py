"""Research-execution agents (Stages 2-3).

ExperimentDesigner and CodeGenerator author the protocol + code; SandboxExecutor runs it in a
hardened Docker container (opt-in); ResultAggregator condenses the output."""
from .experiment_designer_agent import ExperimentDesignerAgent
from .code_generator_agent import CodeGeneratorAgent
from .sandbox_executor_agent import SandboxExecutorAgent
from .result_aggregator_agent import ResultAggregatorAgent

__all__ = [
    "ExperimentDesignerAgent",
    "CodeGeneratorAgent",
    "SandboxExecutorAgent",
    "ResultAggregatorAgent",
]
