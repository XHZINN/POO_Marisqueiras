"""Empresa e suas duas subclasses.

    Empresa (abstrata)
    ├── EmpresaMarisqueira: oferta, analisa pedidos, entrega
    └── EmpresaCompradora: consulta, pede, avalia

RN01 (B2B), RN02 (1 habitação = 1 empresa) e RN03 (marisqueira pode ser
empresa sozinha). `consultar_produtos` é abstrato porque RN12 dá resposta
diferente pra cada uma, e polimorfismo resolve isso sem if de tipo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, time
from decimal import Decimal

from dominio.avaliacao import Avaliacao
from dominio.coordenada import Coordenada
from dominio.entrega import EventoEntrega
from dominio.enums import (
    Categoria,
    FormaPagamento,
    MetodoColeta,
    OrdenacaoBusca,
    SituacaoEmpresa,
    StatusEntrega,
    StatusPedido,
    TipoNotificacao,
)
from dominio.excecoes import (
    AcessoNaoAutorizado,
    AvaliacaoInvalida,
    DadoObrigatorio,
    PrecoAlteradoEmVenda,
    QuantidadeInvalida,
    TransicaoInvalida,
)
from dominio.notificacao import Notificacao
from dominio.pedido import Pedido
from dominio.produto import Produto
from dominio.rastreabilidade import Rastreabilidade


class Empresa(ABC):
    """Base abstrata das empresas. Concentra identidade e horário de funcionamento.

    É abstrata porque "empresa" não existe sozinha no negócio: toda empresa
    é marisqueira ou compradora, e as duas têm papéis incompatíveis. Marcar
    a classe como ABC impede que alguém instancie uma empresa sem papel.
    """

    def __init__(
        self,
        nome: str,
        cnpj: str,
        email: str,
        telefone: str,
        endereco: str,
        localizacao: str,
        abertura: time = time(7, 0),
        fechamento: time = time(18, 0),
        coordenada: Coordenada | None = None,
        id: int | None = None,
    ) -> None:
        for campo, valor in (
            ("nome", nome),
            ("CNPJ", cnpj),
            ("e-mail", email),
            ("telefone", telefone),
            ("endereço", endereco),
            ("localização", localizacao),
        ):
            if not valor or not str(valor).strip():
                raise DadoObrigatorio(f"O campo {campo} é obrigatório.")

        self.id = id
        self.nome = nome.strip()
        self.cnpj = cnpj.strip()
        self.email = email.strip()
        self.telefone = telefone.strip()
        self.endereco = endereco.strip()
        self.localizacao = localizacao.strip()
        self.abertura = abertura
        self.fechamento = fechamento
        # Posição real. Extensão além de P10, que não previa coordenadas.
        self.coordenada = coordenada
        self.notificacoes: list[Notificacao] = []

    # Contrato abstrato: toda subclasse é obrigada a responder

    @abstractmethod
    def tipo(self) -> str:
        """Papel da empresa na plataforma."""

    @abstractmethod
    def consultar_produtos(self, catalogo: list[Produto]) -> list[Produto]:
        """RN12: o que esta empresa pode ver do catálogo."""

    # Comum às duas

    def distancia_ate(self, outra: Empresa) -> Decimal | None:
        """Distância em km até outra empresa, quando as duas têm coordenada."""
        if self.coordenada is None:
            return None
        return self.coordenada.distancia_km(getattr(outra, "coordenada", None))

    def esta_em_horario_de_funcionamento(self, agora: datetime | None = None) -> bool:
        """RN20 / P33: base do indicador vermelho."""
        hora = (agora or datetime.now()).time()
        return self.abertura <= hora <= self.fechamento

    # Caixa de avisos

    def notificar(
        self,
        tipo: TipoNotificacao,
        mensagem: str,
        pedido: Pedido | None = None,
    ) -> Notificacao:
        notificacao = Notificacao(
            destinatario=self, tipo=tipo, mensagem=mensagem, pedido=pedido
        )
        self.notificacoes.append(notificacao)
        return notificacao

    @property
    def notificacoes_nao_lidas(self) -> list[Notificacao]:
        return [n for n in self.notificacoes if n.nao_lida]

    @property
    def total_nao_lidas(self) -> int:
        return len(self.notificacoes_nao_lidas)

    def marcar_notificacoes_como_lidas(self) -> list[Notificacao]:
        """Marca tudo como lido e devolve o que mudou, para o repositório gravar."""
        alteradas = self.notificacoes_nao_lidas
        for notificacao in alteradas:
            notificacao.marcar_como_lida()
        return alteradas

    def __repr__(self) -> str:
        return f"<{type(self).__name__} #{self.id} {self.nome!r}>"


class EmpresaMarisqueira(Empresa):
    """Oferta produtos, analisa pedidos e entrega.

    Métodos da atividade: cadastrar_produto, alterar_quantidade,
    receber_pedido, aceitar_pedido, rejeitar_pedido, solicitar_ajuste,
    atualizar_status_entrega.

    Faz a autorização de RN12 e orquestra. O estado em si fica no Produto e
    no Pedido.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.produtos: list[Produto] = []
        self.pedidos_recebidos: list[Pedido] = []
        self.avaliacoes: list[Avaliacao] = []
        # Extensão além de P27. Por padrão aceita tudo; a empresa restringe
        # se quiser, e o pedido valida contra esta lista.
        self.formas_pagamento_aceitas: set[FormaPagamento] = set(FormaPagamento)

    def tipo(self) -> str:
        return "Empresa das marisqueiras"

    # Métodos exigidos pela atividade

    def cadastrar_produto(
        self,
        nome: str,
        categoria: Categoria,
        preco_por_kg: Decimal,
        quantidade_disponivel_kg: Decimal,
        foto: str | None = None,
        localizacao: str | None = None,
    ) -> Produto:
        """P15 e RN04 a RN07: cadastra um produto desta empresa.

        Os 25 kg de RN05 são exigidos aqui e não no construtor do Produto, porque
        depois o estoque pode cair abaixo disso vendendo (RN09). Por RN06, a
        duplicidade é o par (nome, categoria) e não o nome sozinho.
        """
        if quantidade_disponivel_kg is None or (
            Decimal(quantidade_disponivel_kg) < Produto.QUANTIDADE_MINIMA_KG
        ):
            raise QuantidadeInvalida(
                "A quantidade inicial precisa atingir o mínimo comercial de "
                f"{Produto.QUANTIDADE_MINIMA_KG} kg."
            )

        nome_limpo = (nome or "").strip()
        for existente in self.produtos:
            if (
                existente.nome.casefold() == nome_limpo.casefold()
                and existente.categoria is categoria
            ):
                raise DadoObrigatorio(
                    f"Esta empresa já tem '{nome_limpo}' cadastrado na categoria "
                    f"{categoria.rotulo}. Altere a quantidade do produto existente."
                )

        produto = Produto(
            nome=nome_limpo,
            categoria=categoria,
            preco_por_kg=preco_por_kg,
            quantidade_disponivel_kg=quantidade_disponivel_kg,
            localizacao=(localizacao or self.localizacao),
            empresa=self,
            foto=foto,
        )
        self.produtos.append(produto)
        return produto

    def alterar_quantidade(self, produto: Produto, nova_quantidade_kg: Decimal) -> None:
        """RN08, RN09 e RN12: muda o estoque de um produto desta empresa.

        Checa a autorização e repassa pro produto. Daí os dois nomes parecidos:
        aqui `alterar`, no produto `atualizar`.
        """
        self._exigir_propriedade(produto)
        produto.atualizar_quantidade(nova_quantidade_kg)

    def receber_pedido(self, pedido: Pedido) -> None:
        """P7 / RN14: registra um pedido recebido para análise."""
        if pedido is None:
            raise DadoObrigatorio("Pedido inválido.")
        if pedido.marisqueira is not self:
            raise AcessoNaoAutorizado(f"Este pedido não é destinado a '{self.nome}'.")
        pedido.validar_para_envio()  # RN13 / RN15 / RN18
        if pedido not in self.pedidos_recebidos:
            self.pedidos_recebidos.append(pedido)
        pedido.status = StatusPedido.AGUARDANDO_ANALISE
        self.notificar(
            TipoNotificacao.PEDIDO_RECEBIDO,
            f"{pedido.compradora.nome} fez um pedido de "
            f"{pedido.quantidade_total_kg} kg aguardando sua análise.",
            pedido,
        )

    def aceitar_pedido(self, pedido: Pedido) -> None:
        """P7 / RN18: aceita o pedido e baixa o estoque dos itens."""
        self._exigir_pedido_proprio(pedido)
        pedido.validar_para_envio()  # o estoque pode ter mudado desde o envio
        pedido.marcar_aceito()
        pedido.compradora.notificar(
            TipoNotificacao.PEDIDO_ACEITO,
            f"{self.nome} aceitou seu pedido. Prazo de entrega de "
            f"{pedido.tempo_entrega_dias} dia(s).",
            pedido,
        )

    def rejeitar_pedido(self, pedido: Pedido, motivo: str) -> None:
        """P7: rejeita o pedido, registrando a justificativa."""
        self._exigir_pedido_proprio(pedido)
        pedido.marcar_rejeitado(motivo)
        pedido.compradora.notificar(
            TipoNotificacao.PEDIDO_REJEITADO,
            f"{self.nome} rejeitou seu pedido. Motivo: {pedido.motivo_rejeicao}",
            pedido,
        )

    def solicitar_ajuste(self, pedido: Pedido, observacao: str) -> None:
        """P7: devolve o pedido à compradora pedindo um ajuste.

        A partir daqui a decisão é da compradora, que ajusta e reenvia ou
        cancela. Ver `EmpresaCompradora.responder_ajuste`.
        """
        self._exigir_pedido_proprio(pedido)
        pedido.marcar_ajuste_solicitado(observacao)
        pedido.compradora.notificar(
            TipoNotificacao.AJUSTE_SOLICITADO,
            f"{self.nome} pediu um ajuste no seu pedido: {pedido.observacao_ajuste}",
            pedido,
        )

    def atualizar_status_entrega(
        self, pedido: Pedido, novo_status: StatusEntrega
    ) -> None:
        """RN22: informa o andamento da entrega, sem rastreio em tempo real.

        Quem entrega é a marisqueira (P10), mas o último passo é da compradora,
        em `EmpresaCompradora.confirmar_entrega`.
        """
        self._exigir_pedido_proprio(pedido)
        pedido.definir_status_entrega(novo_status)
        if novo_status is StatusEntrega.SAIU_PARA_ENTREGA:
            pedido.compradora.notificar(
                TipoNotificacao.SAIU_PARA_ENTREGA,
                f"Seu pedido saiu para entrega em {pedido.endereco_entrega}. "
                "Confirme o recebimento quando a mercadoria chegar.",
                pedido,
            )

    # RN12: visibilidade: a marisqueira vê apenas os próprios produtos

    def registrar_rastreabilidade(
        self,
        produto: Produto,
        lote: str,
        data_coleta,
        local_coleta: str,
        responsavel: str,
        metodo: MetodoColeta = MetodoColeta.CATACAO_MANUAL,
        coordenada=None,
        observacoes: str | None = None,
    ) -> Rastreabilidade:
        """Preenche a ficha de origem do lote em venda.

        Extensão além de P2. A ficha substitui a anterior porque representa o
        lote que está na prateleira agora; os lotes já vendidos continuam
        guardados nos itens dos pedidos.
        """
        self._exigir_propriedade(produto)
        ficha = Rastreabilidade(
            lote=lote,
            data_coleta=data_coleta,
            local_coleta=local_coleta,
            responsavel=responsavel,
            metodo=metodo,
            coordenada=coordenada or self.coordenada,
            observacoes=observacoes,
        )
        produto.rastreabilidade = ficha
        return ficha

    def confirmar_pagamento(self, pedido: Pedido) -> Pedido:
        """Confirma que o dinheiro entrou. Extensão além de P27."""
        self._exigir_pedido_proprio(pedido)
        pedido.marcar_pagamento_confirmado()
        pedido.compradora.notificar(
            TipoNotificacao.PAGAMENTO_CONFIRMADO,
            f"{self.nome} confirmou o pagamento em {pedido.forma_pagamento.rotulo}.",
            pedido,
        )
        return pedido

    def registrar_posicao(
        self, pedido: Pedido, coordenada, descricao: str
    ) -> EventoEntrega:
        """Marca onde o entregador está. Extensão além de P10.

        Não notifica a cada ponto de propósito: uma entrega gera dezenas de
        posições e a caixa de avisos da compradora viraria spam. O aviso sai
        no despacho e na chegada; o meio do caminho ela vê no mapa.
        """
        self._exigir_pedido_proprio(pedido)
        return pedido.registrar_evento_entrega(coordenada, descricao)

    def consultar_produtos(
        self, catalogo: list[Produto] | None = None
    ) -> list[Produto]:
        """P25 e RN12: a marisqueira vê só os produtos dela.

        Recebe o catálogo inteiro e filtra. O filtro fica no domínio e não
        na tela, pra regra valer em qualquer tela.
        """
        fonte = catalogo if catalogo is not None else self.produtos
        return [p for p in fonte if p.empresa is self]

    # Métodos complementares exigidos pelas rns

    def alterar_preco_produto(self, produto: Produto, novo_preco: Decimal) -> None:
        """RN07: o preço não pode ser alterado durante uma venda.

        "Durante uma venda" é interpretado como: existe pedido deste produto
        em andamento (aguardando análise, em ajuste, aceito ou em preparação).
        Pedidos entregues ou rejeitados não travam mais nada.
        """
        self._exigir_propriedade(produto)
        em_andamento = (
            StatusPedido.AGUARDANDO_ANALISE,
            StatusPedido.AJUSTE_SOLICITADO,
            StatusPedido.ACEITO,
            StatusPedido.EM_PREPARACAO,
        )
        for pedido in self.pedidos_recebidos:
            if pedido.status in em_andamento and pedido._item_de(produto) is not None:
                raise PrecoAlteradoEmVenda(
                    f"O preço de '{produto.nome}' não pode ser alterado: há "
                    f"uma venda em andamento (pedido #{pedido.id}, "
                    f"{pedido.status.rotulo})."
                )
        produto.alterar_preco(novo_preco)

    def registrar_avaliacao(self, avaliacao: Avaliacao) -> None:
        """RN21: guarda a avaliação recebida, para compor a média."""
        if avaliacao not in self.avaliacoes:
            self.avaliacoes.append(avaliacao)

    @property
    def media_avaliacoes(self) -> Decimal:
        """RN11 / P24: média em estrelas; 0 quando ainda não há avaliações."""
        if not self.avaliacoes:
            return Decimal("0")
        soma = sum(a.nota for a in self.avaliacoes)
        return (Decimal(soma) / Decimal(len(self.avaliacoes))).quantize(Decimal("0.1"))

    @property
    def situacao(self) -> SituacaoEmpresa:
        """RN19 / RN20 / P33: indicador visual da empresa.

        Vermelho fora do horário; verde se há pelo menos um produto
        vendável; laranja caso contrário. RN19 garante que a empresa
        permanece cadastrada mesmo sem estoque.
        """
        if not self.esta_em_horario_de_funcionamento():
            return SituacaoEmpresa.FORA_DE_HORARIO
        if any(p.esta_disponivel for p in self.produtos):
            return SituacaoEmpresa.DISPONIVEL
        return SituacaoEmpresa.ESTOQUE_BAIXO

    @property
    def pedidos_pendentes(self) -> list[Pedido]:
        return [
            p
            for p in self.pedidos_recebidos
            if p.status
            in (StatusPedido.AGUARDANDO_ANALISE, StatusPedido.AJUSTE_SOLICITADO)
        ]

    # Autorização (RN12)

    def _exigir_propriedade(self, produto: Produto) -> None:
        if produto is None:
            raise DadoObrigatorio("Selecione um produto.")
        if produto.empresa is not self:
            raise AcessoNaoAutorizado(
                f"'{produto.nome}' não pertence a '{self.nome}'. "
                "Uma empresa só pode alterar os próprios produtos."
            )

    def _exigir_pedido_proprio(self, pedido: Pedido) -> None:
        if pedido is None:
            raise DadoObrigatorio("Selecione um pedido.")
        if pedido.marisqueira is not self:
            raise AcessoNaoAutorizado(f"O pedido #{pedido.id} não é de '{self.nome}'.")


