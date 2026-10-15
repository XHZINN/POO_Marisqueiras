"""Painel da empresa das marisqueiras: produtos, pedidos e avaliações.

RN12: todas as listagens desta tela passam por
`EmpresaMarisqueira.consultar_produtos`, que devolve apenas os produtos da
própria empresa. A restrição está no domínio, não aqui.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from dominio.empresa import EmpresaMarisqueira
from dominio.enums import (
    Categoria,
    MetodoColeta,
    StatusEntrega,
    StatusPagamento,
    StatusPedido,
)
from dominio.pedido import Pedido
from dominio.produto import Produto
from repositorio.repositorio import Repositorio
from ui.componentes import (
    cartao,
    celula,
    celula_numero,
    celula_situacao,
    celula_status,
    celula_suave,
    divisor,
    estrelas,
    kg,
    metrica,
    pilula_status,
    protegido,
    reais,
    rotulo_secao,
    tabela,
)
from ui.dialogo_simulacao import DialogoSimulacao
from ui.painel_notificacoes import PainelNotificacoes


class DialogoOrigem(QDialog):
    """Ficha do lote em venda. Extensão além de P2."""

    def __init__(self, pai, produto) -> None:
        super().__init__(pai)
        self.setWindowTitle("Ficha de origem")
        self.setMinimumWidth(460)
        ficha = produto.rastreabilidade

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(14)
        titulo = QLabel(produto.nome_exibicao)
        titulo.setObjectName("nomeEmpresa")
        layout.addWidget(titulo)

        formulario = QFormLayout()
        formulario.setSpacing(12)
        self.in_lote = QLineEdit(ficha.lote if ficha else "")
        self.in_lote.setPlaceholderText("SUR-2410-A")
        self.in_data = QDateEdit()
        self.in_data.setCalendarPopup(True)
        self.in_data.setMaximumDate(QDate.currentDate())
        self.in_data.setDate(
            QDate(
                ficha.data_coleta.year, ficha.data_coleta.month, ficha.data_coleta.day
            )
            if ficha
            else QDate.currentDate()
        )
        self.in_local = QLineEdit(ficha.local_coleta if ficha else "")
        self.in_local.setPlaceholderText("Baixio da Raposa")
        self.in_responsavel = QLineEdit(ficha.responsavel if ficha else "")
        self.in_responsavel.setPlaceholderText("Quem coletou")
        self.in_metodo = QComboBox()
        for metodo in MetodoColeta:
            self.in_metodo.addItem(metodo.rotulo, metodo)
        if ficha:
            self.in_metodo.setCurrentIndex(self.in_metodo.findData(ficha.metodo))
        self.in_observacoes = QLineEdit(ficha.observacoes or "" if ficha else "")
        self.in_observacoes.setPlaceholderText("Opcional")

        formulario.addRow("Lote", self.in_lote)
        formulario.addRow("Data da coleta", self.in_data)
        formulario.addRow("Local", self.in_local)
        formulario.addRow("Responsável", self.in_responsavel)
        formulario.addRow("Método", self.in_metodo)
        formulario.addRow("Observações", self.in_observacoes)
        layout.addLayout(formulario)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Salvar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "secundario"
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    @property
    def dados(self) -> dict:
        return {
            "lote": self.in_lote.text(),
            "data_coleta": self.in_data.date().toPython(),
            "local_coleta": self.in_local.text(),
            "responsavel": self.in_responsavel.text(),
            "metodo": self.in_metodo.currentData(),
            "observacoes": self.in_observacoes.text(),
        }


class PainelMarisqueira(QWidget):
    def __init__(
        self,
        empresa: EmpresaMarisqueira,
        repo: Repositorio,
        ao_alterar: Callable[[], None],
    ) -> None:
        super().__init__()
        self.empresa = empresa
        self.repo = repo
        self.ao_alterar = ao_alterar
        self._produtos_na_tabela: list[Produto] = []
        self._pedidos_na_tabela: list[Pedido] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.abas = QTabWidget()
        self.abas.addTab(self._aba_produtos(), "Produtos")
        self.abas.addTab(self._aba_pedidos(), "Pedidos")
        self.abas.addTab(self._aba_avaliacoes(), "Avaliações")
        self.painel_notificacoes = PainelNotificacoes(empresa, repo, ao_alterar)
        self._aba_avisos = self.abas.addTab(self.painel_notificacoes, "Avisos")
        layout.addWidget(self.abas)

        self.atualizar()

    # Aba 1: produtos (cadastrar_produto, alterar_quantidade)

    def _aba_produtos(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        self.area_metricas = QHBoxLayout()
        self.area_metricas.setSpacing(14)
        layout.addLayout(self.area_metricas)

        colunas = QHBoxLayout()
        colunas.setSpacing(18)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(12)
        self.tbl_produtos = tabela(
            ["Produto", "Categoria", "Preço por kg", "Estoque", "Situação", "Lote"]
        )
        self.tbl_produtos.itemSelectionChanged.connect(self._produto_selecionado_mudou)
        esquerda.addWidget(self.tbl_produtos)

        acoes = QHBoxLayout()
        acoes.setSpacing(10)
        self.btn_quantidade = QPushButton("Alterar quantidade")
        self.btn_quantidade.setObjectName("secundario")
        self.btn_quantidade.clicked.connect(self._alterar_quantidade)
        self.btn_preco = QPushButton("Alterar preço")
        self.btn_preco.setObjectName("secundario")
        self.btn_preco.clicked.connect(self._alterar_preco)
        self.btn_origem = QPushButton("Ficha de origem")
        self.btn_origem.setObjectName("secundario")
        self.btn_origem.clicked.connect(self._editar_origem)
        acoes.addWidget(self.btn_quantidade)
        acoes.addWidget(self.btn_preco)
        acoes.addWidget(self.btn_origem)
        acoes.addStretch()
        esquerda.addLayout(acoes)

        colunas.addLayout(esquerda, 3)
        colunas.addWidget(self._formulario_cadastro(), 2)
        layout.addLayout(colunas)
        return pagina

    def _formulario_cadastro(self) -> QGroupBox:
        caixa = QGroupBox("Novo produto")
        formulario = QFormLayout(caixa)
        formulario.setSpacing(12)
        formulario.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.in_nome = QLineEdit()
        self.in_nome.setPlaceholderText("Sururu, ostra, camarão")

        self.in_categoria = QComboBox()
        for categoria in Categoria:  # o enum alimenta o combo
            self.in_categoria.addItem(categoria.rotulo, categoria)

        self.in_preco = QDoubleSpinBox()
        self.in_preco.setRange(0.01, 9999.99)
        self.in_preco.setDecimals(2)
        self.in_preco.setValue(20.00)
        self.in_preco.setPrefix("R$ ")

        # Começa em zero de propósito: quem recusa menos de 25 kg é o
        # domínio em `cadastrar_produto` (RN05), não o widget.
        self.in_quantidade = QDoubleSpinBox()
        self.in_quantidade.setRange(0, 999999)
        self.in_quantidade.setDecimals(2)
        self.in_quantidade.setValue(float(Produto.QUANTIDADE_MINIMA_KG))
        self.in_quantidade.setSuffix(" kg")

        self.in_foto = QLineEdit()
        self.in_foto.setPlaceholderText("Opcional")

        formulario.addRow("Nome", self.in_nome)
        formulario.addRow("Categoria", self.in_categoria)
        formulario.addRow("Preço por kg", self.in_preco)
        formulario.addRow("Quantidade", self.in_quantidade)
        formulario.addRow("Foto", self.in_foto)
        formulario.addRow(divisor())

        botao = QPushButton("Cadastrar")
        botao.clicked.connect(self._cadastrar_produto)
        formulario.addRow(botao)
        return caixa

    def _cadastrar_produto(self) -> None:
        def acao() -> None:
            produto = self.empresa.cadastrar_produto(
                nome=self.in_nome.text(),
                categoria=self.in_categoria.currentData(),
                # Decimal vindo de str: o spin box devolve float e
                # converter direto arrasta erro de ponto flutuante.
                preco_por_kg=Decimal(str(self.in_preco.value())),
                quantidade_disponivel_kg=Decimal(str(self.in_quantidade.value())),
                foto=self.in_foto.text().strip() or None,
            )
            self.repo.salvar_produto(produto)

        if protegido(self, acao, "Produto cadastrado."):
            self.in_nome.clear()
            self.in_foto.clear()
            self.ao_alterar()

    def _alterar_quantidade(self) -> None:
        """RN08 e RN09: altera o estoque pela porta de entrada da empresa."""
        produto = self._produto_selecionado()
        if produto is None:
            return
        valor, confirmado = QInputDialog.getDouble(
            self,
            "Alterar quantidade",
            f"Quantidade em estoque de {produto.nome_exibicao}:",
            float(produto.quantidade_disponivel_kg),
            0,
            999999,
            2,
        )
        if not confirmado:
            return

        def acao() -> None:
            self.empresa.alterar_quantidade(produto, Decimal(str(valor)))
            self.repo.salvar_produto(produto)

        if protegido(self, acao):
            self.ao_alterar()

    def _alterar_preco(self) -> None:
        """RN07: bloqueado se houver venda em andamento com este produto."""
        produto = self._produto_selecionado()
        if produto is None:
            return
        valor, confirmado = QInputDialog.getDouble(
            self,
            "Alterar preço",
            f"Preço por kg de {produto.nome_exibicao}:",
            float(produto.preco_por_kg),
            0.01,
            9999.99,
            2,
        )
        if not confirmado:
            return

        def acao() -> None:
            self.empresa.alterar_preco_produto(produto, Decimal(str(valor)))
            self.repo.salvar_produto(produto)

        if protegido(self, acao):
            self.ao_alterar()

    # Aba 2: pedidos (receber, aceitar, rejeitar, ajuste, entrega)

    def _aba_pedidos(self) -> QWidget:
        pagina = QWidget()
        layout = QHBoxLayout(pagina)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(18)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(12)
        self.tbl_pedidos = tabela(
            [
                "Pedido",
                "Compradora",
                "Itens",
                "Quantidade",
                "Total",
                "Status",
                "Entrega",
            ],
            largura_fixa={0: 72, 2: 64},
        )
        self.tbl_pedidos.itemSelectionChanged.connect(self._pedido_selecionado_mudou)
        esquerda.addWidget(self.tbl_pedidos)
        layout.addLayout(esquerda, 3)
        layout.addWidget(self._detalhe_pedido(), 2)
        return pagina

    def _detalhe_pedido(self) -> QWidget:
        moldura, layout = cartao(margem=20, espacamento=12)

        topo = QHBoxLayout()
        self.lbl_pedido_numero = QLabel()
        self.lbl_pedido_numero.setObjectName("nomeEmpresa")
        topo.addWidget(self.lbl_pedido_numero)
        topo.addStretch()
        self.area_pedido_status = QHBoxLayout()
        topo.addLayout(self.area_pedido_status)
        layout.addLayout(topo)

        self.lbl_pedido_info = QLabel()
        self.lbl_pedido_info.setObjectName("meta")
        self.lbl_pedido_info.setWordWrap(True)
        layout.addWidget(self.lbl_pedido_info)
        layout.addWidget(divisor())

        layout.addWidget(rotulo_secao("Itens"))
        self.lst_itens_pedido = QListWidget()
        self.lst_itens_pedido.setObjectName("carrinho")
        layout.addWidget(self.lst_itens_pedido)

        self.lbl_pedido_total = QLabel()
        self.lbl_pedido_total.setObjectName("metricaValor")
        layout.addWidget(self.lbl_pedido_total)

        self.lbl_pedido_obs = QLabel()
        self.lbl_pedido_obs.setObjectName("meta")
        self.lbl_pedido_obs.setWordWrap(True)
        layout.addWidget(self.lbl_pedido_obs)
        layout.addWidget(divisor())

        primeira = QHBoxLayout()
        primeira.setSpacing(10)
        self.btn_aceitar = QPushButton("Aceitar")
        self.btn_aceitar.setObjectName("sucesso")
        self.btn_aceitar.clicked.connect(self._aceitar_pedido)
        self.btn_rejeitar = QPushButton("Rejeitar")
        self.btn_rejeitar.setObjectName("perigo")
        self.btn_rejeitar.clicked.connect(self._rejeitar_pedido)
        primeira.addWidget(self.btn_aceitar)
        primeira.addWidget(self.btn_rejeitar)
        layout.addLayout(primeira)

        segunda = QHBoxLayout()
        segunda.setSpacing(10)
        self.btn_ajuste = QPushButton("Solicitar ajuste")
        self.btn_ajuste.setObjectName("secundario")
        self.btn_ajuste.clicked.connect(self._solicitar_ajuste)
        self.btn_entrega = QPushButton("Atualizar entrega")
        self.btn_entrega.setObjectName("secundario")
        self.btn_entrega.clicked.connect(self._atualizar_entrega)
        segunda.addWidget(self.btn_ajuste)
        segunda.addWidget(self.btn_entrega)
        layout.addLayout(segunda)

        terceira = QHBoxLayout()
        terceira.setSpacing(10)
        self.btn_pagamento = QPushButton("Confirmar pagamento")
        self.btn_pagamento.setObjectName("secundario")
        self.btn_pagamento.clicked.connect(self._confirmar_pagamento)
        self.btn_simular = QPushButton("Acompanhar entrega")
        self.btn_simular.clicked.connect(self._simular_entrega)
        terceira.addWidget(self.btn_pagamento)
        terceira.addWidget(self.btn_simular)
        layout.addLayout(terceira)
        return moldura

    def _confirmar_pagamento(self) -> None:
        """Extensão além de P27: a marisqueira atesta que o dinheiro entrou."""
        pedido = self._pedido_selecionado()
        if pedido is None:
            return

        def acao() -> None:
            self.empresa.confirmar_pagamento(pedido)
            self.repo.salvar_pedido(pedido)

        if protegido(self, acao, "Pagamento confirmado."):
            self.ao_alterar()

    def _simular_entrega(self) -> None:
        """Extensão além de P10: mapa com o entregador indo de A até B."""
        pedido = self._pedido_selecionado()
        if pedido is None:
            return
        DialogoSimulacao(self, pedido, self.empresa, self.repo, self.ao_alterar).exec()
        self.ao_alterar()

    def _editar_origem(self) -> None:
        """Extensão além de P2: ficha do lote em venda."""
        produto = self._produto_selecionado()
        if produto is None:
            return
        dialogo = DialogoOrigem(self, produto)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        def acao() -> None:
            self.empresa.registrar_rastreabilidade(produto=produto, **dialogo.dados)
            self.repo.salvar_produto(produto)

        if protegido(self, acao, "Ficha de origem registrada."):
            self.ao_alterar()

    def _aceitar_pedido(self) -> None:
        pedido = self._pedido_selecionado()
        if pedido is None:
            return

        def acao() -> None:
            self.empresa.aceitar_pedido(pedido)  # RN18, baixa o estoque
            self.repo.salvar_pedido(pedido)

        if protegido(self, acao, "Pedido aceito. O estoque foi atualizado."):
            self.ao_alterar()

    def _rejeitar_pedido(self) -> None:
        pedido = self._pedido_selecionado()
        if pedido is None:
            return
        motivo, confirmado = QInputDialog.getMultiLineText(
            self, "Rejeitar pedido", "Motivo da rejeição:"
        )
        if not confirmado:
            return

        def acao() -> None:
            self.empresa.rejeitar_pedido(pedido, motivo)
            self.repo.salvar_pedido(pedido)

        if protegido(self, acao, "Pedido rejeitado."):
            self.ao_alterar()

    def _solicitar_ajuste(self) -> None:
        pedido = self._pedido_selecionado()
        if pedido is None:
            return
        observacao, confirmado = QInputDialog.getMultiLineText(
            self, "Solicitar ajuste", "Ajuste necessário:"
        )
        if not confirmado:
            return

        def acao() -> None:
            self.empresa.solicitar_ajuste(pedido, observacao)
            self.repo.salvar_pedido(pedido)

        if protegido(self, acao, "Ajuste solicitado à compradora."):
            self.ao_alterar()

    # RN22: a marisqueira informa até o despacho. ENTREGUE não entra na
    # lista porque quem confirma o recebimento é a compradora.
    STATUS_INFORMAVEIS = (
        StatusEntrega.NAO_INICIADA,
        StatusEntrega.EM_PREPARACAO,
        StatusEntrega.SAIU_PARA_ENTREGA,
    )

    def _atualizar_entrega(self) -> None:
        """RN22: informa o andamento, sem rastreamento em tempo real."""
        pedido = self._pedido_selecionado()
        if pedido is None:
            return
        opcoes = [s.rotulo for s in self.STATUS_INFORMAVEIS]
        atual = (
            opcoes.index(pedido.status_entrega.rotulo)
            if pedido.status_entrega.rotulo in opcoes
            else 0
        )
        escolha, confirmado = QInputDialog.getItem(
            self, "Status da entrega", "Situação:", opcoes, atual, False
        )
        if not confirmado:
            return
        novo = next(s for s in self.STATUS_INFORMAVEIS if s.rotulo == escolha)

        def acao() -> None:
            self.empresa.atualizar_status_entrega(pedido, novo)
            self.repo.salvar_pedido(pedido)

        if protegido(self, acao):
            self.ao_alterar()

    # Aba 3: avaliações recebidas (RN21)

    def _aba_avaliacoes(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        self.area_metricas_avaliacao = QHBoxLayout()
        self.area_metricas_avaliacao.setSpacing(14)
        layout.addLayout(self.area_metricas_avaliacao)

        self.tbl_avaliacoes = tabela(
            ["Pedido", "Compradora", "Nota", "Comentário", "Data"],
            largura_fixa={0: 72, 2: 110, 4: 110},
        )
        layout.addWidget(self.tbl_avaliacoes)
        return pagina

    # Atualização das telas

    def atualizar(self) -> None:
        self._atualizar_produtos()
        self._atualizar_pedidos()
        self._atualizar_avaliacoes()
        self._produto_selecionado_mudou()
        self._pedido_selecionado_mudou()
        self.painel_notificacoes.atualizar()
        self._atualizar_titulo_avisos()

    def _atualizar_titulo_avisos(self) -> None:
        """O contador no título da aba é o aviso de que algo chegou."""
        nao_lidas = self.empresa.total_nao_lidas
        self.abas.setTabText(
            self._aba_avisos, f"Avisos ({nao_lidas})" if nao_lidas else "Avisos"
        )

    def _limpar(self, area: QHBoxLayout) -> None:
        while area.count():
            item = area.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _atualizar_produtos(self) -> None:
        # RN12: a própria empresa filtra o catálogo.
        self._produtos_na_tabela = self.empresa.consultar_produtos(self.repo.catalogo)
        disponiveis = sum(1 for p in self._produtos_na_tabela if p.esta_disponivel)
        estoque = sum(
            (p.quantidade_disponivel_kg for p in self._produtos_na_tabela), Decimal("0")
        )

        self._limpar(self.area_metricas)
        self.area_metricas.addWidget(
            metrica("Produtos", str(len(self._produtos_na_tabela)))
        )
        self.area_metricas.addWidget(metrica("Disponíveis", str(disponiveis)))
        self.area_metricas.addWidget(metrica("Estoque total", kg(estoque)))
        self.area_metricas.addWidget(
            metrica("Pedidos pendentes", str(len(self.empresa.pedidos_pendentes)))
        )
        self.area_metricas.addStretch()

        self.tbl_produtos.setRowCount(len(self._produtos_na_tabela))
        for linha, produto in enumerate(self._produtos_na_tabela):
            self.tbl_produtos.setItem(linha, 0, celula(produto.nome, negrito=True))
            self.tbl_produtos.setItem(linha, 1, celula_suave(produto.categoria.rotulo))
            self.tbl_produtos.setItem(
                linha, 2, celula_numero(reais(produto.preco_por_kg))
            )
            self.tbl_produtos.setItem(
                linha, 3, celula_numero(kg(produto.quantidade_disponivel_kg))
            )
            self.tbl_produtos.setItem(linha, 4, celula_situacao(produto.situacao))
            ficha = produto.rastreabilidade
            self.tbl_produtos.setItem(
                linha,
                5,
                celula(ficha.lote, negrito=True)
                if ficha
                else celula_suave("sem ficha"),
            )

    def _atualizar_pedidos(self) -> None:
        self._pedidos_na_tabela = sorted(
            self.empresa.pedidos_recebidos, key=lambda p: p.id or 0, reverse=True
        )
        self.tbl_pedidos.setRowCount(len(self._pedidos_na_tabela))
        for linha, pedido in enumerate(self._pedidos_na_tabela):
            self.tbl_pedidos.setItem(
                linha, 0, celula(str(pedido.id or ""), negrito=True)
            )
            self.tbl_pedidos.setItem(linha, 1, celula(pedido.compradora.nome))
            self.tbl_pedidos.setItem(linha, 2, celula_numero(str(len(pedido.itens))))
            self.tbl_pedidos.setItem(
                linha, 3, celula_numero(kg(pedido.quantidade_total_kg))
            )
            self.tbl_pedidos.setItem(linha, 4, celula_numero(reais(pedido.total)))
            self.tbl_pedidos.setItem(linha, 5, celula_status(pedido.status))
            self.tbl_pedidos.setItem(
                linha, 6, celula_suave(pedido.status_entrega.rotulo)
            )

    def _atualizar_avaliacoes(self) -> None:
        media = self.empresa.media_avaliacoes
        total = len(self.empresa.avaliacoes)

        self._limpar(self.area_metricas_avaliacao)
        self.area_metricas_avaliacao.addWidget(
            metrica("Média", f"{media}" if total else "0")
        )
        self.area_metricas_avaliacao.addWidget(metrica("Avaliações", str(total)))
        self.area_metricas_avaliacao.addWidget(
            metrica("Estrelas", estrelas(media) if total else "Sem avaliação")
        )
        self.area_metricas_avaliacao.addStretch()

        self.tbl_avaliacoes.setRowCount(total)
        for linha, avaliacao in enumerate(self.empresa.avaliacoes):
            self.tbl_avaliacoes.setItem(
                linha, 0, celula(str(avaliacao.pedido.id or ""), negrito=True)
            )
            self.tbl_avaliacoes.setItem(linha, 1, celula(avaliacao.compradora.nome))
            self.tbl_avaliacoes.setItem(linha, 2, celula(avaliacao.estrelas))
            self.tbl_avaliacoes.setItem(
                linha, 3, celula_suave(avaliacao.comentario or "")
            )
            self.tbl_avaliacoes.setItem(
                linha, 4, celula_suave(f"{avaliacao.criado_em:%d/%m/%Y}")
            )

    # Seleção

    def _produto_selecionado(self) -> Produto | None:
        linha = self.tbl_produtos.currentRow()
        if 0 <= linha < len(self._produtos_na_tabela):
            return self._produtos_na_tabela[linha]
        return None

    def _pedido_selecionado(self) -> Pedido | None:
        linha = self.tbl_pedidos.currentRow()
        if 0 <= linha < len(self._pedidos_na_tabela):
            return self._pedidos_na_tabela[linha]
        return None

    def _produto_selecionado_mudou(self) -> None:
        tem = self._produto_selecionado() is not None
        self.btn_quantidade.setEnabled(tem)
        self.btn_preco.setEnabled(tem)
        self.btn_origem.setEnabled(tem)

    def _pedido_selecionado_mudou(self) -> None:
        pedido = self._pedido_selecionado()
        self._limpar(self.area_pedido_status)
        self.lst_itens_pedido.clear()

        if pedido is None:
            self.lbl_pedido_numero.setText("Nenhum pedido selecionado")
            self.lbl_pedido_info.setText("Selecione uma linha da tabela.")
            self.lbl_pedido_total.setText("")
            self.lbl_pedido_obs.setText("")
            for botao in (
                self.btn_aceitar,
                self.btn_rejeitar,
                self.btn_ajuste,
                self.btn_entrega,
                self.btn_pagamento,
                self.btn_simular,
            ):
                botao.setEnabled(False)
            return

        self.lbl_pedido_numero.setText(f"Pedido {pedido.id}")
        self.area_pedido_status.addWidget(pilula_status(pedido.status))
        self.lbl_pedido_info.setText(
            f"{pedido.compradora.nome}\n"
            f"{pedido.endereco_entrega}\n"
            f"Prazo de {pedido.tempo_entrega_dias} dia(s) · "
            f"entrega {pedido.status_entrega.rotulo.lower()}\n"
            f"{pedido.forma_pagamento.rotulo} · "
            f"pagamento {pedido.status_pagamento.rotulo.lower()}"
            + (
                f"\nTrajeto: faltam {pedido.distancia_restante_km} km "
                f"de {pedido.distancia_total_km} km"
                if pedido.em_transito and pedido.distancia_total_km
                else ""
            )
        )
        for item in pedido.itens:
            self.lst_itens_pedido.addItem(
                f"{item.produto.nome_exibicao}\n"
                f"{kg(item.quantidade_kg)} × {reais(item.preco_unitario)} = "
                f"{reais(item.subtotal)}"
            )
        self.lbl_pedido_total.setText(reais(pedido.total))

        observacoes = []
        if pedido.aguarda_resposta_da_compradora:
            observacoes.append("Aguardando a compradora ajustar ou cancelar.")
        if pedido.status_entrega is StatusEntrega.SAIU_PARA_ENTREGA:
            observacoes.append("Aguardando a compradora confirmar o recebimento.")
        if pedido.motivo_rejeicao:
            observacoes.append(f"Rejeitado: {pedido.motivo_rejeicao}")
        if pedido.observacao_ajuste:
            observacoes.append(f"Ajuste pedido: {pedido.observacao_ajuste}")
        self.lbl_pedido_obs.setText("\n".join(observacoes))

        # Os botões seguem a máquina de estados de P7. A tela desabilita o
        # que o domínio recusaria, mas a regra continua lá.
        permitidos = Pedido.TRANSICOES_PERMITIDAS[pedido.status]
        self.btn_aceitar.setEnabled(StatusPedido.ACEITO in permitidos)
        self.btn_rejeitar.setEnabled(StatusPedido.REJEITADO in permitidos)
        self.btn_ajuste.setEnabled(StatusPedido.AJUSTE_SOLICITADO in permitidos)
        self.btn_entrega.setEnabled(
            pedido.status in (StatusPedido.ACEITO, StatusPedido.EM_PREPARACAO)
            and pedido.status_entrega is not StatusEntrega.SAIU_PARA_ENTREGA
        )
        self.btn_pagamento.setEnabled(
            pedido.status_pagamento
            in (StatusPagamento.PENDENTE, StatusPagamento.INFORMADO)
            and pedido.status is not StatusPedido.CANCELADO
        )
        self.btn_simular.setEnabled(pedido.em_transito)
