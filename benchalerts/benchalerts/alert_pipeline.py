"""Every project implementing ``benchalerts`` may want different input and output
channels for their alerts. This module implements a relatively simple framework for
composing alert pipelines out of common steps.
"""

import abc
from traceback import format_exc
from typing import Any, Dict, List, Optional


class AlertPipelineStep(abc.ABC):
    """One step of a benchalerts pipeline.

    Parameters
    ----------
    step_name
        The name for this step. If not given, will default to this class's name.
    """

    def __init__(self, step_name: Optional[str]) -> None:
        self.step_name = step_name or self.__class__.__name__

    @abc.abstractmethod
    def run_step(self, previous_outputs: Dict[str, Any]) -> Any:
        """Run this step.

        Parameters
        ----------
        previous_outputs
            A dict of previous steps' outputs in the pipeline, keyed by step name.

        Returns
        -------
        Any
            Anything (sent to subsequent steps via the ``previous_outputs`` dict).
        """


class AlertPipelineErrorHandler(abc.ABC):
    """A class to handle errors during the running of a benchalerts pipeline."""

    @abc.abstractmethod
    def handle_error(self, exc: BaseException, traceback: str) -> None:
        """Handle an error that may have happened during a pipeline run.

        Parameters
        ----------
        exc
            The exception that was raised.
        traceback
            A string of the traceback.
        """


class AlertPipeline:
    """A structure for running a sequence of configurable ``AlertPipelineStep``
    instances.

    Parameters
    ----------
    steps
        A list of ``AlertPipelineStep`` instances.
    error_handlers
        An optional list of ``AlertPipelineErrorHandler`` instances to handle any errors
        that may arise before raising them.
    """

    def __init__(
        self,
        steps: List[AlertPipelineStep],
        error_handlers: Optional[List[AlertPipelineErrorHandler]] = None,
    ) -> None:
        self.steps = steps
        self.error_handlers = error_handlers or []

    def run_pipeline(self) -> Dict[str, Any]:
        """Run the pipeline.

        Returns
        -------
        Dict[str, Any]
            All steps' outputs, keyed by step name.
        """
        step_outputs: Dict[str, Any] = {}

        try:
            for step in self.steps:
                step_outputs[step.step_name] = step.run_step(
                    previous_outputs=step_outputs
                )

        except Exception as exc:
            for error_handler in self.error_handlers:
                error_handler.handle_error(exc=exc, traceback=format_exc())
            raise

        return step_outputs
