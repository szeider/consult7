"""File discovery, formatting, and utilities for Consult7."""

import bisect
import os
import glob
import re
import zlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from .constants import DEFAULT_IGNORED, MAX_TOTAL_SIZE, MAX_PDF_PAYLOAD, FILE_SEPARATOR


@dataclass
class PdfFile:
    """A PDF to send to the model as a native document part (v3.12.0)."""

    path: Path
    data: bytes
    pages: int  # 0 = could not be determined


# "/Type /Page" (not "/Pages"), in plain objects or inside Flate-compressed
# object streams (pdfTeX and most modern producers). Pages are counted by
# object number, because incremental updates (arXiv restamping, macOS Preview)
# rewrite page objects and leave the old copies in the file.
_PAGE_RE = re.compile(rb"/Type\s*/Page(?![s\w])")
_OBJ_HEADER_RE = re.compile(rb"(\d+)\s+\d+\s+obj\s*$")
_OBJSTM_RE = re.compile(rb"/Type\s*/ObjStm")
_STREAM_START_RE = re.compile(rb"stream\r?\n")
_INT_RE = re.compile(rb"/(N|First)\s+(\d+)")


def _owning_object(data: bytes, pos: int) -> Optional[int]:
    """Object number of the 'N G obj' header nearest before pos, if any."""
    header_end = data.rfind(b" obj", max(0, pos - 200_000), pos)
    if header_end == -1:
        return None
    header = _OBJ_HEADER_RE.search(data[max(0, header_end - 40) : header_end + 4])
    return int(header.group(1)) if header else None


def count_pdf_pages(data: bytes) -> int:
    """Count pages without a PDF library. Returns 0 when nothing is found
    (unknown), never raises. Only literal searches: no regex may scan the
    whole file with backtracking (a tempered-dot version took 97 s on 9 MB)."""
    page_objects: set = set()

    for match in _PAGE_RE.finditer(data):
        if (number := _owning_object(data, match.start())) is not None:
            page_objects.add(number)

    for match in _OBJSTM_RE.finditer(data):
        dict_start = data.rfind(b" obj", max(0, match.start() - 2_000), match.start())
        stream = _STREAM_START_RE.search(data, match.end(), match.end() + 2_000)
        if dict_start == -1 or not stream:
            continue
        fields = dict(_INT_RE.findall(data[dict_start : stream.start()]))
        stream_end = data.find(b"endstream", stream.end())
        if b"First" not in fields or stream_end == -1:
            continue
        try:
            body = zlib.decompressobj().decompress(data[stream.end() : stream_end])
        except zlib.error:
            continue
        first = int(fields[b"First"])
        header_ints = body[:first].split()
        starts = sorted(
            (int(header_ints[i + 1]), int(header_ints[i]))
            for i in range(0, len(header_ints) - 1, 2)
        )
        for page in _PAGE_RE.finditer(body, first):
            offset = page.start() - first
            index = bisect.bisect_right(starts, (offset, float("inf"))) - 1
            if index >= 0:
                page_objects.add(starts[index][1])

    return len(page_objects)


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

                # Use glob to expand; a pattern that selects nothing is an error,
                # not a silent query-only call
                found = [Path(p) for p in glob.glob(pattern) if Path(p).is_file()]
                kept = [p for p in found if not should_ignore_path(p)]
                if not kept:
                    skipped = len(found)
                    note = (
                        f" ({skipped} matching file{'s' if skipped != 1 else ''} on the ignore list)"
                        if skipped
                        else ""
                    )
                    errors.append(f"No files match pattern: {pattern}{note}")
                    continue
                matching_files.update(kept)
            else:
                # Specific file path
                path_obj = Path(pattern)
                if path_obj.exists():
                    if path_obj.is_dir():
                        errors.append(
                            f"Directory provided, must specify files: {pattern}\n"
                            f"  Hint: Use wildcards to select files (e.g., {pattern}/*.py)"
                        )
                    elif should_ignore_path(path_obj):
                        errors.append(
                            f"File is on the ignore list and is never sent: {pattern}\n"
                            f"  Ignored: {', '.join(DEFAULT_IGNORED)}"
                        )
                    else:
                        matching_files.add(path_obj)
                else:
                    errors.append(
                        f"File not found: {pattern}\n"
                        f"  Check: Path is absolute? File exists? Correct spelling?"
                    )

        except Exception as e:
            errors.append(f"Error processing pattern '{pattern}': {e}")

    return sorted(list(matching_files)), errors


