"""Pedido: a compra de uma empresa compradora junto a uma marisqueira.

Regras implementadas: RN13, RN14, RN15, RN16, RN17, RN18, RN22. Fluxo: P7.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from dominio.enums import StatusEntrega, StatusPedido
from dominio.excecoes import (
    DadoObrigatorio,
    EmpresasDiferentesNoPedido,
    PedidoVazio,
    TransicaoInvalida,
)
from dominio.item_pedido import ItemPedido

if TYPE_CHECKING:
    from dominio.empresa import EmpresaCompradora, EmpresaMarisqueira
    from dominio.produto import Produto


class Pedido:
    """Pedido B2B de uma compradora pra uma única marisqueira.

    RN13 (compradora, itens, endereço e prazo; pagamento fora do escopo por
    P27), RN14 (todos os itens da mesma marisqueira) e RN16 (sem valor mínimo
    em dinheiro).
    """

    # P7: estados do pedido e pra onde cada um pode ir.
    # AJUSTE_SOLICITADO não vai direto pra ACEITO (depois do ajuste quem
    # decide é a compradora) e ACEITO não vai direto pra ENTREGUE (passa
    # pelo despacho da marisqueira antes da confirmação dela).
    TRANSICOES_PERMITIDAS: dict[StatusPedido, tuple[StatusPedido, ...]] = {
        StatusPedido.AGUARDANDO_ANALISE: (
            StatusPedido.ACEITO,
            StatusPedido.REJEITADO,
            StatusPedido.AJUSTE_SOLICITADO,
            StatusPedido.CANCELADO,
        ),
        StatusPedido.AJUSTE_SOLICITADO: (
            StatusPedido.AGUARDANDO_ANALISE,
            StatusPedido.REJEITADO,
            StatusPedido.CANCELADO,
        ),
        StatusPedido.ACEITO: (StatusPedido.EM_PREPARACAO,),
        StatusPedido.EM_PREPARACAO: (StatusPedido.ENTREGUE,),
        StatusPedido.REJEITADO: (),  # estado final
        StatusPedido.CANCELADO: (),  # estado final
        StatusPedido.ENTREGUE: (),  # estado final
    }

    def __init__(
        self,
        compradora: EmpresaCompradora,
        endereco_entrega: str,
        tempo_entrega_dias: int,
        marisqueira: EmpresaMarisqueira | None = None,
        status: StatusPedido = StatusPedido.AGUARDANDO_ANALISE,
        status_entrega: StatusEntrega = StatusEntrega.NAO_INICIADA,
        criado_em: datetime | None = None,
        id: int | None = None,
    ) -> None:
        # RN13: todos obrigatórios.
        if compradora is None:
            raise DadoObrigatorio("O perfil da empresa compradora é obrigatório.")
        if not endereco_entrega or not endereco_entrega.strip():
            raise DadoObrigatorio("O endereço de entrega é obrigatório.")
        if tempo_entrega_dias is None or int(tempo_entrega_dias) <= 0:
            raise DadoObrigatorio("O tempo de entrega deve ser de pelo menos 1 dia.")

        self.id = id
        self.compradora = compradora
        self.endereco_entrega = endereco_entrega.strip()
        self.tempo_entrega_dias = int(tempo_entrega_dias)
        self.marisqueira = marisqueira
        self.status = status
        self.status_entrega = status_entrega
        self.criado_em = criado_em or datetime.now()
        self.itens: list[ItemPedido] = []
        self.motivo_rejeicao: str | None = None
        self.observacao_ajuste: str | None = None

    # Métodos exigidos pela atividade

    def adicionar_item(
        self,
        produto: Produto,
        quantidade_kg: Decimal,
        preco_unitario: Decimal | None = None,
    ) -> ItemPedido:
        """RN14, RN15 e RN18: acrescenta um produto ao pedido.

        A ordem das validações importa: primeiro RN14 (o primeiro item define a
        marisqueira e os outros têm que bater), depois RN15 no ItemPedido, depois
        RN18. Item repetido do mesmo produto é somado em vez de duplicado, senão
        dava pra burlar RN15 com duas linhas de 15 kg.
        """
        if produto is None:
            raise DadoObrigatorio("O produto é obrigatório.")

        dono = produto.empresa

        # RN14: um pedido não reúne produtos de empresas diferentes.
        if self.marisqueira is None:
            self.marisqueira = dono
        elif dono is not None and dono is not self.marisqueira:
            raise EmpresasDiferentesNoPedido(
                f"Este pedido é da empresa '{self.marisqueira.nome}'. "
                f"O produto '{produto.nome}' pertence a '{dono.nome}'. "
                "Um pedido não pode reunir produtos de empresas diferentes. "
                "Faça um pedido separado."
            )

        existente = self._item_de(produto)
        if existente is not None:
            nova_quantidade = existente.quantidade_kg + Decimal(quantidade_kg)
            candidato = ItemPedido(produto, nova_quantidade, existente.preco_unitario)
            candidato.exigir_disponibilidade()  # RN18
            existente.quantidade_kg = nova_quantidade
            return existente

        item = ItemPedido(produto, quantidade_kg, preco_unitario)  # RN15 no construtor
        item.exigir_disponibilidade()  # RN18
        self.itens.append(item)
        return item

    # Máquina de estados (P7). a autorização de quem pode chamar cada uma

    def _mudar_status(self, novo: StatusPedido) -> None:
        permitidos = self.TRANSICOES_PERMITIDAS[self.status]
        if novo not in permitidos:
            raise TransicaoInvalida(
                f"Um pedido com status '{self.status.rotulo}' não pode passar "
                f"para '{novo.rotulo}'."
            )
        self.status = novo

    def marcar_aceito(self) -> None:
        """P7: a marisqueira aceita o pedido; o estoque é baixado (RN18)."""
        self._mudar_status(StatusPedido.ACEITO)
        for item in self.itens:
            item.produto.baixar_estoque(item.quantidade_kg)
        self.status_entrega = StatusEntrega.EM_PREPARACAO

    def marcar_rejeitado(self, motivo: str) -> None:
        """P7: a marisqueira rejeita o pedido, com justificativa."""
        if not motivo or not motivo.strip():
            raise DadoObrigatorio("Informe o motivo da rejeição.")
        self._mudar_status(StatusPedido.REJEITADO)
        self.motivo_rejeicao = motivo.strip()

    def marcar_ajuste_solicitado(self, observacao: str) -> None:
        """P7: a marisqueira devolve o pedido pedindo um ajuste."""
        if not observacao or not observacao.strip():
            raise DadoObrigatorio("Descreva o ajuste necessário.")
        self._mudar_status(StatusPedido.AJUSTE_SOLICITADO)
        self.observacao_ajuste = observacao.strip()

    def definir_status_entrega(self, novo: StatusEntrega) -> None:
        """RN22: a marisqueira informa o andamento da entrega que ela faz.

        Só depois do aceite. ENTREGUE não entra aqui: quem recebe a mercadoria é a
        compradora, então é ela que confirma, em `confirmar_recebimento`. É isso
        que também faz RN21 fazer sentido.
        """
        if self.status not in (StatusPedido.ACEITO, StatusPedido.EM_PREPARACAO):
            raise TransicaoInvalida(
                "O status da entrega só pode ser atualizado depois que o "
                f"pedido for aceito (status atual: '{self.status.rotulo}')."
            )
        if novo is StatusEntrega.ENTREGUE:
            raise TransicaoInvalida(
                "A entrega é confirmada pela empresa compradora, que é quem "
                "recebe a mercadoria. A marisqueira informa até "
                f"'{StatusEntrega.SAIU_PARA_ENTREGA.rotulo}'."
            )
        self.status_entrega = novo
        if (
            novo is StatusEntrega.SAIU_PARA_ENTREGA
            and self.status is StatusPedido.ACEITO
        ):
            self.status = StatusPedido.EM_PREPARACAO

    def confirmar_recebimento(self) -> None:
        """A compradora atesta que a mercadoria chegou.

        Exige que a marisqueira já tenha despachado: não se confirma o
        recebimento de algo que ainda não saiu.
        """
        if self.status_entrega is not StatusEntrega.SAIU_PARA_ENTREGA:
            raise TransicaoInvalida(
                "Só é possível confirmar o recebimento depois que a empresa "
                "das marisqueiras informar que o pedido saiu para entrega "
                f"(entrega atual: '{self.status_entrega.rotulo}')."
            )
        self._mudar_status(StatusPedido.ENTREGUE)
        self.status_entrega = StatusEntrega.ENTREGUE

    def marcar_cancelado(self) -> None:
        """A compradora desiste do pedido antes do aceite."""
        self._mudar_status(StatusPedido.CANCELADO)

    def reenviar_para_analise(self) -> None:
        """A compradora devolve o pedido ajustado para a marisqueira."""
        self._mudar_status(StatusPedido.AGUARDANDO_ANALISE)
        self.observacao_ajuste = None

    def substituir_itens(self, itens: list[tuple[Produto, Decimal]]) -> None:
        """Refaz a lista de itens, revalidando RN14, RN15 e RN18.

        Usado na resposta a um pedido de ajuste. Os itens antigos só são
        descartados depois que os novos passam por toda a validação, para
        que um ajuste inválido não deixe o pedido pela metade.
        """
        if not itens:
            raise PedidoVazio("O pedido precisa de pelo menos um produto.")

        anteriores = list(self.itens)
        self.itens = []
        try:
            for produto, quantidade in itens:
                self.adicionar_item(produto, quantidade)
            self.validar_para_envio()
        except Exception:
            self.itens = anteriores
            raise

    # Consultas

    def _item_de(self, produto: Produto) -> ItemPedido | None:
        for item in self.itens:
            if item.produto is produto or (
                produto.id is not None and item.produto.id == produto.id
            ):
                return item
        return None

    def validar_para_envio(self) -> None:
        """RN13 / RN15 / RN18: checagem final antes de submeter à marisqueira."""
        if not self.itens:
            raise PedidoVazio("Adicione pelo menos um produto ao pedido.")
        for item in self.itens:
            item.validar_quantidade()
            item.exigir_disponibilidade()

    @property
    def total(self) -> Decimal:
        """RN16 / RN23: soma dos subtotais. Sem mínimo financeiro; frete incluso."""
        return sum((item.subtotal for item in self.itens), Decimal("0.00"))

    @property
    def quantidade_total_kg(self) -> Decimal:
        return sum((item.quantidade_kg for item in self.itens), Decimal("0"))

    @property
    def pode_ser_avaliado(self) -> bool:
        """RN21: a avaliação só é liberada após a compra concluída."""
        return self.status is StatusPedido.ENTREGUE

    @property
    def aguarda_resposta_da_compradora(self) -> bool:
        """A marisqueira pediu ajuste e o pedido está parado com a compradora."""
        return self.status is StatusPedido.AJUSTE_SOLICITADO

    @property
    def pode_confirmar_recebimento(self) -> bool:
        return (
            self.status is StatusPedido.EM_PREPARACAO
            and self.status_entrega is StatusEntrega.SAIU_PARA_ENTREGA
        )

    @property
    def pode_ser_cancelado(self) -> bool:
        return StatusPedido.CANCELADO in self.TRANSICOES_PERMITIDAS[self.status]

    def __repr__(self) -> str:
        return (
            f"<Pedido #{self.id} {self.status.rotulo} "
            f"{len(self.itens)} item(ns) R${self.total}>"
        )
