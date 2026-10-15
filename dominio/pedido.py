"""Pedido: a compra de uma empresa compradora junto a uma marisqueira.

Regras implementadas: RN13, RN14, RN15, RN16, RN17, RN18, RN22. Fluxo: P7.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from math import ceil
from typing import TYPE_CHECKING

from dominio.coordenada import Coordenada
from dominio.endereco import Endereco
from dominio.entrega import EventoEntrega
from dominio.enums import (
    FormaPagamento,
    StatusEntrega,
    StatusPagamento,
    StatusPedido,
)
from dominio.excecoes import (
    DadoObrigatorio,
    EmpresasDiferentesNoPedido,
    PedidoVazio,
    TransicaoInvalida,
)
from dominio.item_pedido import ItemPedido
from dominio.rota import VELOCIDADE_PADRAO_KMH, Rota

if TYPE_CHECKING:
    from dominio.empresa import EmpresaCompradora, EmpresaMarisqueira
    from dominio.produto import Produto


class Pedido:
    """Pedido B2B de uma compradora pra uma única marisqueira.

    RN13 (compradora, itens, endereço e prazo; pagamento fora do escopo por
    P27), RN14 (todos os itens da mesma marisqueira) e RN16 (sem valor mínimo
    em dinheiro).

    O prazo de RN13 não é digitado pela compradora. Ele sai da estimativa
    (preparo da marisqueira mais o tempo da rota) e só vira acordo quando a
    marisqueira aceita o pedido. Quem entrega é que sabe em quanto tempo
    consegue entregar; deixar a compradora pedir "amanhã" seria empurrar pra
    marisqueira um prazo que ela não tem como cumprir.
    """

    # Prazo usado quando não há como estimar: sem coordenada das duas pontas,
    # não dá pra calcular tempo de rota.
    PRAZO_PADRAO_DIAS = 2

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
        endereco_entrega: str | Endereco,
        tempo_entrega_dias: int | None = None,
        marisqueira: EmpresaMarisqueira | None = None,
        status: StatusPedido = StatusPedido.AGUARDANDO_ANALISE,
        status_entrega: StatusEntrega = StatusEntrega.NAO_INICIADA,
        forma_pagamento: FormaPagamento = FormaPagamento.PIX,
        status_pagamento: StatusPagamento = StatusPagamento.PENDENTE,
        coordenada_entrega: Coordenada | None = None,
        prazo_confirmado: bool = False,
        previsao_entrega: datetime | None = None,
        criado_em: datetime | None = None,
        id: int | None = None,
    ) -> None:
        # RN13: todos obrigatórios.
        if compradora is None:
            raise DadoObrigatorio("O perfil da empresa compradora é obrigatório.")

        # O endereço pode vir como texto ou como endereço salvo da compradora.
        # Vindo salvo, o pedido guarda uma cópia: editar o cadastro depois não
        # muda pra onde este pedido foi.
        endereco_salvo: Endereco | None = None
        if isinstance(endereco_entrega, Endereco):
            endereco_salvo = endereco_entrega.copiar()
            texto = endereco_salvo.linha
            coordenada_entrega = coordenada_entrega or endereco_salvo.coordenada
        else:
            texto = (endereco_entrega or "").strip()
        if not texto:
            raise DadoObrigatorio("O endereço de entrega é obrigatório.")

        if tempo_entrega_dias is not None and int(tempo_entrega_dias) <= 0:
            raise DadoObrigatorio("O tempo de entrega deve ser de pelo menos 1 dia.")

        self.id = id
        self.compradora = compradora
        self.endereco_entrega = texto
        self.endereco = endereco_salvo
        self.marisqueira = marisqueira
        self.status = status
        self.status_entrega = status_entrega
        self.criado_em = criado_em or datetime.now()
        self.itens: list[ItemPedido] = []
        self.motivo_rejeicao: str | None = None
        self.observacao_ajuste: str | None = None

        # Prazo: o informado, ou o padrão até a estimativa ficar disponível.
        self.tempo_entrega_dias = (
            int(tempo_entrega_dias)
            if tempo_entrega_dias is not None
            else self.PRAZO_PADRAO_DIAS
        )
        self.prazo_confirmado = bool(prazo_confirmado)
        self.previsao_entrega = previsao_entrega

        # Pagamento. Extensão além de P27, que o deixava fora do escopo.
        if not isinstance(forma_pagamento, FormaPagamento):
            raise DadoObrigatorio("Escolha uma forma de pagamento.")
        self.forma_pagamento = forma_pagamento
        self.status_pagamento = status_pagamento
        self.pago_em: datetime | None = None

        # Rastreamento. Extensão além de P10, que não previa tempo real.
        # Sem coordenada informada, usa a da compradora.
        self.coordenada_entrega = coordenada_entrega or getattr(
            compradora, "coordenada", None
        )
        self.eventos_entrega: list[EventoEntrega] = []
        # Traçado por ruas, quando alguém com acesso ao roteador informa.
        # O domínio não busca rota: isso é chamada de rede.
        self.rota: Rota | None = None

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

    def definir_prazo_entrega(
        self, dias: int | None = None, previsao: datetime | None = None
    ) -> None:
        """A marisqueira fecha o prazo, no aceite.

        Sem argumento, assume a estimativa que o próprio pedido calcula. É o
        contrário do que estava antes: o prazo passa a ser compromisso de quem
        entrega, não pedido de quem compra.

        Quando a empresa dá um número diferente do estimado, a data também
        muda. Guardar a estimativa antiga faria o pedido prometer sete dias e
        mostrar a data de amanhã, que é pior que não ter data nenhuma.
        """
        if dias is None:
            dias = self.prazo_estimado_dias
        if int(dias) <= 0:
            raise DadoObrigatorio("O prazo de entrega é de pelo menos 1 dia.")
        self.tempo_entrega_dias = int(dias)
        estimativa = self.previsao_estimada
        if previsao is not None:
            self.previsao_entrega = previsao
        elif estimativa is not None and int(dias) == self.prazo_estimado_dias:
            # O prazo bate com a conta: fica a estimativa, que é mais fina
            # porque sabe a hora do preparo e o tempo do trajeto.
            self.previsao_entrega = estimativa
        else:
            self.previsao_entrega = self.criado_em + timedelta(days=int(dias))
        self.prazo_confirmado = True

    def definir_rota(self, rota: Rota | None) -> None:
        """Guarda o traçado por ruas, que vem de fora do domínio."""
        self.rota = rota

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
        if novo is StatusEntrega.SAIU_PARA_ENTREGA and self.pagamento_pendente:
            raise TransicaoInvalida(
                f"O pagamento em {self.forma_pagamento.rotulo} precisa estar "
                "confirmado antes do despacho (situação atual: "
                f"'{self.status_pagamento.rotulo}')."
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

    def marcar_pagamento_informado(self) -> None:
        """A compradora diz que pagou. Ainda não vale como pago."""
        if self.status_pagamento is StatusPagamento.CONFIRMADO:
            raise TransicaoInvalida("Este pedido já está com pagamento confirmado.")
        if self.status is StatusPedido.CANCELADO:
            raise TransicaoInvalida("Pedido cancelado não recebe pagamento.")
        self.status_pagamento = StatusPagamento.INFORMADO

    def marcar_pagamento_confirmado(self) -> None:
        """A marisqueira confirma que o dinheiro entrou."""
        if self.status_pagamento is StatusPagamento.CONFIRMADO:
            raise TransicaoInvalida("Este pagamento já foi confirmado.")
        self.status_pagamento = StatusPagamento.CONFIRMADO
        self.pago_em = datetime.now()

    def registrar_evento_entrega(
        self, coordenada: Coordenada, descricao: str
    ) -> EventoEntrega:
        """Acrescenta uma posição ao trajeto.

        Só depois do despacho: antes disso não existe veículo na rua.
        """
        if self.status_entrega not in (
            StatusEntrega.SAIU_PARA_ENTREGA,
            StatusEntrega.ENTREGUE,
        ):
            raise TransicaoInvalida(
                "O trajeto só é registrado depois que o pedido sai para entrega."
            )
        evento = EventoEntrega(self, coordenada, descricao)
        self.eventos_entrega.append(evento)
        return evento

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

    @property
    def pagamento_pendente(self) -> bool:
        """Falta pagar antes do despacho?

        Só trava quando a forma é antecipada. Boleto a prazo sai antes de
        o dinheiro entrar, que é o combinado dele.
        """
        return (
            self.forma_pagamento.antecipado
            and self.status_pagamento is not StatusPagamento.CONFIRMADO
        )

    @property
    def horas_de_preparo(self) -> int:
        """Quanto a marisqueira leva pra separar o pedido."""
        if self.marisqueira is None:
            return 24
        return int(getattr(self.marisqueira, "prazo_preparo_horas", 24))

    @property
    def minutos_de_transito(self) -> int | None:
        """Tempo de deslocamento: da rota quando existe, da distância quando não.

        Com rota por ruas sai o número do roteador, que já conta o trânsito do
        trajeto real. Sem rota, divide a distância em linha reta pela
        velocidade média, que é uma conta otimista e está dito que é.
        """
        if self.rota is not None:
            return self.rota.duracao_minutos
        distancia = self.distancia_total_km
        if distancia is None:
            return None
        return max(1, int(distancia / Decimal(VELOCIDADE_PADRAO_KMH) * 60))

    @property
    def previsao_estimada(self) -> datetime | None:
        """Quando a mercadoria chega, somando preparo e deslocamento."""
        transito = self.minutos_de_transito
        if transito is None:
            return None
        return self.criado_em + timedelta(hours=self.horas_de_preparo, minutes=transito)

    @property
    def prazo_estimado_dias(self) -> int:
        """A estimativa em dias, que é o formato que RN13 pede."""
        previsao = self.previsao_estimada
        if previsao is None:
            return self.PRAZO_PADRAO_DIAS
        horas = (previsao - self.criado_em).total_seconds() / 3600
        return max(1, ceil(horas / 24))

    @property
    def previsao_para_mostrar(self) -> datetime | None:
        """A previsão acordada, ou a estimativa enquanto não houver acordo."""
        return self.previsao_entrega or self.previsao_estimada

    @property
    def resumo_prazo(self) -> str:
        """Uma linha dizendo o prazo e se ele já é compromisso.

        Enquanto a marisqueira não aceita, o prazo é conta desta classe e a
        tela precisa deixar isso claro: quem compra não escolhe a data.
        """
        previsao = self.previsao_para_mostrar
        if previsao is None:
            return f"Prazo de {self.tempo_entrega_dias} dia(s)"
        if self.prazo_confirmado:
            return f"Entrega até {previsao:%d/%m às %H:%M} (prazo confirmado)"
        return f"Previsão de {previsao:%d/%m às %H:%M} (a confirmar)"

    @property
    def coordenada_origem(self) -> Coordenada | None:
        return self.marisqueira.coordenada if self.marisqueira is not None else None

    @property
    def distancia_total_km(self) -> Decimal | None:
        """Extensão do trajeto.

        Com rota por ruas é a distância rodada; sem rota, a linha reta, que
        subestima qualquer percurso de verdade.
        """
        if self.rota is not None:
            return self.rota.distancia_km
        origem = self.coordenada_origem
        if origem is None:
            return None
        return origem.distancia_km(self.coordenada_entrega)

    @property
    def posicao_atual(self) -> Coordenada | None:
        """Onde a carga está.

        Entregue vale como estando no destino, mesmo sem trajeto registrado:
        o pedido chegou, independente de alguém ter marcado as posições.
        """
        if self.status is StatusPedido.ENTREGUE and self.coordenada_entrega:
            return self.coordenada_entrega
        if self.eventos_entrega:
            return self.eventos_entrega[-1].coordenada
        return self.coordenada_origem

    @property
    def distancia_restante_km(self) -> Decimal | None:
        """Quanto falta rodar. Pela rota quando há rota, senão em linha reta."""
        if self.rota is not None:
            falta = self.rota.extensao * (
                Decimal("1") - Decimal(str(round(self.fracao_percorrida, 4)))
            )
            return falta.quantize(Decimal("0.1"))
        posicao = self.posicao_atual
        if posicao is None:
            return None
        return posicao.distancia_km(self.coordenada_entrega)

    @property
    def minutos_restantes(self) -> int | None:
        """Quanto tempo falta, na proporção do que ainda não foi rodado."""
        transito = self.minutos_de_transito
        if transito is None:
            return None
        return max(0, int(transito * (1 - self.fracao_percorrida)))

    @property
    def fracao_percorrida(self) -> float:
        """Quanto da rota já foi andado, de 0 a 1.

        Com rota, projeta a última posição sobre o traçado: numa rota que faz
        volta, a distância que falta em linha reta não diz quanto já se andou.
        """
        if self.status is StatusPedido.ENTREGUE:
            return 1.0
        posicao = self.posicao_atual
        if posicao is None:
            return 0.0
        if self.rota is not None:
            return self.rota.fracao_de(posicao)
        total = self.distancia_total_km
        restante = self.distancia_restante_km
        if not total or total <= 0 or restante is None:
            return 0.0
        return float(max(Decimal("0"), total - restante) / total)

    @property
    def progresso_percentual(self) -> int:
        """Quanto do trajeto já foi andado, de 0 a 100."""
        return max(0, min(100, int(self.fracao_percorrida * 100)))

    @property
    def em_transito(self) -> bool:
        return self.status_entrega is StatusEntrega.SAIU_PARA_ENTREGA

    def __repr__(self) -> str:
        return (
            f"<Pedido #{self.id} {self.status.rotulo} "
            f"{len(self.itens)} item(ns) R${self.total}>"
        )
