from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import requests


@dataclass
class ModelAttempt:
    """Records a single execution attempt of a model."""
    model: str
    attempt: int
    status: str  # "success" | "failed" | "skipped"
    error_type: str | None = None
    error_message: str | None = None
    elapsed_seconds: float = 0.0


@dataclass
class GenerationResult:
    """Outcome of an image generation operation."""
    success: bool
    output_path: Path | None = None
    model_used: str | None = None
    provider_used: str | None = None
    attempts_taken: int = 0
    elapsed_seconds: float = 0.0
    seed_used: int | None = None
    resolution: tuple[int, int] = (2048, 1152)
    models_tried: list[ModelAttempt] = field(default_factory=list)
    error_summary: str | None = None

    def format_report(self) -> str:
        """Constructs clear, professional log report without exposing secrets."""
        if self.success:
            return (
                f"[IMAGE GENERATION SUCCESS]\n"
                f"  Output:     {self.output_path}\n"
                f"  Model:      {self.model_used}\n"
                f"  Resolution: {self.resolution[0]}x{self.resolution[1]}\n"
                f"  Seed:       {self.seed_used}\n"
                f"  Attempts:   {self.attempts_taken}\n"
                f"  Time:       {self.elapsed_seconds:.2f}s"
            )
        else:
            lines = [
                "==================================================",
                "IMAGE GENERATION FAILED",
                "==================================================",
                "Models tried:",
            ]
            for attempt in self.models_tried:
                err_info = f"{attempt.error_type} ({attempt.error_message})" if attempt.error_type else "failed"
                lines.append(f"  - {attempt.model} (attempt {attempt.attempt}): {err_info}")
            lines.append("No image generated.")
            lines.append("==================================================")
            return "\n".join(lines)


def classify_error(exc: Exception) -> tuple[str, bool]:
    """Classifies an error into a human-readable category and determines if it is retryable.
    
    Returns:
        (category_name, is_retryable)
    """
    exc_name = type(exc).__name__
    msg = str(exc)

    # 1. HTTP Status Code Inspection (e.g. from HfHubHTTPError or requests.HTTPError)
    status_code: int | None = None
    if hasattr(exc, "response") and exc.response is not None:
        status_code = getattr(exc.response, "status_code", None)

    if status_code is not None:
        if status_code in (401, 403):
            return "Authentication Error", False
        if status_code == 404:
            return "Model Unavailable / Not Found", False
        if status_code == 402:
            return "Payment Required / Quota Exceeded", False
        if status_code in (400, 422):
            return "Invalid Request / Unsupported Parameters", False
        if status_code == 410:
            return "Endpoint Gone", False
        if status_code == 429:
            return "Rate Limit Exceeded", True
        if status_code in (500, 502, 503, 504):
            return f"Server Error ({status_code})", True

    # 2. Timeout Inspection
    if isinstance(exc, (TimeoutError, requests.exceptions.Timeout)):
        return "Request Timeout", True
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return "Request Timeout", True

    # 3. Connection / Network Glitches
    if isinstance(exc, (requests.exceptions.ConnectionError, ConnectionResetError, ConnectionRefusedError)):
        return "Connection Error", True
    if "connection" in msg.lower() or "network" in msg.lower() or "remotely closed" in msg.lower():
        return "Connection Error", True

    # 4. Message Content Fallbacks
    lower_msg = msg.lower()
    if "not found" in lower_msg or "404" in lower_msg:
        return "Model Unavailable / Not Found", False
    if "unsupported" in lower_msg or "invalid" in lower_msg:
        return "Invalid Request / Unsupported Model", False
    if "rate limit" in lower_msg or "429" in lower_msg:
        return "Rate Limit Exceeded", True
    if "503" in lower_msg or "service unavailable" in lower_msg:
        return "Server Error (503 Service Unavailable)", True
    if "502" in lower_msg or "bad gateway" in lower_msg:
        return "Server Error (502 Bad Gateway)", True
    if "504" in lower_msg or "gateway timeout" in lower_msg:
        return "Server Error (504 Gateway Timeout)", True

    return f"General Error ({exc_name})", True
