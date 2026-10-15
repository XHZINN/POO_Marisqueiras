"""Ficha de origem do lote (extensão além de P2).

Fica no produto, representando o lote à venda agora, e é copiada para o item
na compra. Mesma lógica de RN07 com o preço: lote novo amanhã não reescreve
o pedido de hoje.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dominio.coordenada import Coordenada
from dominio.enums import MetodoColeta
from dominio.excecoes import DadoObrigatorio


class Rastreabilidade:
    """Lote, data, local e responsável pela coleta."""

    # Marisco fresco tem janela curta. Serve de alerta na ficha, não bloqueia
    # venda: quem decide o prazo comercial é a marisqueira.
    VALIDADE_SUGERIDA_DIAS = 5

    def __init__(
        self,
        lote: str,
        data_coleta: date,
        local_coleta: str,
        responsavel: str,
        metodo: MetodoColeta = MetodoColeta.CATACAO_MANUAL,
        coordenada: Coordenada | None = None,
        observacoes: str | None = None,
        id: int | None = None,
    ) -> None:
        if not lote or not lote.strip():
            raise DadoObrigatorio("O lote é obrigatório na ficha de origem.")
        if data_coleta is None:
            raise DadoObrigatorio("A data de coleta é obrigatória.")
        if data_coleta > date.today():
            raise DadoObrigatorio("A data de coleta não pode estar no futuro.")
        if not local_coleta or not local_coleta.strip():
            raise DadoObrigatorio("O local de coleta é obrigatório.")
        if not responsavel or not responsavel.strip():
            raise DadoObrigatorio("O responsável pela coleta é obrigatório.")
        if not isinstance(metodo, MetodoColeta):
            raise DadoObrigatorio("O método de coleta é obrigatório.")

        self.id = id
        self.lote = lote.strip().upper()
        self.data_coleta = data_coleta
        self.local_coleta = local_coleta.strip()
        self.responsavel = responsavel.strip()
        self.metodo = metodo
        self.coordenada = coordenada
        self.observacoes = (observacoes or "").strip() or None

    def copiar(self) -> Rastreabilidade:
        """Cópia para congelar no item do pedido, sem o id do original."""
        return Rastreabilidade(
            lote=self.lote,
            data_coleta=self.data_coleta,
            local_coleta=self.local_coleta,
            responsavel=self.responsavel,
            metodo=self.metodo,
            coordenada=self.coordenada,
            observacoes=self.observacoes,
        )

    @property
    def idade_em_dias(self) -> int:
        return (date.today() - self.data_coleta).days

    @property
    def dentro_da_validade_sugerida(self) -> bool:
        return self.idade_em_dias <= self.VALIDADE_SUGERIDA_DIAS

    def distancia_de(self, origem: Coordenada | None) -> Decimal | None:
        """Quanto o lote viajou do ponto de coleta até `origem`."""
        if self.coordenada is None or origem is None:
            return None
        return self.coordenada.distancia_km(origem)

    def resumo(self) -> str:
        """Linha única para tabela e tooltip."""
        return (
            f"Lote {self.lote} · coletado em {self.data_coleta:%d/%m/%Y} "
            f"({self.idade_em_dias}d) · {self.local_coleta} · "
            f"{self.metodo.rotulo} · {self.responsavel}"
        )

    def __repr__(self) -> str:
        return f"<Rastreabilidade {self.lote} {self.data_coleta:%d/%m/%Y}>"
