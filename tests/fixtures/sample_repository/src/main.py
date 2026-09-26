"""Sample Python module for testing."""

from typing import Optional


class User:
    """A user model."""

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def save(self) -> bool:
        return True

    async def fetch(self) -> Optional["User"]:
        return None


def calculate(x: int, y: int) -> int:
    return x + y


def helper():
    pass
