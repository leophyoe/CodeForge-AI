"""Utility functions."""
import json


def format_name(first: str, last: str) -> str:
    return f"{first} {last}"


def parse_json(data: str) -> dict:
    return json.loads(data)
