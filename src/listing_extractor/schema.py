"""The output field schema, kept in its own module to avoid import cycles."""

from __future__ import annotations

# Output columns, in order.
FIELDNAMES = [
    "listing_url",
    "address_full",
    "suburb",
    "state",
    "postcode",
    "price_text",
    "price_value",
    "property_type",
    "bedrooms",
    "bathrooms",
    "car_spaces",
    "land_size",
    "description",
    "agent_name",
    "agency_name",
    "listing_date",
    "image_urls",
]

# A row is valid only when all of these are present.
REQUIRED_FIELDS = [
    "listing_url",
    "suburb",
    "state",
    "postcode",
    "price_text",
    "property_type",
]
