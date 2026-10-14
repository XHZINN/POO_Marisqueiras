"""Janela principal: seleção de perfil e navegação entre os painéis.

RN01 e P6: só empresas operam a plataforma, então a tela inicial oferece
exatamente dois caminhos, entrar como empresa das marisqueiras ou como
empresa compradora. Não existe perfil de consumidor final.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dominio.empresa import Empresa, EmpresaCompradora, EmpresaMarisqueira
from repositorio.repositorio import Repositorio
from ui.componentes import estrelas, pilula_situacao, rotulo_secao
from ui.painel_compradora import PainelCompradora
from ui.painel_marisqueira import PainelMarisqueira


class JanelaPrincipal(QMainWindow):
    def __init__(self, repo: Repositorio) -> None:
        super().__init__()
        self.repo = repo
        self.empresa_atual: Empresa | None = None
        self.painel: QWidget | None = None

        self.setWindowTitle("Marisquês")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 700)

        self.pilha = QStackedWidget()
        self.setCentralWidget(self.pilha)

        self.tela_perfis = self._tela_perfis()
        self.tela_painel = self._tela_painel()
        self.pilha.addWidget(self.tela_perfis)
        self.pilha.addWidget(self.tela_painel)

        self._listar_perfis()

    # Faixa de marca

    def _faixa(self, acao: QPushButton | None = None) -> QFrame:
        faixa = QFrame()
        faixa.setObjectName("faixa")
        faixa.setFixedHeight(56)
        layout = QHBoxLayout(faixa)
        layout.setContentsMargins(28, 0, 24, 0)

        marca = QLabel("MARISQUÊS")
        marca.setObjectName("marca")
        layout.addWidget(marca)

        self._identidade = QLabel()
        self._identidade.setStyleSheet("color: #8FB5B2; font-size: 13px;")
        layout.addSpacing(16)
        layout.addWidget(self._identidade)
        layout.addStretch()

        if acao is not None:
            layout.addWidget(acao)
        return faixa

    # Tela de seleção de perfil

    def _tela_perfis(self) -> QWidget:
        pagina = QWidget()
        raiz = QVBoxLayout(pagina)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._faixa())

        corpo = QWidget()
        layout = QVBoxLayout(corpo)
        layout.setContentsMargins(40, 34, 40, 32)
        layout.setSpacing(4)

        titulo = QLabel("Escolha um perfil")
        titulo.setObjectName("titulo")
        subtitulo = QLabel(
            "Comercialização direta de mariscos entre empresas. "
            "Vila Maresia, Raposa, Maranhão."
        )
        subtitulo.setObjectName("subtitulo")
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(26)

        colunas = QHBoxLayout()
        colunas.setSpacing(26)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(12)
        esquerda.addWidget(rotulo_secao("Empresas das marisqueiras"))
        self.lst_marisqueiras = QListWidget()
        self.lst_marisqueiras.setSpacing(0)
        self.lst_marisqueiras.itemDoubleClicked.connect(
            lambda: self._entrar(self.lst_marisqueiras, self.repo.marisqueiras)
        )
        esquerda.addWidget(self.lst_marisqueiras)
        botao_m = QPushButton("Entrar como marisqueira")
        botao_m.clicked.connect(
            lambda: self._entrar(self.lst_marisqueiras, self.repo.marisqueiras)
        )
        esquerda.addWidget(botao_m)

        direita = QVBoxLayout()
        direita.setSpacing(12)
        direita.addWidget(rotulo_secao("Empresas compradoras"))
        self.lst_compradoras = QListWidget()
        self.lst_compradoras.setSpacing(0)
        self.lst_compradoras.itemDoubleClicked.connect(
            lambda: self._entrar(self.lst_compradoras, self.repo.compradoras)
        )
        direita.addWidget(self.lst_compradoras)
        botao_c = QPushButton("Entrar como compradora")
        botao_c.clicked.connect(
            lambda: self._entrar(self.lst_compradoras, self.repo.compradoras)
        )
        direita.addWidget(botao_c)

        colunas.addLayout(esquerda)
        colunas.addLayout(direita)
        layout.addLayout(colunas)
        raiz.addWidget(corpo)
        return pagina

    def _cartao_empresa(
        self, nome: str, meta: str, extra: str = "", situacao=None
    ) -> QWidget:
        """Conteúdo de um item da lista, desenhado como cartão.

        O fundo fica transparente para que o estilo do item da lista, que é
        quem pinta a borda e o destaque de seleção, apareça por baixo.
        """
        cartao = QWidget()
        cartao.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(cartao)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        texto = QVBoxLayout()
        texto.setSpacing(3)
        etiqueta_nome = QLabel(nome)
        etiqueta_nome.setObjectName("nomeEmpresa")
        etiqueta_meta = QLabel(meta)
        etiqueta_meta.setObjectName("meta")
        texto.addWidget(etiqueta_nome)
        texto.addWidget(etiqueta_meta)
        if extra:
            etiqueta_extra = QLabel(extra)
            etiqueta_extra.setObjectName("meta")
            texto.addWidget(etiqueta_extra)
        layout.addLayout(texto)
        layout.addStretch()

        if situacao is not None:
            coluna = QVBoxLayout()
            coluna.addWidget(pilula_situacao(situacao))
            coluna.addStretch()
            layout.addLayout(coluna)
        return cartao

    def _listar_perfis(self) -> None:
        self.lst_marisqueiras.clear()
        for empresa in self.repo.marisqueiras:
            produtos = len(empresa.produtos)
            cartao = self._cartao_empresa(
                nome=empresa.nome,
                meta=f"{empresa.localizacao} · {produtos} produto(s)",
                extra=estrelas(empresa.media_avaliacoes),
                situacao=empresa.situacao,
            )
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, cartao.sizeHint().height() + 10))
            item.setToolTip(f"{empresa.tipo()} · CNPJ {empresa.cnpj}")
            self.lst_marisqueiras.addItem(item)
            self.lst_marisqueiras.setItemWidget(item, cartao)

        self.lst_compradoras.clear()
        for empresa in self.repo.compradoras:
            cartao = self._cartao_empresa(
                nome=empresa.nome,
                meta=f"{empresa.localizacao} · {len(empresa.pedidos)} pedido(s)",
                extra=empresa.endereco,
            )
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, cartao.sizeHint().height() + 10))
            item.setToolTip(f"{empresa.tipo()} · CNPJ {empresa.cnpj}")
            self.lst_compradoras.addItem(item)
            self.lst_compradoras.setItemWidget(item, cartao)

    # Tela do painel

    def _tela_painel(self) -> QWidget:
        pagina = QWidget()
        raiz = QVBoxLayout(pagina)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        botao_trocar = QPushButton("Trocar perfil")
        botao_trocar.clicked.connect(self._voltar_para_perfis)
        raiz.addWidget(self._faixa(botao_trocar))

        corpo = QWidget()
        layout = QVBoxLayout(corpo)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(14)

        cabecalho = QHBoxLayout()
        identificacao = QVBoxLayout()
        identificacao.setSpacing(2)
        self.lbl_empresa = QLabel()
        self.lbl_empresa.setObjectName("titulo")
        self.lbl_papel = QLabel()
        self.lbl_papel.setObjectName("subtitulo")
        identificacao.addWidget(self.lbl_empresa)
        identificacao.addWidget(self.lbl_papel)
        cabecalho.addLayout(identificacao)
        cabecalho.addStretch()
        self.area_indicador = QHBoxLayout()
        cabecalho.addLayout(self.area_indicador)
        layout.addLayout(cabecalho)

        self.area_painel = QVBoxLayout()
        self.area_painel.setContentsMargins(0, 0, 0, 0)
        container = QWidget()
        container.setLayout(self.area_painel)
        layout.addWidget(container)
        raiz.addWidget(corpo)
        return pagina

    def _entrar(self, lista: QListWidget, empresas: list) -> None:
        indice = lista.currentRow()
        if indice < 0 or indice >= len(empresas):
            return
        self.empresa_atual = empresas[indice]
        self._montar_painel()
        self.pilha.setCurrentWidget(self.tela_painel)

    def _montar_painel(self) -> None:
        empresa = self.empresa_atual
        if empresa is None:
            return

        if self.painel is not None:
            self.area_painel.removeWidget(self.painel)
            self.painel.deleteLater()
            self.painel = None

        self.lbl_empresa.setText(empresa.nome)
        self.lbl_papel.setText(f"{empresa.tipo()} · {empresa.localizacao}")
        self._identidade.setText(empresa.nome)

        while self.area_indicador.count():
            item = self.area_indicador.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        # Polimorfismo: a janela só escolhe qual painel construir pelo tipo
        # da empresa, não sabe o que cada um faz.
        if isinstance(empresa, EmpresaMarisqueira):
            self.area_indicador.addWidget(pilula_situacao(empresa.situacao))
            self.painel = PainelMarisqueira(empresa, self.repo, self.recarregar)
        elif isinstance(empresa, EmpresaCompradora):
            self.painel = PainelCompradora(empresa, self.repo, self.recarregar)
        else:  # pragma: no cover, Empresa é abstrata
            return
        self.area_painel.addWidget(self.painel)

    def _voltar_para_perfis(self) -> None:
        self._identidade.setText("")
        self._listar_perfis()
        self.pilha.setCurrentWidget(self.tela_perfis)

    def recarregar(self) -> None:
        """Chamada pelos painéis após qualquer operação que altere dados.

        Uma operação de uma empresa muda o que a outra vê, porque aceitar um
        pedido baixa estoque que aparece na busca da compradora. Por isso a
        atualização é da tela inteira, não só do widget que disparou a ação.
        """
        if self.painel is not None and hasattr(self.painel, "atualizar"):
            self.painel.atualizar()
        if isinstance(self.empresa_atual, EmpresaMarisqueira):
            while self.area_indicador.count():
                item = self.area_indicador.takeAt(0)
                if item.widget() is not None:
                    item.widget().deleteLater()
            self.area_indicador.addWidget(pilula_situacao(self.empresa_atual.situacao))
        self._listar_perfis()

    def closeEvent(self, evento) -> None:  # noqa: N802, nome exigido pelo Qt
        self.repo.fechar()
        super().closeEvent(evento)
