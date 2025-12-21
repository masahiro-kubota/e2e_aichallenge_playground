"""Node related data structures."""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class NodeExecutionResult(Enum):
    """Result of node execution."""

    SUCCESS = "success"  # 正常実行完了
    SKIPPED = "skipped"  # 入力データ不足等でスキップ
    FAILED = "failed"  # エラー発生


class ComponentConfig(BaseModel):
    """Base configuration for components (nodes) with strict validation.

    All component configuration classes should inherit from this to automatically
    enforce strict validation (extra fields are forbidden).
    Previously known as StrictConfig/NodeConfig.
    """

    model_config = ConfigDict(extra="forbid")
