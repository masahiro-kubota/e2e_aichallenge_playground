from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProcessorProtocol(Protocol):
    """汎用的な処理インターフェース（構造的型付け）."""

    def process(self, **kwargs: Any) -> Any:
        """入力を受け取って出力を返す."""
        ...
