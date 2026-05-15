"""High-dollar-density API bundle catalog for MEMBRA KPI.

The goal is to prioritize free or mostly-free public data sources that create
10x more underwriting, enrichment, compliance, and buyer-discovery value than a
normal standalone product feature.

This module is catalog-first and safe-by-default. It does not execute external
requests directly. Runtime routers can expose these bundles, then provider
workers can implement source-specific fetchers behind rate limits and API-key
checks.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DataProvider:
    provider_id: str
    name: str
    category: str
    free_tier: str
    dollar_density_score: int
    integration_effort_score: int
    memebra_use_case: str
    endpoint_family: str
    api_key_required: bool
    best_for: list[str]
    notes: str


# Scores are directional product-prioritization scores, not financial guarantees.
PROVIDERS: list[DataProvider] = [
    DataProvider("osm_overpass", "OpenStreetMap / Overpass", "geospatial", "free_with_usage_limits", 98, 35, "POI, storefront, road, transit, building and nearby-business context", "https://overpass-api.de/api/interpreter", False, ["nearby_businesses", "map_context", "buyer_discovery", "foot_traffic_proxy"], "Highest immediate MEMBRA value per dollar; respect public server limits or self-host."),
    DataProvider("overture_maps", "Overture Maps Foundation", "geospatial", "open_data", 96, 65, "Commercial-grade open places/buildings/transport base layer", "https://overturemaps.org/download/", False, ["places", "buildings", "transport", "map_enrichment"], "Very high data density; heavier integration because data is distributed as large datasets."),
    DataProvider("us_census", "US Census API", "demographic", "free", 95, 40, "Income, housing, renter/owner, commute, population and neighborhood scoring", "https://api.census.gov/data", False, ["underwriting", "neighborhood_score", "investor_room", "tenant_market"], "Best public source for US demographic underwriting."),
    DataProvider("data_commons", "Google Data Commons", "public_knowledge_graph", "free", 94, 35, "Unified public-stat graph for places, economy, population and social indicators", "https://api.datacommons.org", True, ["public_stats", "city_context", "economic_context", "dashboard_enrichment"], "High leverage because many public datasets normalize into one graph."),
    DataProvider("fred", "FRED", "macro_economic", "free_key", 92, 25, "Inflation, rates, real estate, retail and macro trend context", "https://api.stlouisfed.org/fred", True, ["macro_context", "investor_room", "pricing_context"], "Extremely easy integration and valuable investor context."),
    DataProvider("bls", "BLS Public Data API", "labor_economic", "free", 88, 35, "Local labor, wages, inflation and category economic context", "https://api.bls.gov/publicAPI", False, ["local_economy", "buyer_segments", "wage_context"], "Useful for B2B and local-market scoring."),
    DataProvider("bea", "BEA API", "regional_economic", "free_key", 86, 35, "Regional GDP, income and economic activity", "https://apps.bea.gov/api/data", True, ["regional_gdp", "income", "market_size"], "Good investor-room enhancer."),
    DataProvider("noaa_nws", "NOAA / National Weather Service", "weather", "free", 84, 25, "Weather and seasonal context for local campaign timing", "https://api.weather.gov", False, ["weather_risk", "seasonality", "campaign_timing"], "No key required; excellent for physical-world operations."),
    DataProvider("open_meteo", "Open-Meteo", "weather", "free", 83, 15, "Forecasts without API keys", "https://api.open-meteo.com", False, ["forecast", "weather_scoring", "campaign_timing"], "Fastest useful weather integration."),
    DataProvider("open_sanctions", "OpenSanctions", "compliance", "free_open_data", 90, 45, "Entity and counterparty risk screening", "https://www.opensanctions.org/datasets/", False, ["compliance", "entity_risk", "admin_review"], "High trust value; important for advertisers and payouts."),
    DataProvider("ofac", "OFAC Sanctions Lists", "compliance", "free", 89, 45, "US sanctions screening", "https://ofac.treasury.gov/sanctions-lists", False, ["compliance", "risk_review", "payout_controls"], "Must be handled carefully; exact matching plus human review."),
    DataProvider("wikidata", "Wikidata SPARQL", "knowledge_graph", "free", 82, 40, "Entity, landmark, place and company enrichment", "https://query.wikidata.org/sparql", False, ["landmarks", "entity_context", "research"], "Useful for explainable enrichment and public-place context."),
    DataProvider("openalex", "OpenAlex", "research", "free", 78, 30, "Research graph for moat, prior art, papers and institutions", "https://api.openalex.org", False, ["research_moat", "investor_room", "innovation_tracking"], "Good for research-grade positioning."),
    DataProvider("sec_edgar", "SEC EDGAR", "company_financial", "free", 86, 35, "Public company filings, advertiser/company intelligence and investor room", "https://data.sec.gov", False, ["company_research", "b2b_targeting", "investor_room"], "High-value B2B enrichment; must follow SEC fair-access policy."),
    DataProvider("open_corporates", "OpenCorporates", "company_registry", "limited_free", 80, 45, "Company lookup and business identity enrichment", "https://api.opencorporates.com", True, ["business_verification", "buyer_discovery", "entity_context"], "Useful but free tier may be constrained."),
    DataProvider("gtfs", "Public GTFS Transit Feeds", "transit", "free_open_data", 82, 55, "Transit stop/route proximity as foot-traffic proxy", "varies_by_agency", False, ["foot_traffic_proxy", "map_context", "commute_score"], "High value where local transit feeds are available."),
]


def list_providers() -> list[dict[str, Any]]:
    return [asdict(provider) for provider in PROVIDERS]


def provider_by_id(provider_id: str) -> dict[str, Any] | None:
    for provider in PROVIDERS:
        if provider.provider_id == provider_id:
            return asdict(provider)
    return None


def high_density_providers(min_score: int = 85) -> list[dict[str, Any]]:
    return [asdict(p) for p in sorted(PROVIDERS, key=lambda x: x.dollar_density_score, reverse=True) if p.dollar_density_score >= min_score]


def bundle_definitions() -> list[dict[str, Any]]:
    return [
        {
            "bundle_id": "membra_10x_local_underwriting",
            "name": "MEMBRA 10x Local Underwriting Bundle",
            "provider_ids": ["osm_overpass", "overture_maps", "us_census", "data_commons", "fred", "noaa_nws", "open_sanctions"],
            "purpose": "Turn a basic listing into a location-aware, risk-aware, buyer-aware underwriting record.",
            "expected_value_multiplier": "high",
            "outputs": ["nearby buyer categories", "neighborhood score", "economic context", "weather risk", "compliance flags", "map proof context"],
        },
        {
            "bundle_id": "buyer_discovery_bundle",
            "name": "Buyer Discovery and Pitch Target Bundle",
            "provider_ids": ["osm_overpass", "overture_maps", "open_corporates", "sec_edgar", "wikidata"],
            "purpose": "Discover nearby businesses, corporate targets, and explainable pitch categories.",
            "expected_value_multiplier": "medium_high",
            "outputs": ["nearby businesses", "company enrichment", "pitch categories", "entity context"],
        },
        {
            "bundle_id": "proof_and_compliance_bundle",
            "name": "Proof, Risk and Compliance Bundle",
            "provider_ids": ["open_sanctions", "ofac", "wikidata", "us_census", "noaa_nws"],
            "purpose": "Add trust, risk context, public facts and review triggers around monetizable inventory.",
            "expected_value_multiplier": "high",
            "outputs": ["risk flags", "sanctions review", "public context", "weather proof context", "admin review notes"],
        },
        {
            "bundle_id": "investor_room_enrichment_bundle",
            "name": "Investor Room Data Density Bundle",
            "provider_ids": ["fred", "bea", "bls", "data_commons", "sec_edgar", "openalex"],
            "purpose": "Create investor-grade context from macro, company, labor and research sources.",
            "expected_value_multiplier": "medium_high",
            "outputs": ["market thesis", "macro context", "regional economy", "research moat", "company benchmarks"],
        },
    ]


def value_density_report() -> dict[str, Any]:
    providers = list_providers()
    bundles = bundle_definitions()
    top = high_density_providers(85)
    return {
        "method": "directional score: commercial usefulness per integration effort for MEMBRA KPI",
        "provider_count": len(providers),
        "top_provider_count": len(top),
        "providers": providers,
        "high_density": top,
        "bundles": bundles,
        "recommended_first_bundle": bundles[0],
        "safety": {
            "no_secret_storage": True,
            "respect_rate_limits": True,
            "no_scraping_claims": True,
            "external_calls_should_use_worker_queue": True,
            "human_review_for_compliance_flags": True,
        },
    }


def listing_enrichment_plan(listing: dict[str, Any]) -> dict[str, Any]:
    city = listing.get("city") or listing.get("location_hint") or "unknown"
    title = listing.get("title") or listing.get("detected_name") or "MEMBRA listing"
    return {
        "listing_title": title,
        "city_or_location_hint": city,
        "recommended_bundle": "membra_10x_local_underwriting",
        "provider_sequence": ["osm_overpass", "us_census", "data_commons", "noaa_nws", "open_sanctions"],
        "enrichment_targets": {
            "nearby_businesses": "Use OSM/Overture to identify pitch targets near the listing.",
            "neighborhood_underwriting": "Use Census/Data Commons to add demographic and economic context.",
            "seasonality": "Use NOAA/Open-Meteo for weather and campaign timing context.",
            "risk_review": "Use OpenSanctions/OFAC for entity review where buyer or payout identity is known.",
        },
        "output_columns": [
            "nearby_business_types",
            "recommended_buyer_categories",
            "neighborhood_score",
            "economic_context_summary",
            "weather_risk_summary",
            "compliance_review_flags",
            "data_density_score",
        ],
    }
