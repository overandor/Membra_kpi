"""language-fi integration primitives for MEMBRA KPI.

`language-fi` is treated as a localization and language-intelligence adapter
namespace. Repo `overandor/47` is registered as the current external repository
slot for language-fi experiments until a dedicated repo is promoted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class LanguageFiModule:
    module_name: str
    repository: str
    role: str
    status: str
    supported_locales: list[str]
    default_locale: str
    notes: str


def language_fi_module() -> LanguageFiModule:
    return LanguageFiModule(
        module_name="language-fi",
        repository="overandor/47",
        role="localization, multilingual listing copy, language-aware KPI descriptions, and translation adapter research",
        status="registered_external_repo_slot",
        supported_locales=["en", "fi", "es", "uk", "ru"],
        default_locale="en",
        notes="Registered as a safe adapter namespace. Production translation requires configured provider or deterministic templates.",
    )


def language_fi_status() -> dict[str, Any]:
    module = language_fi_module()
    return {
        **asdict(module),
        "capabilities": {
            "listing_copy_localization": True,
            "kpi_description_localization": True,
            "proofbook_event_label_localization": True,
            "deterministic_template_fallback": True,
            "external_provider_required_for_live_translation": True,
        },
        "safety": {
            "does_not_translate_legal_claims_as_certified": True,
            "does_not_claim_human_translation": True,
            "requires_review_for_public_marketplace_copy": True,
        },
    }


def localize_listing_stub(listing: dict[str, Any], locale: str = "fi") -> dict[str, Any]:
    """Deterministic non-certified localization placeholder.

    This intentionally avoids pretending that a live translation model ran.
    """
    title = str(listing.get("title", "MEMBRA listing"))
    description = str(listing.get("description", "Permissioned local-commerce inventory."))
    labels = {
        "fi": {
            "prefix": "MEMBRA-paikallislistaus",
            "estimate_notice": "Arvio ei ole taattu tulo.",
            "review_notice": "Vaatii omistajan ja ylläpidon tarkistuksen.",
        },
        "es": {
            "prefix": "Listado local MEMBRA",
            "estimate_notice": "La estimación no es ingreso garantizado.",
            "review_notice": "Requiere revisión del propietario y del operador.",
        },
    }.get(locale, {
        "prefix": "MEMBRA local listing",
        "estimate_notice": "Estimate is not guaranteed income.",
        "review_notice": "Requires owner and operator review.",
    })
    return {
        "locale": locale,
        "mode": "deterministic_template_fallback",
        "localized_title": f"{labels['prefix']}: {title}",
        "localized_description": f"{description}\n\n{labels['estimate_notice']} {labels['review_notice']}",
        "review_required": True,
    }
