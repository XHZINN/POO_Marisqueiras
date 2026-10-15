"""Coordenada geográfica (extensão além de P10).

A ordenação por proximidade de RN11 era comparação de texto. Com isto a
distância passa a ser calculada pela geodésica do geopy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from geopy.distance import geodesic

from dominio.excecoes import DadoObrigatorio


@dataclass(frozen=True)
class Coordenada:
    """Par latitude/longitude em graus decimais.

    É `frozen` porque coordenada é objeto de valor: não tem identidade
    própria e duas coordenadas iguais são a mesma coisa. Isso também evita
    alguém mudar a posição de uma empresa por acidente mexendo no objeto.
    """

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise DadoObrigatorio(
                f"Latitude fora da faixa válida: {self.latitude} (use -90 a 90)."
            )
        if not -180 <= self.longitude <= 180:
            raise DadoObrigatorio(
                f"Longitude fora da faixa válida: {self.longitude} (use -180 a 180)."
            )

    @property
    def par(self) -> tuple[float, float]:
        """Formato que o geopy espera."""
        return (self.latitude, self.longitude)

    def distancia_km(self, outra: Coordenada | None) -> Decimal | None:
        """Distância geodésica até `outra`, em km.

        Geodésica e não Haversine: usa o elipsoide da Terra em vez de assumir
        esfera. Decimal com uma casa para a ordenação não depender de
        arredondamento de float.
        """
        if outra is None:
            return None
        km = geodesic(self.par, outra.par).km
        return Decimal(str(round(km, 1)))

    def interpolar(self, destino: Coordenada, fracao: float) -> Coordenada:
        """Ponto a `fracao` do caminho entre esta coordenada e `destino`.

        Interpolação linear em lat/lon. Para poucos quilômetros a diferença
        em relação ao grande círculo não aparece. Move o entregador na
        simulação.
        """
        fracao = max(0.0, min(1.0, float(fracao)))
        return Coordenada(
            latitude=self.latitude + (destino.latitude - self.latitude) * fracao,
            longitude=self.longitude + (destino.longitude - self.longitude) * fracao,
        )

    def __str__(self) -> str:
        lado_ns = "N" if self.latitude >= 0 else "S"
        lado_lo = "L" if self.longitude >= 0 else "O"
        return f"{abs(self.latitude):.4f}{lado_ns} {abs(self.longitude):.4f}{lado_lo}"


# Pontos reais da região do projeto (P4: Vila Maresia, Raposa/MA).
RAPOSA = Coordenada(-2.4258, -44.0961)
VILA_MARESIA = Coordenada(-2.4301, -44.1012)
SAO_LUIS_CENTRO = Coordenada(-2.5307, -44.3068)
ARACAGI = Coordenada(-2.4833, -44.1667)
MERCADO_DO_PEIXE = Coordenada(-2.4289, -44.0918)
