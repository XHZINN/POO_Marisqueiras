"""ItemPedido: uma linha de pedido com um produto e a quantidade.

Regras implementadas: RN04, RN05, RN07, RN15, RN17, RN18.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from dominio.excecoes import QuantidadeIndisponivel, QuantidadeInvalida
from dominio.rastreabilidade import Rastreabilidade

if TYPE_CHECKING:
    from dominio.produto import Produto


class ItemPedido:
    """Uma linha do pedido.

    RN07: o preço unitário é copiado na criação, não lido do produto. Se a
    marisqueira reajustar amanhã, o pedido de hoje não muda.
    """

    def __init__(
        self,
        produto: Produto,
        quantidade_kg: Decimal,
        preco_unitario: Decimal | None = None,
        origem: Rastreabilidade | None = None,
        id: int | None = None,
    ) -> None:
        self.id = id
        self.produto = produto
        self.quantidade_kg = Decimal(quantidade_kg)
        # RN07: cópia do preço vigente. O parâmetro existe para que o
        # repositório possa restaurar o preço histórico gravado no banco.
        self.preco_unitario = (
            Decimal(preco_unitario)
            if preco_unitario is not None
            else produto.preco_por_kg
        )

        # Mesma ideia de RN07 com o preço: congela o lote vendido. Se a
        # marisqueira cadastrar outro lote amanhã, este pedido não muda.
        if origem is not None:
            self.origem = origem
        elif produto.rastreabilidade is not None:
            self.origem = produto.rastreabilidade.copiar()
        else:
            self.origem = None

        self.validar_quantidade()

    # Métodos exigidos pela atividade

    def validar_quantidade(self) -> None:
        """RN05 / RN15: a quantidade mínima de 25 kg vale para CADA produto.

        RN15 é explícita: o mínimo é aplicado individualmente a cada item do
        pedido, não ao pedido somado. Um pedido de 20 kg de sururu + 20 kg de
        camarão é inválido, mesmo totalizando 40 kg.
        """
        minimo = self.produto.QUANTIDADE_MINIMA_KG
        if self.quantidade_kg < minimo:
            raise QuantidadeInvalida(
                f"A quantidade mínima de '{self.produto.nome}' é {minimo} kg "
                f"(solicitado: {self.quantidade_kg} kg)."
            )

    def verificar_disponibilidade(self) -> bool:
        """RN17 / RN18: esta linha cabe no estoque do seu próprio produto?

        Diferente de `Produto.verificar_disponibilidade`, que responde sobre
        uma quantidade arbitrária, este método pergunta sobre a quantidade
        desta linha específica. Continua sendo uma consulta: retorna `bool`.
        """
        return self.produto.verificar_disponibilidade(self.quantidade_kg)

    # Métodos complementares

    def exigir_disponibilidade(self) -> None:
        """RN18: versão imperativa: recusa a linha e informa o estoque real."""
        if not self.verificar_disponibilidade():
            raise QuantidadeIndisponivel(
                self.produto.nome,
                self.quantidade_kg,
                self.produto.quantidade_disponivel_kg,
            )

    @property
    def subtotal(self) -> Decimal:
        """RN04 / RN23: quantidade x preço do kg. O frete já está no preço."""
        return (self.quantidade_kg * self.preco_unitario).quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return (
            f"<ItemPedido {self.produto.nome!r} {self.quantidade_kg}kg "
            f"x R${self.preco_unitario} = R${self.subtotal}>"
        )
