"""Models module."""

from dataclasses import dataclass


@dataclass
class Product:
    name: str
    price: float
    quantity: int = 0

    def total(self) -> float:
        return self.price * self.quantity


def create_product(name: str, price: float) -> Product:
    return Product(name=name, price=price)
