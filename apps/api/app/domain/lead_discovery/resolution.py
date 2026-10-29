"""Entity resolution, domain canonicalization, and deduplication algorithms."""

from __future__ import annotations

import difflib
import re
from typing import Any
from urllib.parse import urlparse

from app.domain.lead_discovery.models import LeadMatchConfidence

# Common corporate legal suffixes to strip during normalization
_LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "co",
    "company",
    "gmbh",
    "pvt",
    "sa",
    "se",
    "kg",
    "plc",
    "holdings",
}

_COMMON_SUBDOMAINS = {"www", "app", "portal", "dev", "sub", "mail", "api", "stage"}


def canonicalize_domain(url_or_domain: str) -> str:
    """Extract clean base domain from a URL or raw domain string."""
    text = url_or_domain.strip().lower()
    if not text:
        return ""

    if not text.startswith(("http://", "https://")):
        # Ensure scheme for urlparse if not present
        parsed = urlparse(f"https://{text}")
    else:
        parsed = urlparse(text)

    host = parsed.netloc or parsed.path
    # Strip port if present
    host = host.split(":", 1)[0]
    # Strip any trailing path or query if urlparse put it in netloc
    host = host.split("/", 1)[0].split("?", 1)[0].strip()

    parts = host.split(".")
    # If 3 or more parts, strip known generic subdomains like www, app, sub, dev
    while len(parts) > 2 and parts[0] in _COMMON_SUBDOMAINS:
        parts.pop(0)

    return ".".join(parts)


def normalize_company_name(name: str) -> str:
    """Normalize company name by stripping legal suffixes and punctuation."""
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [t.strip() for t in cleaned.split() if t.strip()]

    # Strip legal suffixes from tokens
    filtered_tokens: list[str] = []
    for token in tokens:
        if token in _LEGAL_SUFFIXES:
            continue
        filtered_tokens.append(token)

    result = " ".join(filtered_tokens).strip()
    return result or name.lower().strip()


def fuzzy_company_similarity(name_a: str, name_b: str) -> float:
    """Calculate similarity score (0.0 - 1.0) between two company names."""
    norm_a = normalize_company_name(name_a)
    norm_b = normalize_company_name(name_b)

    if norm_a == norm_b:
        return 1.0

    # Sequence matcher ratio
    seq_ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()

    # Jaccard token overlap
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    jaccard = len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)

    return max(seq_ratio, jaccard)


def resolve_lead_entity(
    domain: str,
    company_name: str,
    existing_accounts: list[dict[str, Any]],
    existing_contacts: list[dict[str, Any]],
) -> tuple[LeadMatchConfidence, dict[str, Any] | None]:
    """Resolve a discovered company/lead against existing CRM accounts and contacts."""
    lead_domain = canonicalize_domain(domain)

    # 1. Exact domain match against existing accounts
    for account in existing_accounts:
        acc_domain = canonicalize_domain(str(account.get("domain") or ""))
        if acc_domain and acc_domain == lead_domain:
            return LeadMatchConfidence.EXACT_MATCH, account

    # 2. Exact domain match against existing contacts
    for contact in existing_contacts:
        email = str(contact.get("email") or "").lower()
        if "@" in email:
            contact_domain = canonicalize_domain(email.split("@", 1)[1])
            if contact_domain and contact_domain == lead_domain:
                account_id = contact.get("account_id")
                matching_acc = next((a for a in existing_accounts if a.get("id") == account_id), None)
                return LeadMatchConfidence.EXACT_MATCH, matching_acc or {"id": account_id}

    # 3. Fuzzy company name match
    best_sim = 0.0
    best_acc: dict[str, Any] | None = None
    for account in existing_accounts:
        acc_name = str(account.get("name") or "")
        sim = fuzzy_company_similarity(company_name, acc_name)
        if sim > best_sim:
            best_sim = sim
            best_acc = account

    if best_sim >= 0.85:
        return LeadMatchConfidence.HIGH_CONFIDENCE_FUZZY, best_acc
    elif best_sim >= 0.65:
        return LeadMatchConfidence.AMBIGUOUS_CONFLICT, best_acc

    return LeadMatchConfidence.NEW_ENTITY, None
