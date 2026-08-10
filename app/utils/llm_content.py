"""Facade — preferir app.utils.llm_models para lógica por modelo."""

from __future__ import annotations

from typing import Any

from app.utils.llm_models import (
    extract_llm_text,
    extract_response_text,
    parse_json_object,
    parse_model_json,
    resolve_model_family,
)


def extract_llm_text_from_response(response: Any, model: str = "") -> str:
    if model:
        return extract_response_text(response, model)
    return extract_response_text(response, "generic")
