"""Painel da empresa compradora: busca, comparação, pedido e avaliação.

RN12: a compradora vê produtos de todas as empresas. Quem decide isso é
`EmpresaCompradora.consultar_produtos`, não esta tela.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtWidgets import (
    QComboBox,
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
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dominio.avaliacao import Avaliacao
from dominio.empresa import EmpresaCompradora
from dominio.enums import Categoria, OrdenacaoBusca, StatusPedido
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
from ui.estilo import LARANJA, PRIMARIA, TEXTO_SUAVE, VERDE
from ui.painel_notificacoes import PainelNotificacoes

TODAS = "Todas"


class DialogoAvaliacao(QDialog):
    """RN21 e P24: captura nota de 1 a 5 estrelas e comentário opcional."""

    def __init__(self, pai, nome_empresa: str) -> None:
        super().__init__(pai)
        self.setWindowTitle("Avaliar empresa")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(16)

        titulo = QLabel(nome_empresa)
        titulo.setObjectName("nomeEmpresa")
        layout.addWidget(titulo)

        formulario = QFormLayout()
        formulario.setSpacing(12)
        self.in_nota = QComboBox()
        for nota in range(Avaliacao.NOTA_MAXIMA, Avaliacao.NOTA_MINIMA - 1, -1):
            self.in_nota.addItem("★" * nota + "☆" * (5 - nota), nota)
        self.in_comentario = QTextEdit()
        self.in_comentario.setPlaceholderText("Comentário opcional")
        self.in_comentario.setFixedHeight(96)
        formulario.addRow("Nota", self.in_nota)
        formulario.addRow("Comentário", self.in_comentario)
        layout.addLayout(formulario)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Avaliar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "secundario"
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    @property
    def nota(self) -> int:
        return self.in_nota.currentData()

    @property
    def comentario(self) -> str:
        return self.in_comentario.toPlainText()


class DialogoAjuste(QDialog):
    """P7: a compradora responde ao pedido de ajuste da marisqueira.

    Mostra o que a marisqueira pediu e deixa corrigir a quantidade de cada
    item. Zero remove o item. As regras RN14, RN15 e RN18 continuam sendo
    validadas pelo domínio em `responder_ajuste`, não aqui.
    """

    def __init__(self, pai, pedido: Pedido) -> None:
        super().__init__(pai)
        self.pedido = pedido
        self.setWindowTitle("Ajustar pedido")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(14)

        titulo = QLabel(f"Pedido {pedido.id}")
        titulo.setObjectName("nomeEmpresa")
        layout.addWidget(titulo)

        solicitacao = QLabel(pedido.observacao_ajuste or "")
        solicitacao.setWordWrap(True)
        solicitacao.setStyleSheet(
            f"background-color: #FCF0E2; color: {LARANJA};"
            "border-radius: 8px; padding: 12px; font-weight: 600;"
        )
        layout.addWidget(solicitacao)
        layout.addWidget(divisor())

        layout.addWidget(rotulo_secao("Quantidades"))
        formulario = QFormLayout()
        formulario.setSpacing(12)
        self._campos: list[tuple[Produto, QDoubleSpinBox]] = []
        for item in pedido.itens:
            campo = QDoubleSpinBox()
            campo.setRange(0, 999999)
            campo.setDecimals(2)
            campo.setValue(float(item.quantidade_kg))
            campo.setSuffix(" kg")
            formulario.addRow(
                f"{item.produto.nome_exibicao}\n"
                f"{reais(item.preco_unitario)} por kg, "
                f"{kg(item.produto.quantidade_disponivel_kg)} em estoque",
                campo,
            )
            self._campos.append((item.produto, campo))
        layout.addLayout(formulario)

        nota = QLabel("Zerar a quantidade remove o produto do pedido.")
        nota.setObjectName("meta")
        layout.addWidget(nota)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Reenviar pedido")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Voltar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "secundario"
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    @property
    def itens(self) -> list[tuple[Produto, Decimal]]:
        return [
            (produto, Decimal(str(campo.value())))
            for produto, campo in self._campos
            if campo.value() > 0
        ]


class DialogoComparacao(QDialog):
    """P26: tabela de comparação entre produtos, inclusive de empresas diferentes.

    Recebe do domínio uma lista de dicionários (`comparar_produtos`) e apenas
    desenha. Nenhum cálculo de melhor preço acontece aqui.
    """

    def __init__(self, pai, comparacao: list[dict]) -> None:
        super().__init__(pai)
        self.setWindowTitle("Comparar produtos")
        self.setMinimumSize(940, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(14)

        titulo = QLabel("Comparação de produtos")
        titulo.setObjectName("titulo")
        layout.addWidget(titulo)
        legenda = QLabel("O melhor preço e a melhor avaliação aparecem em verde.")
        legenda.setObjectName("subtitulo")
        layout.addWidget(legenda)

        grade = tabela(
            [
                "Produto",
                "Categoria",
                "Empresa",
                "Localização",
                "Preço por kg",
                "Estoque",
                "Avaliação",
                "Situação",
            ]
        )
        grade.setRowCount(len(comparacao))
        for linha, dados in enumerate(comparacao):
            melhor_preco = dados["melhor_preco"]
            melhor_nota = dados["melhor_avaliacao"]
            grade.setItem(linha, 0, celula(dados["nome"], negrito=True))
            grade.setItem(linha, 1, celula_suave(dados["categoria"]))
            grade.setItem(linha, 2, celula(dados["empresa"]))
            grade.setItem(linha, 3, celula_suave(dados["localizacao"]))
            grade.setItem(
                linha,
                4,
                celula_numero(
                    reais(dados["preco_por_kg"]), VERDE if melhor_preco else None
                ),
            )
            grade.setItem(linha, 5, celula_numero(kg(dados["estoque_kg"])))
            grade.setItem(
                linha,
                6,
                celula(estrelas(dados["avaliacao"]), VERDE if melhor_nota else None),
            )
            grade.setItem(linha, 7, celula_situacao(dados["produto"].situacao))
        layout.addWidget(grade)

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botoes.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)


class PainelCompradora(QWidget):
    def __init__(
        self,
        empresa: EmpresaCompradora,
        repo: Repositorio,
        ao_alterar: Callable[[], None],
    ) -> None:
        super().__init__()
        self.empresa = empresa
        self.repo = repo
        self.ao_alterar = ao_alterar
        self._resultados: list[Produto] = []
        self._pedidos_na_tabela: list[Pedido] = []
        # Carrinho: pares (produto, quantidade_kg) até virar um Pedido.
        self._carrinho: list[tuple[Produto, Decimal]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.abas = QTabWidget()
        self.abas.addTab(self._aba_busca(), "Buscar")
        self.abas.addTab(self._aba_pedidos(), "Meus pedidos")
        self.painel_notificacoes = PainelNotificacoes(empresa, repo, ao_alterar)
        self._aba_avisos = self.abas.addTab(self.painel_notificacoes, "Avisos")
        layout.addWidget(self.abas)

        self.atualizar()

    # Aba 1: busca (consultar_produtos, comparar_produtos, realizar_pedido)

    def _aba_busca(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._filtros())

        colunas = QHBoxLayout()
        colunas.setSpacing(18)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(12)
        self.tbl_busca = tabela(
            [
                "Produto",
                "Categoria",
                "Empresa",
                "Localização",
                "Preço por kg",
                "Estoque",
                "Avaliação",
                "Situação",
            ]
        )
        esquerda.addWidget(self.tbl_busca)

        acoes = QHBoxLayout()
        acoes.setSpacing(10)
        botao_adicionar = QPushButton("Adicionar ao pedido")
        botao_adicionar.clicked.connect(self._adicionar_ao_carrinho)
        botao_comparar = QPushButton("Comparar")
        botao_comparar.setObjectName("secundario")
        botao_comparar.setToolTip("Selecione duas ou mais linhas com Ctrl pressionado")
        botao_comparar.clicked.connect(self._comparar)
        self.lbl_resultados = QLabel()
        self.lbl_resultados.setObjectName("meta")
        acoes.addWidget(botao_adicionar)
        acoes.addWidget(botao_comparar)
        acoes.addSpacing(8)
        acoes.addWidget(self.lbl_resultados)
        acoes.addStretch()
        esquerda.addLayout(acoes)

        colunas.addLayout(esquerda, 3)
        colunas.addWidget(self._carrinho_widget(), 2)
        layout.addLayout(colunas)
        return pagina

    def _filtros(self) -> QGroupBox:
        """P21: nome, categoria, localização, empresa e avaliação. P22: ordenação."""
        caixa = QGroupBox("Filtros")
        linha = QHBoxLayout(caixa)
        linha.setSpacing(14)

        self.f_nome = QLineEdit()
        self.f_nome.setPlaceholderText("Buscar por nome")
        self.f_nome.textChanged.connect(self._buscar)

        self.f_categoria = QComboBox()
        self.f_categoria.addItem(TODAS, None)
        for categoria in Categoria:
            self.f_categoria.addItem(categoria.rotulo, categoria)
        self.f_categoria.currentIndexChanged.connect(self._buscar)

        self.f_localizacao = QComboBox()
        self.f_localizacao.currentIndexChanged.connect(self._buscar)

        self.f_empresa = QComboBox()
        self.f_empresa.currentIndexChanged.connect(self._buscar)

        self.f_avaliacao = QComboBox()
        self.f_avaliacao.addItem("Qualquer", None)
        for nota in range(1, 6):
            self.f_avaliacao.addItem("★" * nota, nota)
        self.f_avaliacao.currentIndexChanged.connect(self._buscar)

        self.f_ordenacao = QComboBox()
        self.f_ordenacao.addItem("Relevância", None)
        for ordem in OrdenacaoBusca:
            self.f_ordenacao.addItem(ordem.rotulo, ordem)
        self.f_ordenacao.currentIndexChanged.connect(self._buscar)

        campos = [
            ("Nome", self.f_nome, 2),
            ("Categoria", self.f_categoria, 1),
            ("Localização", self.f_localizacao, 1),
            ("Empresa", self.f_empresa, 2),
            ("Avaliação", self.f_avaliacao, 1),
            ("Ordenar por", self.f_ordenacao, 1),
        ]
        for rotulo, campo, peso in campos:
            coluna = QVBoxLayout()
            coluna.setSpacing(5)
            etiqueta = QLabel(rotulo)
            etiqueta.setObjectName("campoObrigatorio")
            coluna.addWidget(etiqueta)
            coluna.addWidget(campo)
            linha.addLayout(coluna, peso)
        return caixa

    def _carrinho_widget(self) -> QGroupBox:
        """RN13 e P27: dados obrigatórios do pedido.

        A forma de pagamento está fora do escopo atual (P27).
        """
        caixa = QGroupBox("Pedido")
        layout = QVBoxLayout(caixa)
        layout.setSpacing(12)

        self.lbl_vendedora = QLabel()
        self.lbl_vendedora.setObjectName("meta")
        self.lbl_vendedora.setWordWrap(True)
        layout.addWidget(self.lbl_vendedora)

        self.lst_carrinho = QListWidget()
        self.lst_carrinho.setObjectName("carrinho")
        layout.addWidget(self.lst_carrinho)

        botao_remover = QPushButton("Remover item")
        botao_remover.setObjectName("secundario")
        botao_remover.clicked.connect(self._remover_do_carrinho)
        layout.addWidget(botao_remover)
        layout.addWidget(divisor())

        formulario = QFormLayout()
        formulario.setSpacing(12)
        self.in_endereco = QLineEdit(self.empresa.endereco)
        self.in_prazo = QSpinBox()
        self.in_prazo.setRange(1, 60)
        self.in_prazo.setValue(3)
        self.in_prazo.setSuffix(" dia(s)")
        formulario.addRow("Endereço de entrega", self.in_endereco)
        formulario.addRow("Tempo de entrega", self.in_prazo)
        layout.addLayout(formulario)

        layout.addWidget(rotulo_secao("Total"))
        self.lbl_total_carrinho = QLabel()
        self.lbl_total_carrinho.setObjectName("metricaValor")
        layout.addWidget(self.lbl_total_carrinho)

        botao_pedir = QPushButton("Realizar pedido")
        botao_pedir.clicked.connect(self._realizar_pedido)
        layout.addWidget(botao_pedir)
        return caixa

    def _buscar(self) -> None:
        """RN10 e RN11: delega a busca ao domínio e apenas desenha o resultado."""
        self._resultados = self.empresa.consultar_produtos(
            self.repo.catalogo,
            nome=self.f_nome.text() or None,
            categoria=self.f_categoria.currentData(),
            localizacao=self.f_localizacao.currentData(),
            empresa=self.f_empresa.currentData(),
            avaliacao_minima=self.f_avaliacao.currentData(),
            ordenar_por=self.f_ordenacao.currentData(),
        )
        self.lbl_resultados.setText(f"{len(self._resultados)} produto(s)")
        self.tbl_busca.setRowCount(len(self._resultados))
        for linha, produto in enumerate(self._resultados):
            nota = produto.empresa.media_avaliacoes if produto.empresa else Decimal("0")
            self.tbl_busca.setItem(linha, 0, celula(produto.nome, negrito=True))
            self.tbl_busca.setItem(linha, 1, celula_suave(produto.categoria.rotulo))
            self.tbl_busca.setItem(
                linha, 2, celula(produto.empresa.nome if produto.empresa else "")
            )
            self.tbl_busca.setItem(linha, 3, celula_suave(produto.localizacao))
            self.tbl_busca.setItem(linha, 4, celula_numero(reais(produto.preco_por_kg)))
            self.tbl_busca.setItem(
                linha, 5, celula_numero(kg(produto.quantidade_disponivel_kg))
            )
            self.tbl_busca.setItem(linha, 6, celula_suave(estrelas(nota)))
            # RN09 e P20: sem estoque continua listado, marcado indisponível.
            self.tbl_busca.setItem(linha, 7, celula_situacao(produto.situacao))

    def _produtos_selecionados(self) -> list[Produto]:
        linhas = sorted({indice.row() for indice in self.tbl_busca.selectedIndexes()})
        return [
            self._resultados[linha] for linha in linhas if linha < len(self._resultados)
        ]

    def _adicionar_ao_carrinho(self) -> None:
        selecionados = self._produtos_selecionados()
        if not selecionados:
            return
        produto = selecionados[0]
        minimo = float(Produto.QUANTIDADE_MINIMA_KG)
        quantidade, confirmado = QInputDialog.getDouble(
            self,
            "Quantidade",
            f"{produto.nome_exibicao}\n"
            f"Mínimo {minimo:.0f} kg, disponível "
            f"{produto.quantidade_disponivel_kg} kg",
            minimo,
            0,
            999999,
            2,
        )
        if not confirmado:
            return

        # Valida no domínio antes de entrar no carrinho, pro erro aparecer
        # na hora da escolha e não no fim.
        candidato = Pedido(
            compradora=self.empresa,
            endereco_entrega=self.in_endereco.text() or self.empresa.endereco,
            tempo_entrega_dias=self.in_prazo.value(),
        )

        def acao() -> None:
            for item_produto, item_quantidade in self._carrinho:
                candidato.adicionar_item(item_produto, item_quantidade)
            candidato.adicionar_item(produto, Decimal(str(quantidade)))

        if not protegido(self, acao):
            return

        for indice, (item_produto, item_quantidade) in enumerate(self._carrinho):
            if item_produto is produto:
                self._carrinho[indice] = (
                    produto,
                    item_quantidade + Decimal(str(quantidade)),
                )
                break
        else:
            self._carrinho.append((produto, Decimal(str(quantidade))))
        self._atualizar_carrinho()

    def _remover_do_carrinho(self) -> None:
        linha = self.lst_carrinho.currentRow()
        if 0 <= linha < len(self._carrinho):
            del self._carrinho[linha]
            self._atualizar_carrinho()

    def _atualizar_carrinho(self) -> None:
        self.lst_carrinho.clear()
        total = Decimal("0")
        for produto, quantidade in self._carrinho:
            subtotal = quantidade * produto.preco_por_kg
            total += subtotal
            self.lst_carrinho.addItem(
                f"{produto.nome_exibicao}\n"
                f"{kg(quantidade)} × {reais(produto.preco_por_kg)} = {reais(subtotal)}"
            )
        self.lbl_total_carrinho.setText(reais(total))

        empresa = self._carrinho[0][0].empresa if self._carrinho else None
        if empresa is None:
            self.lbl_vendedora.setText("Nenhum produto adicionado.")
            self.lbl_vendedora.setStyleSheet(f"color: {TEXTO_SUAVE};")
        else:
            self.lbl_vendedora.setText(f"Vendedora: {empresa.nome}")
            self.lbl_vendedora.setStyleSheet(f"color: {PRIMARIA}; font-weight: 600;")

    def _comparar(self) -> None:
        """P26: comparação entre produtos, inclusive de empresas diferentes."""
        selecionados = self._produtos_selecionados()
        comparacao: list[dict] = []

        def acao() -> None:
            comparacao.extend(self.empresa.comparar_produtos(selecionados))

        if protegido(self, acao):
            DialogoComparacao(self, comparacao).exec()

    def _realizar_pedido(self) -> None:
        """RN13, RN14, RN15 e RN18: monta, valida e envia o pedido."""

        def acao() -> None:
            pedido = self.empresa.realizar_pedido(
                itens=list(self._carrinho),
                endereco_entrega=self.in_endereco.text(),
                tempo_entrega_dias=self.in_prazo.value(),
            )
            self.repo.salvar_pedido(pedido)

        if protegido(
            self, acao, "Pedido enviado. Aguarde a análise da empresa das marisqueiras."
        ):
            self._carrinho.clear()
            self._atualizar_carrinho()
            self.ao_alterar()

    # Aba 2: meus pedidos e avaliação

    def _aba_pedidos(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        self.area_metricas = QHBoxLayout()
        self.area_metricas.setSpacing(14)
        layout.addLayout(self.area_metricas)

        colunas = QHBoxLayout()
        colunas.setSpacing(18)
        self.tbl_meus_pedidos = tabela(
            [
                "Pedido",
                "Empresa",
                "Itens",
                "Quantidade",
                "Total",
                "Status",
                "Avaliação",
            ],
            largura_fixa={0: 72, 2: 64},
        )
        self.tbl_meus_pedidos.itemSelectionChanged.connect(self._meu_pedido_mudou)
        colunas.addWidget(self.tbl_meus_pedidos, 3)
        colunas.addWidget(self._detalhe_pedido(), 2)
        layout.addLayout(colunas)
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

        self.btn_confirmar = QPushButton("Confirmar recebimento")
        self.btn_confirmar.setObjectName("sucesso")
        self.btn_confirmar.clicked.connect(self._confirmar_entrega)
        layout.addWidget(self.btn_confirmar)

        self.btn_avaliar = QPushButton("Avaliar empresa")
        self.btn_avaliar.clicked.connect(self._avaliar)
        layout.addWidget(self.btn_avaliar)

        resposta = QHBoxLayout()
        resposta.setSpacing(10)
        self.btn_ajustar = QPushButton("Ajustar e reenviar")
        self.btn_ajustar.clicked.connect(self._ajustar)
        self.btn_cancelar = QPushButton("Cancelar pedido")
        self.btn_cancelar.setObjectName("perigo")
        self.btn_cancelar.clicked.connect(self._cancelar)
        resposta.addWidget(self.btn_ajustar)
        resposta.addWidget(self.btn_cancelar)
        layout.addLayout(resposta)
        return moldura

    def _pedido_selecionado(self) -> Pedido | None:
        linha = self.tbl_meus_pedidos.currentRow()
        if 0 <= linha < len(self._pedidos_na_tabela):
            return self._pedidos_na_tabela[linha]
        return None

    def _avaliacao_de(self, pedido: Pedido) -> Avaliacao | None:
        if pedido.marisqueira is None:
            return None
        return next(
            (a for a in pedido.marisqueira.avaliacoes if a.pedido is pedido), None
        )

    def _avaliar(self) -> None:
        pedido = self._pedido_selecionado()
        if pedido is None or pedido.marisqueira is None:
            return
        dialogo = DialogoAvaliacao(self, pedido.marisqueira.nome)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        def acao() -> None:
            avaliacao = self.empresa.avaliar_empresa(
                pedido, dialogo.nota, dialogo.comentario
            )
            self.repo.salvar_avaliacao(avaliacao)

        if protegido(self, acao, "Avaliação registrada."):
            self.ao_alterar()

    def _ajustar(self) -> None:
        """P7: responde ao pedido de ajuste com as quantidades corrigidas."""
        pedido = self._pedido_selecionado()
        if pedido is None:
            return
        dialogo = DialogoAjuste(self, pedido)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        itens = dialogo.itens

        def acao() -> None:
            self.empresa.responder_ajuste(pedido, itens)
            self.repo.salvar_pedido(pedido)

        if protegido(self, acao, "Pedido reenviado para análise."):
            self.ao_alterar()

    def _cancelar(self) -> None:
        pedido = self._pedido_selecionado()
        if pedido is None:
            return
        confirmacao = QMessageBox.question(
            self,
            "Cancelar pedido",
            f"Cancelar o pedido {pedido.id}? Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmacao is not QMessageBox.StandardButton.Yes:
            return

        def acao() -> None:
            self.empresa.cancelar_pedido(pedido)
            self.repo.salvar_pedido(pedido)

        if protegido(self, acao, "Pedido cancelado."):
            self.ao_alterar()

    def _confirmar_entrega(self) -> None:
        """RN22: quem recebe a mercadoria é quem atesta o recebimento."""
        pedido = self._pedido_selecionado()
        if pedido is None:
            return

        def acao() -> None:
            self.empresa.confirmar_entrega(pedido)
            self.repo.salvar_pedido(pedido)

        if protegido(
            self, acao, "Recebimento confirmado. Você já pode avaliar a empresa."
        ):
            self.ao_alterar()

    def _meu_pedido_mudou(self) -> None:
        pedido = self._pedido_selecionado()
        self._limpar(self.area_pedido_status)
        self.lst_itens_pedido.clear()

        if pedido is None:
            self.lbl_pedido_numero.setText("Nenhum pedido selecionado")
            self.lbl_pedido_info.setText("Selecione uma linha da tabela.")
            self.lbl_pedido_total.setText("")
            self.lbl_pedido_obs.setText("")
            for botao in (
                self.btn_avaliar,
                self.btn_ajustar,
                self.btn_cancelar,
                self.btn_confirmar,
            ):
                botao.setEnabled(False)
            return

        self.lbl_pedido_numero.setText(f"Pedido {pedido.id}")
        self.area_pedido_status.addWidget(pilula_status(pedido.status))
        self.lbl_pedido_info.setText(
            f"{pedido.marisqueira.nome if pedido.marisqueira else ''}\n"
            f"{pedido.endereco_entrega}\n"
            f"Prazo de {pedido.tempo_entrega_dias} dia(s) · "
            f"entrega {pedido.status_entrega.rotulo.lower()}"
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
            observacoes.append("Aguardando sua resposta ao ajuste solicitado.")
        if pedido.pode_confirmar_recebimento:
            observacoes.append(
                "A mercadoria saiu para entrega. Confirme o recebimento."
            )
        if pedido.motivo_rejeicao:
            observacoes.append(f"Rejeitado: {pedido.motivo_rejeicao}")
        if pedido.observacao_ajuste:
            observacoes.append(f"Ajuste pedido: {pedido.observacao_ajuste}")
        avaliacao = self._avaliacao_de(pedido)
        if avaliacao:
            nota = f"Sua avaliação: {avaliacao.estrelas}"
            if avaliacao.comentario:
                nota += f" {avaliacao.comentario}"
            observacoes.append(nota)
        self.lbl_pedido_obs.setText("\n".join(observacoes))

        # RN21: só após a entrega, e uma única vez por pedido.
        self.btn_avaliar.setEnabled(pedido.pode_ser_avaliado and avaliacao is None)
        # P7: ajustar e cancelar só fazem sentido enquanto a compradora tem a
        # decisão na mão. RN22: confirmar só depois do despacho.
        self.btn_ajustar.setEnabled(pedido.aguarda_resposta_da_compradora)
        self.btn_cancelar.setEnabled(pedido.pode_ser_cancelado)
        self.btn_confirmar.setEnabled(pedido.pode_confirmar_recebimento)

    def atualizar(self) -> None:
        self._recarregar_filtros()
        self._buscar()
        self._atualizar_meus_pedidos()
        self._atualizar_carrinho()
        self._meu_pedido_mudou()
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

    def _recarregar_filtros(self) -> None:
        """Repopula os combos de localização e empresa a partir do catálogo."""
        for combo, valores in (
            (self.f_localizacao, sorted({p.localizacao for p in self.repo.catalogo})),
            (self.f_empresa, self.repo.marisqueiras),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(TODAS, None)
            for valor in valores:
                combo.addItem(
                    valor if isinstance(valor, str) else valor.nome,
                    valor if not isinstance(valor, str) else valor,
                )
            combo.blockSignals(False)

    def _atualizar_meus_pedidos(self) -> None:
        self._pedidos_na_tabela = sorted(
            self.empresa.pedidos, key=lambda p: p.id or 0, reverse=True
        )
        entregues = sum(
            1 for p in self._pedidos_na_tabela if p.status is StatusPedido.ENTREGUE
        )
        gasto = sum(
            (
                p.total
                for p in self._pedidos_na_tabela
                if p.status is StatusPedido.ENTREGUE
            ),
            Decimal("0"),
        )

        self._limpar(self.area_metricas)
        self.area_metricas.addWidget(
            metrica("Pedidos", str(len(self._pedidos_na_tabela)))
        )
        self.area_metricas.addWidget(metrica("Entregues", str(entregues)))
        self.area_metricas.addWidget(metrica("Total comprado", reais(gasto)))
        self.area_metricas.addStretch()

        self.tbl_meus_pedidos.setRowCount(len(self._pedidos_na_tabela))
        for linha, pedido in enumerate(self._pedidos_na_tabela):
            avaliacao = self._avaliacao_de(pedido)
            self.tbl_meus_pedidos.setItem(
                linha, 0, celula(str(pedido.id or ""), negrito=True)
            )
            self.tbl_meus_pedidos.setItem(
                linha, 1, celula(pedido.marisqueira.nome if pedido.marisqueira else "")
            )
            self.tbl_meus_pedidos.setItem(
                linha, 2, celula_numero(str(len(pedido.itens)))
            )
            self.tbl_meus_pedidos.setItem(
                linha, 3, celula_numero(kg(pedido.quantidade_total_kg))
            )
            self.tbl_meus_pedidos.setItem(linha, 4, celula_numero(reais(pedido.total)))
            self.tbl_meus_pedidos.setItem(linha, 5, celula_status(pedido.status))
            self.tbl_meus_pedidos.setItem(
                linha, 6, celula_suave(avaliacao.estrelas if avaliacao else "")
            )
