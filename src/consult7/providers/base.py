"""Base provider interface and shared utilities for Consult7."""

import base64
from abc import ABC, abstractmethod
from typing import Optional, Sequence, Tuple, Union

from ..constants import MAX_RESPONSE_SIZE, PDF_PAGE_FALLBACK_BYTES
from ..file_processor import PdfFile
from ..token_utils import estimate_tokens, estimate_pdf_tokens

SYSTEM_PROMPT = (
    "You are a helpful assistant analyzing code and files. Be specific and precise. "
    "Match the length of your answer to the task — thorough when the question needs "
    "depth or breadth, short when it doesn't. Lead with the key finding; don't pad."
)


def build_user_text(content: str, query: str) -> str:
    """The text part of the user message; also used for token estimates."""
    if content:
        return f"Here are the files to analyze:\n\n{content}\n\nQuery: {query}"
    return query


def build_messages(
    content: str, query: str, pdfs: Sequence[PdfFile] = ()
) -> Tuple[str, Union[str, list]]:
    """Return (system, user) message contents. The user content is a plain string,
    or a content-part list when PDFs are attached: the text part first, then one
    `file` part per PDF (OpenRouter's native PDF input, base64 data URL)."""
    text = build_user_text(content, query)
    if not pdfs:
        return SYSTEM_PROMPT, text
    parts: list = [{"type": "text", "text": text}]
    for pdf in pdfs:
        encoded = base64.b64encode(pdf.data).decode("ascii")
        parts.append(
            {
                "type": "file",
                "file": {
                    "filename": pdf.path.name,
                    "file_data": f"data:application/pdf;base64,{encoded}",
                },
            }
        )
    return SYSTEM_PROMPT, parts


def pdf_page_count(pdfs: Sequence[PdfFile]) -> int:
    """Total pages, with a size-based guess for PDFs whose count is unknown."""
    return sum(p.pages or max(1, len(p.data) // PDF_PAGE_FALLBACK_BYTES) for p in pdfs)


def estimate_input_tokens(
    content: str, query: str, pdfs: Sequence[PdfFile], model_name: str
) -> int:
    """Prompt-token estimate shared by consultation.py and the provider."""
    tokens = estimate_tokens(SYSTEM_PROMPT + build_user_text(content, query))
    if pdfs:
        tokens += estimate_pdf_tokens(model_name, pdf_page_count(pdfs))
    return tokens


def process_llm_response(response_content: Optional[str]) -> str:
    """Normalize and truncate LLM response if needed.

    Args:
        response_content: The response content from the LLM

    Returns:
        Processed response content
    """
    response = response_content or ""
    if len(response) > MAX_RESPONSE_SIZE:
        return response[:MAX_RESPONSE_SIZE] + "\n[TRUNCATED - Response exceeded size limit]"
    return response


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def get_model_info(self, model_name: str, api_key: Optional[str]) -> Optional[dict]:
        """Get model context information.

        Args:
            model_name: The name of the model
            api_key: API key for the provider

        Returns:
            Dictionary with model information, {"found": False, "suggestions": [...]}
            when the model list was fetched but does not contain the model, or None
            if the list is not available.
            Expected keys when found: context_length, max_output_tokens, provider
        """
        pass

    @abstractmethod
    async def call_llm(
        self,
        content: str,
        query: str,
        model_name: str,
        api_key: str,
        thinking_mode: bool = False,
        thinking_budget: Optional[int] = None,
        zdr: bool = False,
        mode: str = "fast",
        pdfs: Sequence[PdfFile] = (),
    ) -> Tuple[str, Optional[str], Optional[int], Optional[float]]:
        """Call the LLM and return the response.

        Args:
            content: The formatted file content
            query: The user's query
            model_name: The model to use
            api_key: API key for the provider
            thinking_mode: Whether thinking/reasoning mode is enabled
            thinking_budget: Number of thinking tokens to use (if applicable)
            zdr: Whether to enforce Zero Data Retention routing
            mode: Performance mode ("fast"/"mid"/"think"); used by models like
                Fusion that map mode to a deliberation knob rather than reasoning tokens
            pdfs: PDFs to attach as native document parts

        Returns:
            Tuple of (response, error_message, actual_thinking_budget_used, cost_usd).
            cost_usd is the call's cost in USD, or None if unavailable.
        """
        pass
