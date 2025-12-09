from dataclasses import dataclass


@dataclass
class NodeIO:
    """Node I/O definition."""

    inputs: dict[str, type | str]
    outputs: dict[str, type | str]

    def __init__(
        self,
        inputs: list[str] | dict[str, type | str],
        outputs: str | list[str] | dict[str, type | str] | None = None,
        output: str | None = None,
    ):
        """Initialize NodeIO.

        Args:
            inputs: List of input field names or dict mapping field name to type.
            outputs: Output field name(s) or dict mapping field name to type.
            output: Legacy alias for outputs (single output).
        """
        if output is not None:
            outputs = output

        if outputs is None:
            outputs = {}
        if isinstance(inputs, list):
            self.inputs = {k: "Any" for k in inputs}
        else:
            self.inputs = inputs

        if isinstance(outputs, str):
            self.outputs = {outputs: "Any"}
        elif isinstance(outputs, list):
            self.outputs = {k: "Any" for k in outputs}
        else:
            self.outputs = outputs