class EmpresaCompradora(Empresa):
    """Empresa compradora: consulta, compara, pede e avalia.

    Métodos da atividade: consultar_produtos, comparar_produtos,
    realizar_pedido, avaliar_empresa.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pedidos: list[Pedido] = []

    def tipo(self) -> str:
        return "Empresa compradora"

    # Métodos exigidos pela atividade

    def consultar_produtos(
        self,
        catalogo: list[Produto],
        nome: str | None = None,
        categoria: Categoria | None = None,
        localizacao: str | None = None,
        empresa: EmpresaMarisqueira | None = None,
        avaliacao_minima: int | None = None,
        raio_km: Decimal | int | None = None,
        ordenar_por: OrdenacaoBusca | None = None,
    ) -> list[Produto]:
        """RN10, RN11, RN12, P9, P21 e P22: busca no catálogo.

        Só os filtros de P21: nome, categoria, localização, empresa e
        avaliação. O catálogo vem por parâmetro pra não precisar de banco
        aqui. Produto sem estoque continua no resultado, marcado como
        indisponível (RN09, P20).
        """
        resultado = list(catalogo)

        if nome:
            termo = nome.strip().casefold()
            resultado = [p for p in resultado if termo in p.nome.casefold()]

        if categoria is not None:
            resultado = [p for p in resultado if p.categoria is categoria]

        if localizacao:
            termo = localizacao.strip().casefold()
            resultado = [p for p in resultado if termo in p.localizacao.casefold()]

        if empresa is not None:
            resultado = [p for p in resultado if p.empresa is empresa]

        if avaliacao_minima is not None:
            resultado = [
                p
                for p in resultado
                if p.empresa is not None
                and p.empresa.media_avaliacoes >= Decimal(avaliacao_minima)
            ]

        # Extensão além de P10: filtra por distância real, não por texto.
        if raio_km is not None:
            limite = Decimal(str(raio_km))
            resultado = [
                p
                for p in resultado
                if (d := self.distancia_ate_produto(p)) is not None and d <= limite
            ]

        return self._ordenar(resultado, ordenar_por)

    def comparar_produtos(self, produtos: list[Produto]) -> list[dict]:
        """RN12 e P26: compara produtos, inclusive de empresas diferentes.

        Devolve dicionários prontos pra tabela. Quem compara é a compradora; a
        marisqueira só vê os produtos dela.
        """
        if len(produtos) < 2:
            raise DadoObrigatorio("Selecione pelo menos dois produtos para comparar.")

        precos = [p.preco_por_kg for p in produtos]
        menor_preco = min(precos)
        melhor_nota = max(
            (p.empresa.media_avaliacoes for p in produtos if p.empresa),
            default=Decimal("0"),
        )

        comparacao = []
        for p in produtos:
            nota = p.empresa.media_avaliacoes if p.empresa else Decimal("0")
            comparacao.append(
                {
                    "produto": p,
                    "nome": p.nome,
                    "categoria": p.categoria.rotulo,
                    "empresa": p.empresa.nome if p.empresa else "",
                    "localizacao": p.localizacao,
                    "preco_por_kg": p.preco_por_kg,
                    "estoque_kg": p.quantidade_disponivel_kg,
                    "disponivel": p.esta_disponivel,
                    "avaliacao": nota,
                    "melhor_preco": p.preco_por_kg == menor_preco,
                    "melhor_avaliacao": nota == melhor_nota and nota > 0,
                }
            )
        return comparacao

    def realizar_pedido(
        self,
        itens: list[tuple[Produto, Decimal]],
        endereco_entrega: str,
        tempo_entrega_dias: int,
        forma_pagamento: FormaPagamento = FormaPagamento.PIX,
    ) -> Pedido:
        """RN13 a RN18 e P27: monta e envia o pedido.

        `itens` é uma lista de pares (produto, quantidade_kg). Valida tudo antes
        de passar pra marisqueira, então não existe pedido meio criado. O estoque
        só baixa no aceite, porque antes disso a venda ainda pode não acontecer.
        """
        if not itens:
            raise DadoObrigatorio("Adicione pelo menos um produto ao pedido.")

        pedido = Pedido(
            compradora=self,
            endereco_entrega=endereco_entrega,
            tempo_entrega_dias=tempo_entrega_dias,
            forma_pagamento=forma_pagamento,
        )
        for produto, quantidade in itens:
            pedido.adicionar_item(produto, quantidade)  # RN14 / RN15 / RN18

        pedido.validar_para_envio()

        marisqueira = pedido.marisqueira
        if marisqueira is None:
            raise DadoObrigatorio("Não foi possível identificar a empresa vendedora.")
        if forma_pagamento not in marisqueira.formas_pagamento_aceitas:
            aceitas = ", ".join(f.rotulo for f in marisqueira.formas_pagamento_aceitas)
            raise DadoObrigatorio(
                f"{marisqueira.nome} não aceita {forma_pagamento.rotulo}. "
                f"Formas aceitas: {aceitas}."
            )
        marisqueira.receber_pedido(pedido)  # P7

        self.pedidos.append(pedido)
        return pedido

    def responder_ajuste(
        self, pedido: Pedido, itens: list[tuple[Produto, Decimal]]
    ) -> Pedido:
        """P7: responde ao pedido de ajuste com as quantidades corrigidas.

        Sem isso o pedido travava: a marisqueira pedia ajuste e ninguém podia
        mexer. Revalida RN14, RN15 e RN18, e não altera nada se algum item for
        inválido.
        """
        self._exigir_pedido_proprio(pedido)
        if not pedido.aguarda_resposta_da_compradora:
            raise TransicaoInvalida(
                "Só é possível ajustar um pedido com ajuste solicitado "
                f"(status atual: '{pedido.status.rotulo}')."
            )

        pedido.substituir_itens(itens)
        pedido.reenviar_para_analise()
        if pedido.marisqueira is not None:
            pedido.marisqueira.notificar(
                TipoNotificacao.PEDIDO_REENVIADO,
                f"{self.nome} ajustou o pedido para "
                f"{pedido.quantidade_total_kg} kg e reenviou para análise.",
                pedido,
            )
        return pedido

    def cancelar_pedido(self, pedido: Pedido) -> Pedido:
        """P7: a compradora desiste do pedido enquanto ele não foi aceito.

        É a outra saída de um ajuste que não serve: se a quantidade possível
        não atende, cancelar é melhor que deixar o pedido parado para sempre.
        """
        self._exigir_pedido_proprio(pedido)
        pedido.marcar_cancelado()
        if pedido.marisqueira is not None:
            pedido.marisqueira.notificar(
                TipoNotificacao.PEDIDO_CANCELADO,
                f"{self.nome} cancelou o pedido {pedido.id or ''}.".strip(),
                pedido,
            )
        return pedido

    def informar_pagamento(self, pedido: Pedido) -> Pedido:
        """A compradora avisa que pagou. Extensão além de P27.

        Não vale como pago: quem confirma é a marisqueira, que é quem vê o
        dinheiro na conta.
        """
        self._exigir_pedido_proprio(pedido)
        pedido.marcar_pagamento_informado()
        if pedido.marisqueira is not None:
            pedido.marisqueira.notificar(
                TipoNotificacao.PAGAMENTO_INFORMADO,
                f"{self.nome} informou pagamento de {pedido.total} em "
                f"{pedido.forma_pagamento.rotulo}. Confirme o recebimento.",
                pedido,
            )
        return pedido

    def consultar_origem(self, pedido: Pedido) -> list[Rastreabilidade]:
        """Fichas de origem dos itens comprados. Extensão além de P2."""
        self._exigir_pedido_proprio(pedido)
        return [item.origem for item in pedido.itens if item.origem is not None]

    def confirmar_entrega(self, pedido: Pedido) -> Pedido:
        """RN21 / RN22: a compradora atesta que recebeu a mercadoria.

        Quem confirma é quem recebe. A marisqueira informa até o despacho
        (`atualizar_status_entrega`); dizer que chegou é da compradora, e é
        essa confirmação que libera a avaliação de RN21.
        """
        self._exigir_pedido_proprio(pedido)
        pedido.confirmar_recebimento()
        if pedido.marisqueira is not None:
            pedido.marisqueira.notificar(
                TipoNotificacao.ENTREGA_CONFIRMADA,
                f"{self.nome} confirmou o recebimento do pedido "
                f"{pedido.id or ''}.".strip(),
                pedido,
            )
        return pedido

    def avaliar_empresa(
        self, pedido: Pedido, nota: int, comentario: str | None = None
    ) -> Avaliacao:
        """RN21, P23 e P24: avalia a marisqueira depois da compra.

        Checa nesta ordem: o pedido é desta compradora, já foi entregue, e ainda
        não tem avaliação.
        """
        if pedido is None:
            raise DadoObrigatorio("Selecione um pedido.")
        if pedido.compradora is not self:
            raise AvaliacaoInvalida("Só é possível avaliar os próprios pedidos.")
        if not pedido.pode_ser_avaliado:
            raise AvaliacaoInvalida(
                "A avaliação só é liberada após a entrega do pedido "
                f"(status atual: '{pedido.status.rotulo}')."
            )
        if pedido.marisqueira is None:
            raise AvaliacaoInvalida("O pedido não tem empresa vendedora definida.")
        if any(a.pedido is pedido for a in pedido.marisqueira.avaliacoes):
            raise AvaliacaoInvalida("Este pedido já foi avaliado.")

        avaliacao = Avaliacao(pedido=pedido, nota=nota, comentario=comentario)
        pedido.marisqueira.registrar_avaliacao(avaliacao)
        pedido.marisqueira.notificar(
            TipoNotificacao.AVALIACAO_RECEBIDA,
            f"{self.nome} avaliou sua empresa com {avaliacao.nota} estrela(s).",
            pedido,
        )
        return avaliacao

    # Apoio

    def _exigir_pedido_proprio(self, pedido: Pedido) -> None:
        if pedido is None:
            raise DadoObrigatorio("Selecione um pedido.")
        if pedido.compradora is not self:
            raise AcessoNaoAutorizado(
                f"O pedido {pedido.id or ''} não é de '{self.nome}'.".strip()
            )

    def _ordenar(
        self, produtos: list[Produto], ordenar_por: OrdenacaoBusca | None
    ) -> list[Produto]:
        """RN11 / P22: menor preço, maior preço, melhor avaliação, proximidade.

        PROXIMIDADE é simplificada: produtos na mesma localização da
        compradora vêm primeiro, depois os demais em ordem alfabética.
        Geolocalização real está fora do escopo (P10: sem rastreamento).
        """
        if ordenar_por is None:
            return produtos

        if ordenar_por is OrdenacaoBusca.MENOR_PRECO:
            return sorted(produtos, key=lambda p: p.preco_por_kg)
        if ordenar_por is OrdenacaoBusca.MAIOR_PRECO:
            return sorted(produtos, key=lambda p: p.preco_por_kg, reverse=True)
        if ordenar_por is OrdenacaoBusca.MELHOR_AVALIACAO:
            return sorted(
                produtos,
                key=lambda p: p.empresa.media_avaliacoes if p.empresa else Decimal("0"),
                reverse=True,
            )
        if ordenar_por is OrdenacaoBusca.PROXIMIDADE:
            # Extensão além de P10: distância geodésica de verdade. Produto
            # sem coordenada vai para o fim, com desempate por texto, que era
            # o comportamento anterior.
            def chave(produto: Produto):
                distancia = self.distancia_ate_produto(produto)
                if distancia is None:
                    return (1, Decimal("0"), produto.localizacao.casefold())
                return (0, distancia, produto.localizacao.casefold())

            return sorted(produtos, key=chave)
        return produtos

    def distancia_ate_produto(self, produto: Produto) -> Decimal | None:
        """Km entre esta compradora e onde o produto está."""
        if self.coordenada is None:
            return None
        return self.coordenada.distancia_km(produto.coordenada)
