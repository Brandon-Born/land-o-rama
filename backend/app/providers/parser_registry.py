from __future__ import annotations

from pathlib import Path
from typing import Literal, TypeGuard
from urllib.parse import urlparse

ParserTemplateKey = Literal[
    "csv_taxsale_v1",
    "pdf_taxsale_v1",
    "html_table_taxsale_v1",
    "lgbs_property_sales_v1",
]

SUPPORTED_PARSER_TEMPLATE_KEYS: tuple[ParserTemplateKey, ...] = (
    "csv_taxsale_v1",
    "pdf_taxsale_v1",
    "html_table_taxsale_v1",
    "lgbs_property_sales_v1",
)


def is_supported_parser_template_key(value: str) -> TypeGuard[ParserTemplateKey]:
    return value in SUPPORTED_PARSER_TEMPLATE_KEYS


def infer_parser_template_from_url(source_url: str) -> ParserTemplateKey:
    suffix = Path(urlparse(source_url).path).suffix.lower()
    if suffix == ".pdf":
        return "pdf_taxsale_v1"
    if suffix == ".csv":
        return "csv_taxsale_v1"
    if suffix == ".json":
        return "lgbs_property_sales_v1"
    return "html_table_taxsale_v1"
