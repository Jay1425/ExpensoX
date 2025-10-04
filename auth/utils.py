from __future__ import annotations

import logging
import random
import smtplib
import string
from email.message import EmailMessage
from functools import lru_cache
from typing import Dict, List, Tuple

import requests
from flask import current_app

REST_COUNTRIES_ENDPOINT = "https://restcountries.com/v3.1/all?fields=name,currencies"


def generate_otp(length: int = 6) -> str:

	return "".join(random.choices(string.digits, k=length))


class OTPDeliveryError(RuntimeError):
	"""Raised when an OTP email cannot be delivered."""


def send_otp_email(recipient: str, otp_code: str, purpose: str) -> None:

	subject = f"Your ExpensoX OTP for {purpose}"
	body = (
		f"Hi,\n\n"
		f"Use the following one-time password to complete {purpose}: {otp_code}.\n"
		f"This code expires in {current_app.config.get('OTP_EXPIRY_MINUTES', 5)} minutes.\n\n"
		"If you didn't request this code, you can ignore this message.\n"
		"\n— ExpensoX"
	)

	_send_via_smtp(recipient, subject, body)


def _send_via_smtp(recipient: str, subject: str, body: str) -> None:

	config = current_app.config
	server = config.get("SMTP_SERVER")
	username = config.get("SMTP_USERNAME")
	password = config.get("SMTP_PASSWORD")

	if not (server and username and password):
		raise OTPDeliveryError("SMTP credentials are not fully configured.")

	port = config.get("SMTP_PORT") or 587
	use_tls = config.get("SMTP_USE_TLS", True)
	from_email = config.get("SMTP_FROM_EMAIL") or username

	message = EmailMessage()
	message["Subject"] = subject
	message["From"] = from_email
	message["To"] = recipient
	message.set_content(body)

	try:
		with smtplib.SMTP(server, port, timeout=10) as smtp:
			if use_tls:
				smtp.starttls()
			smtp.login(username, password)
			smtp.send_message(message)
		current_app.logger.info("OTP email sent to %s via SMTP", recipient)
	except Exception as exc:  # pragma: no cover - network dependent
		current_app.logger.exception("Failed to send OTP email via SMTP")
		raise OTPDeliveryError(str(exc)) from exc


@lru_cache(maxsize=1)
def fetch_country_currency_map() -> Dict[str, str]:
	"""Fetch and cache mapping of country name to primary currency code."""

	default_currency = current_app.config.get("DEFAULT_CURRENCY", "USD")
	try:
		response = requests.get(REST_COUNTRIES_ENDPOINT, timeout=15)
		response.raise_for_status()
	except requests.RequestException as exc:  # pragma: no cover - network failure handling
		current_app.logger.warning("Failed to fetch country data: %s", exc)
		return {"United States": default_currency}

	country_currency: Dict[str, str] = {}
	for item in response.json():
		name_info = item.get("name", {})
		country_name = name_info.get("common") or name_info.get("official")
		currencies = item.get("currencies", {})
		currency_code = next(iter(currencies.keys()), default_currency)
		if country_name:
			country_currency[country_name] = currency_code

	if not country_currency:
		country_currency["United States"] = default_currency

	return dict(sorted(country_currency.items(), key=lambda kv: kv[0]))


def get_country_choices() -> List[Tuple[str, str]]:
	mapping = fetch_country_currency_map()
	return [(country, country) for country in mapping.keys()]


def get_currency_for_country(country: str) -> str:
	mapping = fetch_country_currency_map()
	return mapping.get(country) or current_app.config.get("DEFAULT_CURRENCY", "USD")
