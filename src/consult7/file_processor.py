"""File discovery, formatting, and utilities for Consult7."""

import os
import glob
from collections import defaultdict
from pathlib import Path
from typing import Tuple, List

from .constants import DEFAULT_IGNORED, MAX_FILE_SIZE, MAX_TOTAL_SIZE, FILE_SEPARATOR


def should_ignore_path(path: Path) -> bool:
    """Check if a path should be ignored based on default ignore list."""
    return any(ignored in path.parts or path.name == ignored for ignored in DEFAULT_IGNORED)


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
                errors.append(
                    f"Path must be absolute: {pattern}\n"
                    f"  Hint: Use absolute paths starting with / (e.g., /Users/name/project/file.py)"
                )
                continue

            # Check for wildcards
            if "*" in pattern:
                # Ensure wildcard is only in filename portion
                dir_part = os.path.dirname(pattern)
                file_part = os.path.basename(pattern)

                if "*" in dir_part:
                    errors.append(
                        f"Wildcards only allowed in filename, not path: {pattern}\n"
                        f"  Example: /path/to/dir/*.py (not /path/*/dir/*.py)"
                    )
                    continue

                # Ensure extension is specified
                if "." not in file_part.split("*")[-1]:
                    errors.append(
                        f"Extension must be specified with wildcards: {pattern}\n"
                        f"  Example: *.py (not just *)"
                    )
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
                        errors.append(
                            f"Directory provided, must specify files: {pattern}\n"
                            f"  Hint: Use wildcards to select files (e.g., {pattern}/*.py)"
                        )
                    elif not should_ignore_path(path_obj):
                        matching_files.add(path_obj)
                else:
                    errors.append(
                        f"File not found: {pattern}\n"
                        f"  Check: Path is absolute? File exists? Correct spelling?"
                    )

        except Exception as e:
            errors.append(f"Error processing pattern '{pattern}': {e}")

    return sorted(list(matching_files)), errors


def format_content(
    files: List[Path],
    errors: List[str],
    max_total_size: int = MAX_TOTAL_SIZE,
    max_file_size: int = MAX_FILE_SIZE
) -> Tuple[str, int]:
    """Format files into text content.

    Args:
        files: List of file paths to format
        errors: List to append errors to
        max_total_size: Maximum total size in bytes (model-dependent)
        max_file_size: Maximum per-file size in bytes (model-dependent)

    Returns:
        Tuple of (content, total_size)
    """
    content_parts = []
    total_size = 0

    sorted_files = sorted(files)

    # Add capacity information
    content_parts.append(f"File Size Budget: {max_total_size:,} bytes (~{max_total_size // 4:,} tokens)")
    content_parts.append(f"Files Found: {len(files)}")
    content_parts.append("")

    # Add file list (no tree needed since files can be from anywhere)
    content_parts.append("Files to Process:")
    content_parts.append(FILE_SEPARATOR)

    # Group files by directory for cleaner display
    dirs: dict[Path, list[str]] = defaultdict(list)
    for file in sorted_files:
        dirs[file.parent].append(file.name)

    # Display grouped files
    for dir_path in sorted(dirs):
        content_parts.append(f"{dir_path}/")
        for filename in sorted(dirs[dir_path]):
            content_parts.append(f"  - {filename}")

    content_parts.append("")

    # Add file contents
    content_parts.append("File Contents:")
    content_parts.append(FILE_SEPARATOR)

    for file in sorted_files:
        content_parts.append(f"\nFile: {file}")
        content_parts.append(FILE_SEPARATOR)

        try:
            # Check file size
            file_size = file.stat().st_size
            if file_size > max_file_size:
                content_parts.append(
                    f"[ERROR: File too large ({file_size} bytes > {max_file_size} bytes)]"
                )
                errors.append(f"File too large: {file} ({file_size} bytes)")
            elif total_size + file_size > max_total_size:
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


def save_output_to_file(content: str, output_path: str) -> Tuple[str, str]:
    """Save content to a file with conflict resolution.

    Args:
        content: The content to save
        output_path: The desired output file path

    Returns:
        Tuple of (actual_save_path, error_message)
        - actual_save_path: Path where content was saved (may differ from output_path)
        - error_message: Error message if save failed, empty string on success
    """
    try:
        # Validate absolute path
        if not os.path.isabs(output_path):
            return "", (
                f"Output path must be absolute: {output_path}\n"
                f"Hint: Use absolute paths like /Users/name/reports/output.md"
            )

        path_obj = Path(output_path)

        # Handle existing file conflict
        if path_obj.exists():
            # Create new filename with "_updated" suffix
            stem = path_obj.stem
            suffix = path_obj.suffix
            parent = path_obj.parent
            new_path = parent / f"{stem}_updated{suffix}"

            # Keep trying with additional "_updated" suffixes if needed
            counter = 1
            while new_path.exists() and counter < 100:
                new_path = parent / f"{stem}_updated_{counter}{suffix}"
                counter += 1

            if counter >= 100:
                return "", (
                    f"Too many existing files with '_updated' suffix for: {output_path}\n"
                    f"Hint: Clean up old _updated files or choose a different filename"
                )

            path_obj = new_path

        # Ensure parent directory exists
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Write the content
        path_obj.write_text(content, encoding="utf-8")

        return str(path_obj), ""

    except PermissionError:
        return "", (
            f"Permission denied writing to: {output_path}\n"
            f"Check: Do you have write access to this directory?"
        )
    except Exception as e:
        return "", f"Error saving file: {e}"
