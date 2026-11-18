"""
Réglages de l'application web (variables d'environnement préfixées WEBAPP_).

Trois modes d'accès, exclusifs :
- production : WEBAPP_ACCESS_AUD renseigné → jeton Cloudflare Access exigé partout ;
- développement : WEBAPP_DEV_USER renseigné (et pas d'AUD) → utilisateur simulé ;
- non configuré : ni l'un ni l'autre → les pages répondent 503, jamais ouvertes.
"""
from pathlib import Path
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class WebappSettings(BaseSettings):
    team_domain: str = "groupekarta.cloudflareaccess.com"
    access_aud: str = ""
    admins: Annotated[list[str], NoDecode] = []
    dev_user: str | None = None
    data_dir: Path = Path("data/webapp")
    registry_path: Path = Path("data/chassis_registry.db")
    default_taux: float = 596.302
    profile_path: Path = Path("profils/karta-transit.ini")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WEBAPP_",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )

    @field_validator("access_aud", mode="before")
    @classmethod
    def _strip_aud(cls, v):
        return (v or "").strip()

    @field_validator("dev_user", mode="before")
    @classmethod
    def _norm_dev_user(cls, v):
        if v is None:
            return None
        v = str(v).strip().lower()
        return v or None

    @field_validator("admins", mode="before")
    @classmethod
    def _split_admins(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            v = v.split(",")
        return [str(e).strip().lower() for e in v if str(e).strip()]

    @model_validator(mode="after")
    def _modes_exclusifs(self):
        if self.access_aud and self.dev_user:
            raise ValueError(
                "Configuration refusée : WEBAPP_DEV_USER (mode développement) ne peut pas "
                "coexister avec WEBAPP_ACCESS_AUD (authentification Cloudflare Access). "
                "Retirer WEBAPP_DEV_USER en production."
            )
        return self

    @property
    def mode(self) -> str:
        """'access', 'dev' ou 'non_configure'."""
        if self.access_aud:
            return "access"
        if self.dev_user:
            return "dev"
        return "non_configure"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "webapp.db"


settings = WebappSettings()


def get_settings() -> WebappSettings:
    """Réglages courants (lus à chaque appel pour permettre leur remplacement en test)."""
    return settings
