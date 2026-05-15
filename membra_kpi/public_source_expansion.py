"""Expanded public-source catalog for MEMBRA KPI.

This module adds a broad, high-density public-data source catalog for MEMBRA's
backend enrichment layer. It focuses on free, open, public, or public-interest
sources that can improve local-commerce underwriting, buyer discovery,
compliance review, research-grade narratives, proof context, and investor-room
reporting.

No live external requests are executed here. This is adapter-ready metadata for
future provider workers, queues, and endpoint mounting.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .value_api_bundle import value_density_report


@dataclass(frozen=True, slots=True)
class PublicSource:
    source_id: str
    name: str
    category: str
    access_model: str
    endpoint_family: str
    api_key_required: bool
    value_density: int
    integration_difficulty: int
    memebra_outputs: list[str]
    best_worker: str
    notes: str


PUBLIC_SOURCES: list[PublicSource] = [
    PublicSource("osm_overpass", "OpenStreetMap Overpass", "geospatial_poi", "free_public", "overpass_query", False, 98, 35, ["nearby_pois", "buyer_categories", "street_context", "foot_traffic_proxy"], "buyer_discovery", "Respect public server limits; cache results."),
    PublicSource("overture_places", "Overture Maps Places", "geospatial_places", "open_dataset", "parquet_dataset", False, 97, 65, ["places", "business_density", "building_context"], "map_context_worker", "Heavy but very high-value open map data."),
    PublicSource("nominatim", "Nominatim", "geocoding", "free_with_policy", "geocode_reverse_geocode", False, 86, 25, ["approx_location", "address_context"], "map_context_worker", "Use politely and cache."),
    PublicSource("geonames", "GeoNames", "geography", "free_account", "places_admin_geography", True, 78, 30, ["place_names", "admin_regions", "country_context"], "map_context_worker", "Useful global place fallback."),
    PublicSource("natural_earth", "Natural Earth", "geospatial_basemap", "open_dataset", "shapefiles", False, 72, 40, ["country_region_boundaries", "map_layers"], "map_context_worker", "Good static global basemap data."),
    PublicSource("us_census", "US Census API", "demographics", "free_optional_key", "census_data", False, 96, 40, ["income", "housing", "population", "commute", "neighborhood_score"], "underwriting_analyst", "Core US underwriting source."),
    PublicSource("acs", "American Community Survey", "demographics", "free_optional_key", "census_acs", False, 95, 45, ["renter_density", "income", "education", "commute"], "underwriting_analyst", "Best neighborhood-level US demographic dataset."),
    PublicSource("data_commons", "Google Data Commons", "public_stats_graph", "free_key", "statistical_graph", True, 94, 35, ["city_context", "economic_context", "public_stats"], "underwriting_analyst", "High-density public-stat graph."),
    PublicSource("world_bank", "World Bank Open Data", "global_macro", "free", "world_bank_indicators", False, 82, 30, ["country_macro", "international_context"], "investor_memo", "Good for global expansion context."),
    PublicSource("oecd", "OECD Data", "global_macro", "free", "oecd_data", False, 78, 45, ["labor", "economy", "policy_context"], "investor_memo", "Useful for developed-market context."),
    PublicSource("fred", "FRED", "macro_economic", "free_key", "economic_series", True, 92, 25, ["rates", "inflation", "real_estate_context"], "investor_memo", "Fast, high-signal macro context."),
    PublicSource("bea", "BEA", "regional_economic", "free_key", "bea_data", True, 86, 35, ["regional_gdp", "income", "industry_context"], "underwriting_analyst", "Good for regional economic density."),
    PublicSource("bls", "BLS Public API", "labor_economic", "free_optional_key", "labor_series", False, 87, 35, ["wages", "employment", "inflation"], "underwriting_analyst", "Useful for local labor and wage context."),
    PublicSource("sec_edgar", "SEC EDGAR", "company_filings", "free", "company_filings", False, 88, 35, ["company_context", "b2b_targets", "investor_room"], "buyer_discovery", "Use SEC-compliant user agent and rate limits."),
    PublicSource("open_corporates", "OpenCorporates", "company_registry", "limited_free", "company_search", True, 80, 45, ["entity_context", "company_verification"], "buyer_discovery", "Free tier may be limited."),
    PublicSource("sam_gov", "SAM.gov Entity/Contract Data", "government_procurement", "free_key", "entity_contract_data", True, 84, 55, ["vendor_context", "public_contracting", "buyer_discovery"], "buyer_discovery", "High-value public procurement source; API key required."),
    PublicSource("usaspending", "USAspending.gov", "government_spending", "free", "federal_awards", False, 82, 45, ["grant_awards", "contract_awards", "public_money_context"], "investor_memo", "Useful for institutional buyer/procurement context."),
    PublicSource("grants_gov", "Grants.gov", "grants", "free", "grant_opportunities", False, 76, 45, ["grant_opportunities", "public_funding_context"], "research_analyst", "Can enrich public/private funding strategies."),
    PublicSource("open_sanctions", "OpenSanctions", "compliance", "open_data", "sanctions_pep_entities", False, 91, 45, ["entity_risk", "compliance_flags"], "proof_reviewer", "Human review required for matches."),
    PublicSource("ofac", "OFAC Sanctions Lists", "compliance", "free_public", "sanctions_lists", False, 89, 45, ["sanctions_screening", "payout_controls"], "proof_reviewer", "Exact/entity matching requires care."),
    PublicSource("eu_sanctions", "EU Sanctions Map/Data", "compliance", "public", "sanctions_lists", False, 82, 50, ["international_compliance_flags"], "proof_reviewer", "Useful for global compliance context."),
    PublicSource("openownership", "OpenOwnership Register", "beneficial_ownership", "open_data", "beneficial_ownership", False, 77, 55, ["ownership_context", "entity_risk"], "proof_reviewer", "Coverage varies by jurisdiction."),
    PublicSource("noaa_nws", "NOAA / National Weather Service", "weather", "free", "weather_alerts_forecast", False, 85, 25, ["weather_risk", "campaign_timing", "proof_context"], "underwriting_analyst", "No key required for many endpoints."),
    PublicSource("open_meteo", "Open-Meteo", "weather", "free", "forecast_archive", False, 84, 15, ["forecast", "seasonality", "weather_score"], "underwriting_analyst", "Very easy weather integration."),
    PublicSource("nasa_power", "NASA POWER", "climate_weather", "free", "climate_solar_meteorology", False, 76, 35, ["climate_context", "seasonality"], "underwriting_analyst", "Good for climate/seasonality context."),
    PublicSource("usgs", "USGS APIs", "geology_hazard", "free", "hazards_elevation_land", False, 72, 45, ["hazard_context", "land_context"], "proof_reviewer", "Useful for location risk context."),
    PublicSource("epa_envirofacts", "EPA Envirofacts", "environment", "free", "environmental_records", False, 74, 45, ["environmental_risk", "site_context"], "proof_reviewer", "Environmental context for physical locations."),
    PublicSource("openaq", "OpenAQ", "air_quality", "free", "air_quality_measurements", False, 70, 30, ["air_quality", "environmental_score"], "underwriting_analyst", "Useful environmental context."),
    PublicSource("gtfs_feeds", "Public GTFS Feeds", "transit", "free_open_data", "gtfs_static_realtime", False, 83, 55, ["transit_proximity", "commute_flow", "foot_traffic_proxy"], "map_context_worker", "Agency-specific feeds; strong local value."),
    PublicSource("transitland", "Transitland", "transit", "free_tier_open", "transit_feeds", False, 79, 40, ["transit_stops", "routes", "mobility_context"], "map_context_worker", "Useful global transit abstraction."),
    PublicSource("gbfs", "GBFS Bike/Scooter Feeds", "mobility", "free_open_data", "shared_mobility_feeds", False, 72, 35, ["mobility_density", "street_activity_proxy"], "map_context_worker", "City-specific mobility context."),
    PublicSource("eventbrite", "Eventbrite API", "events", "free_dev", "events_search", True, 72, 40, ["local_events", "activation_timing"], "buyer_discovery", "Free access varies by app status."),
    PublicSource("gdelt", "GDELT", "news_events", "free", "global_news_events", False, 80, 45, ["local_news", "event_context", "trend_context"], "research_analyst", "High-volume global news/event context."),
    PublicSource("wikidata", "Wikidata SPARQL", "knowledge_graph", "free", "sparql", False, 82, 40, ["landmarks", "entities", "public_place_context"], "research_analyst", "Great explainable public graph."),
    PublicSource("wikipedia", "Wikipedia/Wikimedia APIs", "knowledge", "free", "page_summary_media", False, 72, 25, ["landmark_context", "city_summary"], "research_analyst", "Good narrative context; cite and avoid overuse."),
    PublicSource("openalex", "OpenAlex", "research_graph", "free", "works_authors_institutions", False, 79, 30, ["research_moat", "papers", "institutions"], "research_analyst", "Excellent research graph."),
    PublicSource("crossref", "Crossref", "research_metadata", "free", "doi_metadata", False, 72, 30, ["citations", "research_context"], "research_analyst", "Good scholarly metadata."),
    PublicSource("semantic_scholar", "Semantic Scholar", "research_graph", "free_key_optional", "papers_recommendations", False, 78, 35, ["research_context", "prior_art"], "research_analyst", "Useful for AI/research tracking."),
    PublicSource("arxiv", "arXiv API", "research_preprints", "free", "atom_feed", False, 70, 25, ["preprints", "research_monitoring"], "research_analyst", "Useful research monitoring."),
    PublicSource("uspto", "USPTO Open Data", "patents", "free", "patent_data", False, 78, 55, ["patent_context", "defensibility", "prior_art"], "research_analyst", "High-value but heavier integration."),
    PublicSource("github_api", "GitHub API", "software_signal", "free_rate_limited", "repos_issues_commits", True, 74, 35, ["repo_signals", "developer_ecosystem", "partner_research"], "research_analyst", "Useful for ecosystem intelligence; auth raises limits."),
    PublicSource("common_crawl", "Common Crawl", "web_corpus", "open_data", "warc_index", False, 76, 80, ["local_web_mining", "business_web_presence"], "research_analyst", "Very powerful but heavy."),
    PublicSource("wayback_cdx", "Internet Archive CDX", "web_archive", "free", "archive_index", False, 70, 45, ["historical_web_context", "company_history"], "research_analyst", "Good for historical context."),
    PublicSource("defillama", "DeFiLlama", "crypto_public_data", "free", "defi_protocols_chains_prices", False, 72, 25, ["chain_context", "public_crypto_metrics"], "research_analyst", "Read-only public crypto context; no trading."),
    PublicSource("coingecko", "CoinGecko", "crypto_market_data", "free_limited", "crypto_prices_metadata", False, 70, 25, ["token_reference_prices", "market_context"], "research_analyst", "Public market context only."),
    PublicSource("solana_rpc_public", "Solana Public RPC Devnet", "web3_devnet", "free_public", "json_rpc", False, 74, 35, ["devnet_anchor_verify", "signature_lookup"], "proof_reviewer", "Devnet only for MEMBRA anchoring."),
]


def expanded_public_sources() -> list[dict[str, Any]]:
    return [asdict(source) for source in PUBLIC_SOURCES]


def sources_by_category() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for source in PUBLIC_SOURCES:
        grouped.setdefault(source.category, []).append(asdict(source))
    return grouped


def top_public_sources(min_value_density: int = 80) -> list[dict[str, Any]]:
    return [asdict(s) for s in sorted(PUBLIC_SOURCES, key=lambda x: x.value_density, reverse=True) if s.value_density >= min_value_density]


def public_source_bundles() -> list[dict[str, Any]]:
    return [
        {
            "bundle_id": "all_public_local_underwriting",
            "name": "All-Public Local Underwriting Bundle",
            "source_ids": ["osm_overpass", "overture_places", "nominatim", "us_census", "acs", "data_commons", "fred", "bls", "bea", "open_meteo", "noaa_nws"],
            "outputs": ["nearby context", "demographics", "income", "commute", "macro context", "weather risk", "foot traffic proxies"],
        },
        {
            "bundle_id": "public_buyer_discovery_bundle",
            "name": "Public Buyer Discovery Bundle",
            "source_ids": ["osm_overpass", "overture_places", "open_corporates", "sec_edgar", "sam_gov", "usaspending", "wikidata"],
            "outputs": ["buyer categories", "business targets", "company facts", "procurement context", "entity context"],
        },
        {
            "bundle_id": "public_compliance_risk_bundle",
            "name": "Public Compliance and Risk Bundle",
            "source_ids": ["open_sanctions", "ofac", "eu_sanctions", "openownership", "epa_envirofacts", "usgs", "openaq"],
            "outputs": ["entity flags", "ownership context", "environmental risk", "admin review notes"],
        },
        {
            "bundle_id": "public_research_moat_bundle",
            "name": "Public Research Moat Bundle",
            "source_ids": ["openalex", "crossref", "semantic_scholar", "arxiv", "uspto", "github_api", "common_crawl", "wayback_cdx"],
            "outputs": ["prior art", "research graph", "patent context", "software ecosystem", "historical web context"],
        },
        {
            "bundle_id": "public_mobility_activation_bundle",
            "name": "Public Mobility and Activation Bundle",
            "source_ids": ["gtfs_feeds", "transitland", "gbfs", "eventbrite", "gdelt", "open_meteo"],
            "outputs": ["transit proximity", "event timing", "street activity proxies", "seasonality", "local trend context"],
        },
    ]


def public_source_expansion_report() -> dict[str, Any]:
    sources = expanded_public_sources()
    return {
        "product": "MEMBRA expanded public source graph",
        "source_count": len(sources),
        "sources": sources,
        "by_category": sources_by_category(),
        "top_sources": top_public_sources(),
        "bundles": public_source_bundles(),
        "linked_existing_value_bundle": value_density_report()["recommended_first_bundle"],
        "safety": {
            "no_live_calls_in_catalog": True,
            "respect_api_terms": True,
            "cache_public_data": True,
            "human_review_for_compliance_matches": True,
            "no_private_data_scraping": True,
        },
    }


def build_public_source_enrichment_plan(*, listing: dict[str, Any], bundle_id: str = "all_public_local_underwriting") -> dict[str, Any]:
    bundles = {b["bundle_id"]: b for b in public_source_bundles()}
    bundle = bundles.get(bundle_id)
    if not bundle:
        raise ValueError(f"unknown public source bundle: {bundle_id}")
    seed = {"listing": listing, "bundle_id": bundle_id, "created_at": utc_now()}
    return {
        "plan_id": "pse_" + sha256_text(canonical_json(seed))[:24],
        "created_at": seed["created_at"],
        "bundle": bundle,
        "listing_context": listing,
        "source_execution_mode": "worker_queue_required_for_live_fetch",
        "output_contract": bundle["outputs"],
        "review_required": True,
    }


def record_public_source_plan(conn, context: BackendContext, plan: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "public_source_plan",
        plan["plan_id"],
        "public_source.enrichment_plan_created",
        plan,
    )


def create_public_source_enrichment_plan(conn, *, context: BackendContext, listing: dict[str, Any], bundle_id: str = "all_public_local_underwriting") -> dict[str, Any]:
    plan = build_public_source_enrichment_plan(listing=listing, bundle_id=bundle_id)
    event = record_public_source_plan(conn, context, plan)
    return {"success": True, "public_source_plan": plan, "proofbook_event": event}
