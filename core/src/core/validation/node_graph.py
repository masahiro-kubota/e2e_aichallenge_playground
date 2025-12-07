"""Node graph validation and visualization."""

from core.nodes.generic_node import GenericProcessingNode


def validate_node_graph(nodes: list[GenericProcessingNode]) -> None:
    """Validate that the node graph is consistent and acyclic.

    Args:
        nodes: List of nodes to validate

    Raises:
        ValueError: If graph is invalid

    Examples:
        >>> nodes = [
        ...     GenericProcessingNode(..., io_spec=NodeIO(inputs=[], output="a")),
        ...     GenericProcessingNode(..., io_spec=NodeIO(inputs=["a"], output="b"))
        ... ]
        >>> validate_node_graph(nodes)  # OK
    """
    # 利用可能な出力(初期値として"action"と"sim_state"を含む - 循環のため)
    available_outputs = {"action", "sim_state"}

    for node in nodes:
        # 必要な入力が利用可能かチェック
        for input_field in node.io_spec.inputs:
            if input_field not in available_outputs:
                raise ValueError(
                    f"Node '{node.name}' requires '{input_field}' "
                    f"but no previous node produces it. "
                    f"Available outputs: {available_outputs}"
                )

        # このノードの出力を追加
        available_outputs.add(node.io_spec.output)

    # actionが最終的に生成されるかチェック
    if "action" not in available_outputs:
        raise ValueError("No node produces 'action' required for simulation")


def visualize_node_graph(nodes: list[GenericProcessingNode]) -> str:
    """Visualize node graph in Mermaid format.

    Args:
        nodes: List of nodes

    Returns:
        str: Mermaid graph definition
    """
    lines = ["graph LR"]

    for node in nodes:
        # ノード定義 (名前と周波数を表示)
        lines.append(f'    {node.name}["{node.name}<br/>{node.rate_hz}Hz"]')

        # 入力エッジ
        for input_field in node.io_spec.inputs:
            lines.append(f"    {input_field} --> {node.name}")

        # 出力エッジ
        lines.append(f"    {node.name} --> {node.io_spec.output}")

    return "\n".join(lines)
