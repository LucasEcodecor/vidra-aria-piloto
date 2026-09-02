from decimal import Decimal, ROUND_HALF_UP


def calcular_item(
    largura_mm: float,
    altura_mm: float,
    quantidade: int,
    preco_m2: float,
) -> dict[str, float]:
    """Calcula área e valor de uma linha do orçamento."""
    area = (
        Decimal(str(largura_mm))
        * Decimal(str(altura_mm))
        / Decimal("1000000")
        * Decimal(str(quantidade))
    )
    valor = area * Decimal(str(preco_m2))
    return {
        "area_m2": float(area.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)),
        "valor_item": float(valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    }


def moeda(valor: float) -> str:
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")

