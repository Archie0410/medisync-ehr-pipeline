import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class AxxessConfig:
    url: str = ""
    email: str = ""
    password: str = ""
    agency_name: str = ""


@dataclass
class ChromeConfig:
    download_dir: str = "./downloads"
    headless: bool = False


@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff_seconds: int = 5


@dataclass
class RPAConfig:
    backend_url: str = "http://localhost:8000/api/v1"
    api_key: str = ""
    rpa_name: str = "MediSync-RPA"
    max_patients: int | None = None
    axxess: AxxessConfig = field(default_factory=AxxessConfig)
    chrome: ChromeConfig = field(default_factory=ChromeConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)


def load_config(path: str = "config.json") -> RPAConfig:
    raw = json.loads(Path(path).read_text())
    return RPAConfig(
        backend_url=raw.get("backend_url", ""),
        api_key=raw.get("api_key", ""),
        rpa_name=raw.get("rpa_name", "MediSync-RPA"),
        max_patients=raw.get("max_patients"),
        axxess=AxxessConfig(**raw.get("axxess", {})),
        chrome=ChromeConfig(**raw.get("chrome", {})),
        retry=RetryConfig(**raw.get("retry", {})),
    )
