"""File discovery, formatting, and utilities for Consult7."""

import os
import re
from pathlib import Path
from typing import Optional, Tuple, List

from .constants import DEFAULT_IGNORED, MAX_FILE_SIZE, MAX_TOTAL_SIZE, FILE_SEPARATOR


def should_ignore_path(path: Path) -> bool:
    """Check if a path should be ignored based on default ignore list."""
    parts = path.parts
    for ignored in DEFAULT_IGNORED:
        if ignored in parts or path.name == ignored:
            return True
    return False


def discover_files(
    base_path: str, pattern: str, exclude_pattern: Optional[str] = None
) -> Tuple[List[Path], List[str]]:
    """Discover files matching the pattern.

    Args:
        base_path: Base directory to search from
        pattern: Regex pattern to match files
        exclude_pattern: Optional regex pattern to exclude files

    Returns:
        Tuple of (matching_files, errors)
    """
    errors = []
    matching_files = []

    try:
        base = Path(base_path).resolve()
        if not base.exists():
            errors.append(f"Path does not exist: {base_path}")
            return [], errors

        if not base.is_dir():
            errors.append(f"Path is not a directory: {base_path}")
            return [], errors

        # Compile regex patterns
        try:
            include_re = re.compile(pattern)
        except re.error as e:
            errors.append(f"Invalid include pattern '{pattern}': {e}")
            return [], errors

        exclude_re = None
        if exclude_pattern:
            try:
                exclude_re = re.compile(exclude_pattern)
            except re.error as e:
                errors.append(f"Invalid exclude pattern '{exclude_pattern}': {e}")
                return [], errors

        # Walk directory tree
        for root, dirs, files in os.walk(base):
            root_path = Path(root)

            # Skip ignored directories
            dirs[:] = [d for d in dirs if not should_ignore_path(root_path / d)]

            for file in files:
                file_path = root_path / file

                # Skip ignored files
                if should_ignore_path(file_path):
                    continue

                # Check include pattern
                if not include_re.match(file):
                    continue

                # Check exclude pattern
                if exclude_re and exclude_re.match(file):
                    continue

                matching_files.append(file_path)

    except PermissionError as e:
        errors.append(f"Permission denied: {e}")
    except Exception as e:
        errors.append(f"Error during file discovery: {e}")

    return matching_files, errors


def format_content(
    base_path: str, files: List[Path], errors: List[str]
) -> Tuple[str, int]:
    """Format files into text content.

    Args:
        base_path: Base directory for relative paths
        files: List of file paths to format
        errors: List to append errors to

    Returns:
        Tuple of (content, total_size)
    """
    content_parts = []
    total_size = 0

    # Add capacity information
    content_parts.append(f"File Size Budget: {MAX_TOTAL_SIZE:,} bytes (100MB)")
    content_parts.append(f"Files Found: {len(files)}")
    content_parts.append("")

    # Add directory tree
    content_parts.append("Directory Structure:")
    content_parts.append(FILE_SEPARATOR)

    # Build simple tree structure
    base = Path(base_path).resolve()
    tree_lines = []

    # Group files by directory
    dirs = {}
    for file in sorted(files):
        rel_path = file.relative_to(base)
        dir_path = rel_path.parent
        if dir_path not in dirs:
            dirs[dir_path] = []
        dirs[dir_path].append(rel_path.name)

    # Format tree
    for dir_path in sorted(dirs.keys()):
        if str(dir_path) == ".":
            tree_lines.append(f"{base_path}/")
        else:
            tree_lines.append(f"  {dir_path}/")
        for filename in sorted(dirs[dir_path]):
            tree_lines.append(f"    - {filename}")

    content_parts.extend(tree_lines)
    content_parts.append("")

    # Add file contents
    content_parts.append("File Contents:")
    content_parts.append(FILE_SEPARATOR)

    for file in sorted(files):
        content_parts.append(f"\nFile: {file}")
        content_parts.append(FILE_SEPARATOR)

        try:
            # Check file size
            file_size = file.stat().st_size
            if file_size > MAX_FILE_SIZE:
                content_parts.append(
                    f"[ERROR: File too large ({file_size} bytes > {MAX_FILE_SIZE} bytes)]"
                )
                errors.append(f"File too large: {file} ({file_size} bytes)")
            elif total_size + file_size > MAX_TOTAL_SIZE:
                content_parts.append("[ERROR: Total size limit exceeded]")
                errors.append(f"Total size limit exceeded at file: {file}")
                break
            else:
                # Read file content
                content = file.read_text(encoding="utf-8", errors="replace")
                content_parts.append(content)
                total_size += file_size

        except PermissionError:
            content_parts.append("[ERROR: Permission denied]")
            errors.append(f"Permission denied reading file: {file}")
        except Exception as e:
            content_parts.append(f"[ERROR: {e}]")
            errors.append(f"Error reading file {file}: {e}")

        content_parts.append("")

    # Add errors summary if any
    if errors:
        content_parts.append(FILE_SEPARATOR)
        content_parts.append("Errors encountered:")
        for error in errors:
            content_parts.append(f"- {error}")

    return "\n".join(content_parts), total_size
