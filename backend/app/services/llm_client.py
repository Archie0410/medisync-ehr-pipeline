"""Abstracted LLM client — supports Gemini, OpenAI, and Azure OpenAI.

Configured via env/settings:
    EXTRACTION_PROVIDER = "gemini" | "openai" | "azure_openai"
    EXTRACTION_MODEL    = "gemini-2.0-flash" | "gpt-4o-mini" | …
    GEMINI_API_KEY      = "…"
    OPENAI_API_KEY      = "…"
    AZURE_OPENAI_API_KEY = "…"
    AZURE_OPENAI_ENDPOINT = "https://<resource>.openai.azure.com/"
    AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-35-turbo"
"""

import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger("medisync.llm_client")


async def complete(system_prompt: str, user_prompt: str) -> str:
    """Send a prompt to the configured LLM and return the raw text response."""
    settings = get_settings()
    provider = settings.extraction_provider.lower()

    if provider == "gemini":
        return await _gemini_complete(system_prompt, user_prompt, settings)
    elif provider == "openai":
        return await _openai_complete(system_prompt, user_prompt, settings)
    elif provider == "azure_openai":
        return await _azure_openai_complete(system_prompt, user_prompt, settings)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def complete_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call LLM and parse the response as JSON."""
    raw = await complete(system_prompt, user_prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
    return json.loads(raw)


# ---- Gemini ----

async def _gemini_complete(system_prompt: str, user_prompt: str, settings) -> str:
    import google.generativeai as genai

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.extraction_model,
        system_instruction=system_prompt,
    )

    response = model.generate_content(user_prompt)
    return response.text


# ---- OpenAI ----

async def _openai_complete(system_prompt: str, user_prompt: str, settings) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("pip install openai  to use the OpenAI provider")

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.extraction_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


# ---- Azure OpenAI ----

async def _azure_openai_complete(system_prompt: str, user_prompt: str, settings) -> str:
    try:
        from openai import AzureOpenAI
    except ImportError:
        raise RuntimeError("pip install openai to use the Azure OpenAI provider")

    if not settings.azure_openai_api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY is not set. Add it to your .env file.")
    if not settings.azure_openai_endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT is not set. Add it to your .env file.")
    if not settings.azure_openai_deployment_name:
        raise RuntimeError("AZURE_OPENAI_DEPLOYMENT_NAME is not set. Add it to your .env file.")

    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )
    response = client.chat.completions.create(
        model=settings.azure_openai_deployment_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content
