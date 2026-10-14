"""Avaliacao: nota em estrelas dada pela compradora à marisqueira.

Regras implementadas: RN21, P23, P24.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from dominio.excecoes import AvaliacaoInvalida

if TYPE_CHECKING:
    from dominio.pedido import Pedido


class Avaliacao:
    """Nota que a compradora dá pra marisqueira depois da compra.

    P23 (quem avalia é a compradora), P24 (1 a 5 estrelas) e RN21 (só depois
    da entrega). Aponta pro pedido e não só pra empresa, pra garantir uma
    avaliação por compra.
    """

    NOTA_MINIMA = 1
    NOTA_MAXIMA = 5

    def __init__(
        self,
        pedido: Pedido,
        nota: int,
        comentario: str | None = None,
        criado_em: datetime | None = None,
        id: int | None = None,
    ) -> None:
        self.id = id
        self.pedido = pedido
        self.comentario = (comentario or "").strip() or None
        self.criado_em = criado_em or datetime.now()
        self.nota: int = 0
        # A validação vive num só lugar: o próprio registrar_nota.
        self.registrar_nota(nota)

    # Método exigido pela atividade

    def registrar_nota(self, nota: int) -> None:
        """RN21 / P24: grava a nota, validando a escala de 1 a 5 estrelas.

        É chamado pelo construtor e pode ser chamado de novo para corrigir
        uma nota. Concentrar a validação aqui evita que exista um caminho
        pelo qual uma nota inválida entre no objeto.
        """
        try:
            valor = int(nota)
        except (TypeError, ValueError):
            raise AvaliacaoInvalida(
                "A nota deve ser um número de 1 a 5 estrelas."
            ) from None

        if not self.NOTA_MINIMA <= valor <= self.NOTA_MAXIMA:
            raise AvaliacaoInvalida(
                f"A nota deve estar entre {self.NOTA_MINIMA} e "
                f"{self.NOTA_MAXIMA} estrelas (recebido: {valor})."
            )
        self.nota = valor

    # Consultas

    @property
    def marisqueira(self):
        """A empresa avaliada é a que vendeu no pedido."""
        return self.pedido.marisqueira

    @property
    def compradora(self):
        return self.pedido.compradora

    @property
    def estrelas(self) -> str:
        """Representação visual da nota para a interface."""
        return "★" * self.nota + "☆" * (self.NOTA_MAXIMA - self.nota)

    def __repr__(self) -> str:
        return f"<Avaliacao pedido#{self.pedido.id} {self.nota}/5>"