def is_pdf_path(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def format_content(
    files: List[Path],
    errors: List[str],
    max_total_size: int = MAX_TOTAL_SIZE,
) -> Tuple[str, int, List[PdfFile]]:
    """Format files into text content; PDFs are returned separately.

    Args:
        files: List of file paths to format
        errors: List to append errors to (binary, unreadable, over budget)
        max_total_size: Maximum total text size in bytes (model-dependent)

    Returns:
        Tuple of (content, total_size, pdfs). total_size counts every file
        (text and PDF bytes), so an over-budget error can report the full size
        of the request. PDFs do not count against max_total_size (their bytes
        are no token proxy); they have their own wire-size budget and a
        per-page token estimate.
    """
    content_parts = []
    total_size = 0
    text_size = 0
    pdf_payload = 0  # base64 size, what actually goes over the wire
    pdfs: List[PdfFile] = []

    sorted_files = sorted(files)

    # Add capacity information
    content_parts.append(
        f"File Size Budget: {max_total_size:,} bytes (~{max_total_size // 4:,} tokens)"
    )
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
            tag = " (PDF, attached as a document)" if filename.lower().endswith(".pdf") else ""
            content_parts.append(f"  - {filename}{tag}")

    content_parts.append("")

    # Add file contents
    content_parts.append("File Contents:")
    content_parts.append(FILE_SEPARATOR)

    # Errors are not added to the prompt: the caller fails the call on any error
    # before anything is sent, so the LLM never sees a partial bundle.
    for file in sorted_files:
        try:
            size = file.stat().st_size
            total_size += size
            if is_pdf_path(file):
                pdf_payload += (size + 2) // 3 * 4
                if pdf_payload > MAX_PDF_PAYLOAD:
                    continue  # over budget: keep summing for the error, skip reading
            else:
                text_size += size
                if text_size > max_total_size:
                    continue
            data = file.read_bytes()
        except PermissionError:
            errors.append(f"Permission denied reading file: {file}")
            continue
        except Exception as e:
            errors.append(f"Error reading file {file}: {e}")
            continue

        if is_pdf_path(file):
            # Sent to the model as a native document part, not as text
            if not data.startswith(b"%PDF-"):
                errors.append(f"Not a PDF (missing %PDF header), not sent: {file}")
                continue
            pdf = PdfFile(file, data, count_pdf_pages(data))
            pdfs.append(pdf)
            pages = f"{pdf.pages} pages" if pdf.pages else "page count unknown"
            content_parts.append(f"\nFile: {file}")
            content_parts.append(FILE_SEPARATOR)
            content_parts.append(f"[PDF, {pages}: attached as document '{file.name}' below]")
            content_parts.append("")
            continue

        # Same heuristic as git: a NUL byte near the start means binary
        if b"\x00" in data[:8192]:
            errors.append(f"Binary file (contains NUL bytes), not sent: {file}")
            continue

        content_parts.append(f"\nFile: {file}")
        content_parts.append(FILE_SEPARATOR)
        content_parts.append(data.decode("utf-8", errors="replace"))
        content_parts.append("")

    if text_size > max_total_size:
        errors.append(
            f"Total text size {text_size:,} bytes exceeds the {max_total_size:,}-byte budget "
            f"(model context minus output and reasoning reserve, ~4 bytes per token)"
        )
    if pdf_payload > MAX_PDF_PAYLOAD:
        errors.append(
            f"PDFs total {pdf_payload:,} bytes base64-encoded, over the {MAX_PDF_PAYLOAD:,}-byte "
            f"request limit; send fewer or smaller PDFs, or convert them to text first"
        )

    return "\n".join(content_parts), total_size, pdfs


def validate_output_path(output_path: str) -> str:
    """Check before the LLM call that output_path can be written.

    Returns an error message, or an empty string if the path looks writable.
    The parent directory may not exist yet (save creates it), so the nearest
    existing ancestor must be a writable directory.
    """
    if not os.path.isabs(output_path):
        return (
            f"Output path must be absolute: {output_path}\n"
            f"Hint: Use absolute paths like /Users/name/reports/output.md"
        )

    path_obj = Path(output_path)
    if path_obj.is_dir():
        return f"Output path is a directory, not a file: {output_path}"

    ancestor = path_obj.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not ancestor.is_dir():
        return f"Cannot create {path_obj.parent}: {ancestor} is not a directory"
    if not os.access(ancestor, os.W_OK):
        return f"Permission denied: cannot write under {ancestor}"
    return ""


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
