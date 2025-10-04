"""Currency conversion and metadata helpers."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional

import requests

EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/{base}"
REST_COUNTRIES_URL = "https://restcountries.com/v3.1/all?fields=name,currencies"


def get_default_currency_for_country(country_name: str) -> Dict[str, Optional[str]]:
    """Return the default currency information for a given country."""
    try:
        response = requests.get(REST_COUNTRIES_URL, timeout=10)
        response.raise_for_status()
        countries = response.json()
    except requests.RequestException:
        return {"currency_code": None, "currency_name": None}

    target = next(
        (
            entry
            for entry in countries
            if entry.get("name", {}).get("common", "").lower() == country_name.lower()
        ),
        None,
    )

    if not target:
        return {"currency_code": None, "currency_name": None}

    currencies = target.get("currencies") or {}
    if not currencies:
        return {"currency_code": None, "currency_name": None}

    code, details = next(iter(currencies.items()))
    return {"currency_code": code, "currency_name": details.get("name")}


def fetch_exchange_rates(base_currency: str) -> Dict[str, float]:
    """Fetch exchange rates for the given base currency."""
    try:
        response = requests.get(EXCHANGE_API_URL.format(base=base_currency.upper()), timeout=10)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        return {}

    return payload.get("rates", {})


def convert_currency(amount: Decimal | float, source_currency: str, target_currency: str) -> Decimal:
    """Convert an amount between currencies using the exchangerate-api service."""
    if source_currency.upper() == target_currency.upper():
        return Decimal(amount)

    rates = fetch_exchange_rates(source_currency)
    rate = rates.get(target_currency.upper())
    if not rate:
        return Decimal(amount)

    quantized = Decimal(str(rate)) * Decimal(amount)
    return quantized.quantize(Decimal("0.01"))
