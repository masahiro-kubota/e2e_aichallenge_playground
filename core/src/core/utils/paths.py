"""Path utilities."""

from pathlib import Path


def get_project_root(path: Path | str | None = None) -> Path:
    """Find the project root directory.

    Searches up from the given path (or current file) for a marker file
    like pyproject.toml or .git.

    Args:
        path: Starting path. If None, uses the current file's location.

    Returns:
        Path to the project root.
    """
    if path is None:
        # Start from the current file if available, otherwise current working directory
        try:
            current_path = Path(__file__).resolve()
        except NameError:
            current_path = Path.cwd()
    else:
        current_path = Path(path).resolve()

    if current_path.is_file():
        current_path = current_path.parent

    for parent in [current_path, *current_path.parents]:
        if (parent / "uv.lock").exists() or (parent / ".git").exists():
            return parent

    # Fallback: look for pyproject.toml but this might return package root
    # instead of workspace root in a monorepo.
    for parent in [current_path, *current_path.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    # Fallback to current working directory
    return Path.cwd()
