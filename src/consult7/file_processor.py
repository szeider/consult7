"""File discovery, formatting, and utilities for Consult7."""

import os
import re
import base64
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from .constants import DEFAULT_IGNORED, MAX_FILE_SIZE, MAX_TOTAL_SIZE, FILE_SEPARATOR

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


def is_image_file(path: Path) -> bool:
    """Check if a path corresponds to an image file."""
    return path.suffix.lower() in IMAGE_EXTENSIONS


def should_ignore_path(path: Path) -> bool:
    """Check if a path should be ignored based on default ignore list."""
    parts = path.parts
    for ignored in DEFAULT_IGNORED:
        if ignored in parts or path.name == ignored:
            return True
    return False


def discover_files(
    base_path: str, pattern: str, exclude_pattern: Optional[str] = None
) -> Tuple[List[Path], List[Path], List[str]]:
    """Discover files matching the pattern.

    Args:
        base_path: Base directory to search from
        pattern: Regex pattern to match files
        exclude_pattern: Optional regex pattern to exclude files

    Returns:
        Tuple of (text_files, image_files, errors)
    """
    errors = []
    text_files = []
    image_files = []

    try:
        base = Path(base_path).resolve()
        if not base.exists():
            errors.append(f"Path does not exist: {base_path}")
            return [], [], errors

        if not base.is_dir():
            errors.append(f"Path is not a directory: {base_path}")
            return [], [], errors

        # Compile regex patterns
        try:
            include_re = re.compile(pattern)
        except re.error as e:
            errors.append(f"Invalid include pattern '{pattern}': {e}")
            return [], [], errors

        exclude_re = None
        if exclude_pattern:
            try:
                exclude_re = re.compile(exclude_pattern)
            except re.error as e:
                errors.append(f"Invalid exclude pattern '{exclude_pattern}': {e}")
                return [], [], errors

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

                if is_image_file(file_path):
                    image_files.append(file_path)
                else:
                    text_files.append(file_path)

    except PermissionError as e:
        errors.append(f"Permission denied: {e}")
    except Exception as e:
        errors.append(f"Error during file discovery: {e}")

    return text_files, image_files, errors


def format_content(
    base_path: str,
    text_files: List[Path],
    image_files: List[Path],
    errors: List[str],
    include_images: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    """Format files into a list of content parts (text or image).

    Args:
        base_path: Base directory for relative paths
        text_files: List of text file paths to format
        image_files: List of image file paths to format
        errors: List to append errors to
        include_images: Whether to include image content

    Returns:
        Tuple of (content_parts, total_size)
    """
    content_list = []
    total_size = 0
    all_files = sorted(text_files + image_files)

    # Add capacity information
    content_list.append(
        {"text": f"File Size Budget: {MAX_TOTAL_SIZE:,} bytes (100MB)"}
    )
    content_list.append({"text": f"Files Found: {len(all_files)}"})
    content_list.append({"text": ""})

    # Add directory tree
    content_list.append({"text": "Directory Structure:"})
    content_list.append({"text": FILE_SEPARATOR})

    base = Path(base_path).resolve()
    tree_lines = []
    dirs = {}
    for file_path in all_files:
        rel_path = file_path.relative_to(base)
        dir_path = rel_path.parent
        if dir_path not in dirs:
            dirs[dir_path] = []
        dirs[dir_path].append(rel_path.name)

    for dir_path in sorted(dirs.keys()):
        if str(dir_path) == ".":
            tree_lines.append(f"{base_path}/")
        else:
            tree_lines.append(f"  {dir_path}/")
        for filename in sorted(dirs[dir_path]):
            tree_lines.append(f"    - {filename}")

    content_list.append({"text": "\n".join(tree_lines)})
    content_list.append({"text": ""})

    # Add file contents
    content_list.append({"text": "File Contents:"})
    content_list.append({"text": FILE_SEPARATOR})

    for file_path in all_files:
        content_list.append({"text": f"\nFile: {file_path}"})
        content_list.append({"text": FILE_SEPARATOR})

        try:
            file_size = file_path.stat().st_size
            estimated_size = file_size
            is_img = is_image_file(file_path)

            if is_img and include_images:
                # Base64 encoding adds ~33% overhead
                estimated_size = int(file_size * 1.33)

            if file_size > MAX_FILE_SIZE:
                content_list.append(
                    {
                        "text": f"[ERROR: File too large ({file_size:,} bytes > {MAX_FILE_SIZE:,} bytes)]"
                    }
                )
                errors.append(f"File too large: {file_path} ({file_size:,} bytes)")
            elif total_size + estimated_size > MAX_TOTAL_SIZE:
                content_list.append(
                    {"text": "[ERROR: Total size limit exceeded for subsequent files]"}
                )
                errors.append(
                    f"Total size limit reached before processing {file_path}. Estimated size: {estimated_size:,}"
                )
                break  # Stop processing further files
            else:
                if is_img:
                    if include_images:
                        try:
                            img_bytes = file_path.read_bytes()
                            base64_encoded_data = base64.b64encode(img_bytes).decode(
                                "utf-8"
                            )
                            mime_type = f"image/{file_path.suffix.lower().lstrip('.')}"
                            if file_path.suffix.lower() == ".jpg":
                                mime_type = "image/jpeg" # Common practice

                            content_list.append(
                                {
                                    "inline_data": {
                                        "mime_type": mime_type,
                                        "data": base64_encoded_data,
                                    }
                                }
                            )
                            total_size += estimated_size
                        except Exception as e:
                            content_list.append({"text": f"[ERROR reading image: {e}]"})
                            errors.append(f"Error reading image {file_path}: {e}")
                    else:
                        content_list.append(
                            {"text": "[INFO: Image file, content not included (use --include-images)]"}
                        )
                        # Add original file size even if not included for context
                        total_size += file_size
                else: # Text file
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    content_list.append({"text": content})
                    total_size += file_size

        except PermissionError:
            content_list.append({"text": "[ERROR: Permission denied]"})
            errors.append(f"Permission denied reading file: {file_path}")
        except Exception as e:
            content_list.append({"text": f"[ERROR: {e}]"})
            errors.append(f"Error processing file {file_path}: {e}")

        content_list.append({"text": ""})  # Separator after each file's content or error

    # Add errors summary if any
    if errors:
        content_list.append({"text": FILE_SEPARATOR})
        content_list.append({"text": "Errors encountered:"})
        for error in errors:
            content_list.append({"text": f"- {error}"})

    return content_list, total_size
