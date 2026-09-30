from __future__ import annotations

import time
import logging
from typing import Any
from PIL import Image
from huggingface_hub import InferenceClient

try:
    from .config import (
        IMAGE_MODELS,
        AUTO_FALLBACK_KEY,
        MAX_RETRIES_PER_MODEL,
        BACKOFF_BASE_SECONDS,
        DEFAULT_REQUEST_TIMEOUT,
        get_hf_token,
    )
    from .models import ModelAttempt, classify_error
except ImportError:
    from image_engine_config import (
        IMAGE_MODELS,
        AUTO_FALLBACK_KEY,
        MAX_RETRIES_PER_MODEL,
        BACKOFF_BASE_SECONDS,
        DEFAULT_REQUEST_TIMEOUT,
        get_hf_token,
    )
    from image_engine_models import ModelAttempt, classify_error

logger = logging.getLogger("ImageEngine.Router")


class ImageGenerationError(RuntimeError):
    """Raised when all configured models and AUTO fallback fail to generate an image."""
    def __init__(self, message: str, models_tried: list[ModelAttempt]):
        super().__init__(message)
        self.models_tried = models_tried


class ModelRouter:
    """Orchestrates model selection, exponential retries, and fallback routing."""

    def __init__(
        self,
        client: InferenceClient | None = None,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.timeout = timeout
        self.token = get_hf_token()
        self.client = client or InferenceClient(token=self.token, timeout=self.timeout)

    def route_and_generate(
        self,
        prompt: str,
        seed: int | None = None,
        negative_prompt: str | None = None,
        width: int = 2048,
        height: int = 1152,
    ) -> tuple[Image.Image, str, str | None, list[ModelAttempt]]:
        """Executes image generation with multi-model fallback and intelligent retries.
        
        Priority order:
        1. Tongyi-MAI/Z-Image-Turbo
        2. black-forest-labs/FLUX.1-schnell
        3. Qwen/Qwen-Image-2512
        4. Qwen/Qwen-Image
        5. AUTO fallback
        
        Returns:
            (PIL.Image, successful_model_name, provider_name, list_of_all_attempts)
        """
        models_to_try = [*IMAGE_MODELS, AUTO_FALLBACK_KEY]
        all_attempts: list[ModelAttempt] = []

        for model_target in models_to_try:
            is_auto = (model_target == AUTO_FALLBACK_KEY)
            display_name = "AUTO (Provider Router)" if is_auto else model_target
            logger.info(f"Trying image model: {display_name}")

            for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
                t_start = time.time()
                try:
                    kwargs: dict[str, Any] = {
                        "prompt": prompt,
                    }
                    if not is_auto:
                        kwargs["model"] = model_target

                    # Pass resolution
                    kwargs["width"] = width
                    kwargs["height"] = height

                    if seed is not None:
                        kwargs["seed"] = seed
                    if negative_prompt:
                        kwargs["negative_prompt"] = negative_prompt

                    img = self.client.text_to_image(**kwargs)

                    elapsed = time.time() - t_start
                    attempt_rec = ModelAttempt(
                        model=display_name,
                        attempt=attempt,
                        status="success",
                        elapsed_seconds=elapsed,
                    )
                    all_attempts.append(attempt_rec)
                    logger.info(f"Model {display_name} succeeded on attempt {attempt} in {elapsed:.2f}s")
                    return img, display_name, getattr(self.client, "provider", None), all_attempts

                except Exception as exc:
                    elapsed = time.time() - t_start
                    err_type, is_retryable = classify_error(exc)
                    err_msg = str(exc)
                    if len(err_msg) > 160:
                        err_msg = err_msg[:157] + "..."

                    attempt_rec = ModelAttempt(
                        model=display_name,
                        attempt=attempt,
                        status="failed",
                        error_type=err_type,
                        error_message=err_msg,
                        elapsed_seconds=elapsed,
                    )
                    all_attempts.append(attempt_rec)

                    # PERMANENT ERROR: do NOT retry, immediately jump to next model!
                    if not is_retryable:
                        logger.warning(
                            f"Model {display_name} encountered permanent error '{err_type}'. "
                            f"Skipping immediately to next model without retrying."
                        )
                        break

                    # TEMPORARY ERROR: retry with backoff if attempts remain
                    if attempt < MAX_RETRIES_PER_MODEL:
                        sleep_s = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                        logger.warning(
                            f"Model {display_name} attempt {attempt} failed ({err_type}). "
                            f"Retrying in {sleep_s:.1f}s..."
                        )
                        time.sleep(sleep_s)
                    else:
                        logger.warning(
                            f"Model {display_name} failed all {MAX_RETRIES_PER_MODEL} attempts. "
                            f"Advancing to next model."
                        )

        # All models & AUTO failed: build detailed report
        report_lines = [
            "==================================================",
            "IMAGE GENERATION FAILED",
            "==================================================",
            "Models tried:",
        ]
        for idx, att in enumerate(all_attempts, start=1):
            report_lines.append(f"{idx}. {att.model} (attempt {att.attempt}) — {att.error_type}: {att.error_message}")
        report_lines.append("No image generated.")
        report_lines.append("==================================================")
        summary = "\n".join(report_lines)
        logger.error(summary)
        raise ImageGenerationError(summary, all_attempts)
