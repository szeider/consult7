"""File discovery, formatting, and utilities for Consult7."""

import os
import glob
from pathlib import Path
from typing import Tuple, List

from .constants import DEFAULT_IGNORED, MAX_FILE_SIZE, MAX_TOTAL_SIZE, FILE_SEPARATOR


def should_ignore_path(path: Path) -> bool:
    """Check if a path should be ignored based on default ignore list."""
    parts = path.parts
    for ignored in DEFAULT_IGNORED:
        if ignored in parts or path.name == ignored:
            return True
    return False


def expand_file_patterns(file_patterns: List[str]) -> Tuple[List[Path], List[str]]:
    """Expand file patterns into actual file paths.

    Args:
        file_patterns: List of file paths/patterns (wildcards allowed only in filename)

    Returns:
        Tuple of (matching_files, errors)
    """
    errors = []
    matching_files = set()  # Use set to avoid duplicates

    for pattern in file_patterns:
        try:
            # Validate absolute path
            if not os.path.isabs(pattern):
                errors.append(f"Path must be absolute: {pattern}")
                continue

            # Check for wildcards
            if "*" in pattern:
                # Ensure wildcard is only in filename portion
                dir_part = os.path.dirname(pattern)
                file_part = os.path.basename(pattern)

                if "*" in dir_part:
                    errors.append(f"Wildcards only allowed in filename, not path: {pattern}")
                    continue

                # Ensure extension is specified
                if "." not in file_part.split("*")[-1]:
                    errors.append(f"Extension must be specified with wildcards: {pattern}")
                    continue

                # Use glob to expand
                expanded = glob.glob(pattern)
                for file_path in expanded:
                    path_obj = Path(file_path)
                    if path_obj.is_file() and not should_ignore_path(path_obj):
                        matching_files.add(path_obj)
            else:
                # Specific file path
                path_obj = Path(pattern)
                if path_obj.exists():
                    if path_obj.is_dir():
                        errors.append(f"Directory provided, must specify files: {pattern}")
                    elif not should_ignore_path(path_obj):
                        matching_files.add(path_obj)
                else:
                    errors.append(f"File does not exist: {pattern}")

        except Exception as e:
            errors.append(f"Error processing pattern '{pattern}': {e}")

    return sorted(list(matching_files)), errors


def format_content(files: List[Path], errors: List[str]) -> Tuple[str, int]:
    """Format files into text content.

    Args:
        files: List of file paths to format
        errors: List to append errors to

    Returns:
        Tuple of (content, total_size)
    """
    content_parts = []
    total_size = 0

    # Add capacity information
    content_parts.append(f"File Size Budget: {MAX_TOTAL_SIZE:,} bytes (4MB for ~1M tokens)")
    content_parts.append(f"Files Found: {len(files)}")
    content_parts.append("")

    # Add file list (no tree needed since files can be from anywhere)
    content_parts.append("Files to Process:")
    content_parts.append(FILE_SEPARATOR)

    # Group files by directory for cleaner display
    dirs = {}
    for file in sorted(files):
        dir_path = file.parent
        if dir_path not in dirs:
            dirs[dir_path] = []
        dirs[dir_path].append(file.name)

    # Display grouped files
    for dir_path in sorted(dirs.keys()):
        content_parts.append(f"{dir_path}/")
        for filename in sorted(dirs[dir_path]):
            content_parts.append(f"  - {filename}")

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
