"""Configurazione letta dalle variabili d'ambiente (in locale arrivano da .env via docker compose)."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Radice del progetto: /app nel container, la cartella del repo in locale.
PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    model_agent: str
    model_deep: str
    model_riserva: str
    data_dir: Path
    llm_prova: bool = False    # modello di prova deterministico (vice/llm_prova.py), solo per le prove dell'interfaccia

    @property
    def raw_dir(self) -> Path:
        """Dati scaricati dalle fonti: gitignored, mai serviti dall'app."""
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        """Risultati piccoli usati dall'app: tracciati in git."""
        return self.data_dir / "processed"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        llm_base_url=os.environ.get("VICE_LLM_BASE_URL", "https://hydrogen.ht-x.com").rstrip("/"),
        llm_api_key=os.environ.get("VICE_LLM_API_KEY", ""),
        model_agent=os.environ.get("VICE_MODEL_AGENT", "HTX-EU-Claude-Sonnet-5"),
        model_deep=os.environ.get("VICE_MODEL_DEEP", "HTX-EU-Claude-Opus-5.5"),
        model_riserva=os.environ.get("VICE_MODEL_RISERVA", "HTX-EU-Claude-Sonnet-4.6"),
        data_dir=Path(os.environ.get("VICE_DATA_DIR") or PROJECT_DIR / "data"),
        llm_prova=os.environ.get("VICE_LLM_PROVA", "") == "1",
    )
