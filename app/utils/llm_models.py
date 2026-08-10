"""
Adaptadores de resposta por modelo Gemini (e extensível a outros).

Famílias:
- gemini_legacy: content tipicamente string (Gemini 2.x)
- gemini_blocks: content como lista [{type, text, ...}] (Gemini 3.5+)
- generic: tenta blocks e depois legacy (modelos desconhecidos)
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ModelFamily(str, Enum):
    GEMINI_LEGACY = "gemini_legacy"
    GEMINI_BLOCKS = "gemini_blocks"
    GENERIC = "generic"


# Slugs conhecidos — adicione aqui ao testar novos modelos.
KNOWN_MODEL_FAMILIES: dict[str, ModelFamily] = {
    "gemini-2.0-flash": ModelFamily.GEMINI_LEGACY,
    "gemini-2.0-flash-lite": ModelFamily.GEMINI_LEGACY,
    "gemini-2.5-flash": ModelFamily.GEMINI_LEGACY,
    "gemini-2.5-flash-lite": ModelFamily.GEMINI_LEGACY,
    "gemini-2.5-pro": ModelFamily.GEMINI_LEGACY,
    "gemini-3.5-flash": ModelFamily.GEMINI_BLOCKS,
    "gemini-3.5-flash-lite": ModelFamily.GEMINI_BLOCKS,
}


def normalize_model_slug(model: str) -> str:
    return (model or "").strip().lower()


def resolve_model_family(model: str) -> ModelFamily:
    slug = normalize_model_slug(model)
    if slug in KNOWN_MODEL_FAMILIES:
        return KNOWN_MODEL_FAMILIES[slug]

    if re.search(r"gemini-3\.5|gemini_3\.5|3\.5-flash", slug):
        logger.info("Modelo '%s' inferido como gemini_blocks (3.5).", model)
        return ModelFamily.GEMINI_BLOCKS

    if slug.startswith("gemini-"):
        logger.info("Modelo '%s' inferido como gemini_legacy.", model)
        return ModelFamily.GEMINI_LEGACY

    logger.warning("Modelo '%s' desconhecido; usando extrator generic.", model)
    return ModelFamily.GENERIC


def _join_content_blocks(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text")
            if text is not None:
                parts.append(str(text))
        else:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(str(text))
    return "\n".join(p for p in parts if p)


def _extract_gemini_legacy(response: Any) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str) and content.strip():
        return content

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    if isinstance(content, list):
        joined = _join_content_blocks(content)
        if joined.strip():
            logger.debug("gemini_legacy recebeu content em blocos; normalizando.")
            return joined

    return _join_content_blocks(content)


def _extract_gemini_blocks(response: Any) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, list):
        return _join_content_blocks(content)

    if isinstance(content, str) and content.strip():
        logger.debug("gemini_blocks recebeu content string; usando direto.")
        return content

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    return _join_content_blocks(content)


def _extract_generic(response: Any) -> str:
    blocks = _extract_gemini_blocks(response)
    if blocks.strip():
        return blocks
    return _extract_gemini_legacy(response)


_EXTRACTORS: dict[ModelFamily, Callable[[Any], str]] = {
    ModelFamily.GEMINI_LEGACY: _extract_gemini_legacy,
    ModelFamily.GEMINI_BLOCKS: _extract_gemini_blocks,
    ModelFamily.GENERIC: _extract_generic,
}


def extract_response_text(response: Any, model: str) -> str:
    family = resolve_model_family(model)
    text = _EXTRACTORS[family](response)
    if not text.strip():
        logger.warning(
            "Resposta vazia após extração (modelo=%s, família=%s).",
            model,
            family.value,
        )
    return text


def extract_llm_text(content: Any) -> str:
    """Normaliza content bruto (sem objeto response) — ex.: histórico de revisão."""
    return _join_content_blocks(content)


def strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = strip_json_fences(text)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise json.JSONDecodeError("Expected JSON object", cleaned, 0)
    return data


def parse_model_json(text: str, model: str) -> dict[str, Any]:
    """Parse JSON do veredito; família blocks tende a usar cercas markdown com mais frequência."""
    family = resolve_model_family(model)
    try:
        return parse_json_object(text)
    except json.JSONDecodeError:
        if family == ModelFamily.GEMINI_BLOCKS:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return parse_json_object(match.group(0))
        raise
