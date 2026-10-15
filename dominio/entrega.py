"""Posições do trajeto da entrega (extensão além de P10).

Append-only: a entrega não muda de lugar, ela acumula pontos. Guardar o
trajeto todo deixa conferir o percurso, não só onde a carga está agora.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from dominio.coordenada import Coordenada
from dominio.excecoes import DadoObrigatorio

if TYPE_CHECKING:
    from dominio.pedido import Pedido


class EventoEntrega:
    """Uma posição do veículo num instante do trajeto."""

    def __init__(
        self,
        pedido: Pedido,
        coordenada: Coordenada,
        descricao: str,
        registrado_em: datetime | None = None,
        id: int | None = None,
    ) -> None:
        if pedido is None:
            raise DadoObrigatorio("O evento precisa estar ligado a um pedido.")
        if coordenada is None:
            raise DadoObrigatorio("O evento precisa de uma coordenada.")
        if not descricao or not descricao.strip():
            raise DadoObrigatorio("Descreva o ponto do trajeto.")

        self.id = id
        self.pedido = pedido
        self.coordenada = coordenada
        self.descricao = descricao.strip()
        self.registrado_em = registrado_em or datetime.now()

    def distancia_ate(self, destino: Coordenada | None) -> Decimal | None:
        return self.coordenada.distancia_km(destino)

    def __repr__(self) -> str:
        return (
            f"<EventoEntrega {self.registrado_em:%d/%m %H:%M} "
            f"{self.coordenada} {self.descricao!r}>"
        )
