"""Cadastro de endereços de entrega da compradora (extensão além de RN13).

RN13 trata o endereço como campo do pedido, digitado de novo a cada compra.
Aqui ele vira cadastro: a compradora guarda os endereços com apelido, marca
um como principal e, na hora de comprar, só escolhe. É o que os serviços de
entrega fazem, e evita erro de digitação no destino de uma carga.

A coordenada vem de dois caminhos: a busca pelo Nominatim
(`geo/geocodificacao.py`), que lê o endereço escrito, e o clique no mapa, pra
quando o cadastro é de um lugar que o geocodificador não acha — porto, ponto
de descarga, casa sem número. Com ou sem ela o endereço vale; sem ela é que
não entra no mapa nem no cálculo do prazo.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dominio.empresa import EmpresaCompradora
from dominio.endereco import SEM_NUMERO, Endereco
from dominio.excecoes import DadoObrigatorio
from geo.geocodificacao import geocodificar
from repositorio.repositorio import Repositorio
from ui.componentes import cartao, protegido, rolavel, rotulo_secao
from ui.estilo import TEXTO_SUAVE, VERDE, VERMELHO
from ui.mapa_web import MapaWeb


class DialogoEnderecos(QDialog):
    """Lista, cadastra, edita e remove os endereços de entrega."""

    # Borda do item e folga pro cursor: o widget de dentro tem essa largura
    # a menos que o viewport da lista.
    RECUO_ITEM = 8
    # Margens do widget de cada item, repetidas aqui porque a altura da linha
    # é calculada à mão (o Qt não sabe quebrar o texto sozinho num item).
    MARGEM_ITEM_H = 13
    MARGEM_ITEM_V = 10
    ESPACO_ITEM = 3
    # O QSS reserva margem embaixo e borda em volta do item, e o widget recebe
    # o retângulo já sem isso: a altura pedida precisa devolver o desconto.
    SOBRA_ITEM = 14

    def __init__(self, pai, empresa: EmpresaCompradora, repo: Repositorio) -> None:
        super().__init__(pai)
        self.empresa = empresa
        self.repo = repo
        # Endereço sendo editado. None significa que o formulário é de cadastro.
        self.editando: Endereco | None = None

        self.setWindowTitle("Endereços de entrega")
        # Só a largura é fixada: a altura mínima quem decide é o layout, e
        # travar um número menor que ele espremia os campos uns sobre os outros.
        self.setMinimumWidth(900)
        # A altura mínima quem calcula é o layout: fixar um número aqui
        # autoriza o Qt a encolher a janela abaixo do que os cartões pedem,
        # e aí o mapa passa por cima do texto da coordenada. O que se escolhe
        # é só o tamanho de abertura, com teto na tela de quem usa.
        tela = self.screen().availableGeometry()
        self.resize(min(1080, tela.width() - 80), min(880, int(tela.height() * 0.8)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Endereços de entrega")
        titulo.setObjectName("titulo")
        layout.addWidget(titulo)
        subtitulo = QLabel(
            "O pedido usa o endereço marcado como principal. A busca de "
            "coordenada põe o endereço no mapa e no cálculo do prazo."
        )
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        layout.addWidget(subtitulo)

        # Mapa embaixo da lista, não dentro do formulário: a coluna da
        # esquerda sobrava altura vazia e a da direita vivia espremida, com
        # o mapa sempre meio escondido atrás da barra de rolagem.
        esquerda = QVBoxLayout()
        esquerda.setSpacing(14)
        esquerda.addWidget(self._coluna_lista(), 2)
        esquerda.addWidget(self._coluna_mapa(), 3)

        corpo = QHBoxLayout()
        corpo.setSpacing(16)
        corpo.addLayout(esquerda, 1)
        # O formulário rola: em tela baixa o Qt espremia tudo abaixo do
        # mínimo e os campos chegavam a cortar o texto digitado. Com a
        # rolagem, falta de altura vira barra, não widget torto.
        corpo.addWidget(rolavel(self._coluna_formulario()), 1)
        layout.addLayout(corpo, 1)

        rodape = QHBoxLayout()
        rodape.addStretch()
        fechar = QPushButton("Fechar")
        fechar.setObjectName("secundario")
        fechar.clicked.connect(self.accept)
        rodape.addWidget(fechar)
        layout.addLayout(rodape)

        self.recarregar()

    # montagem

    def _coluna_lista(self):
        moldura, caixa = cartao()
        caixa.addWidget(rotulo_secao("Cadastrados"))
        self.lista = QListWidget()
        # O endereço inteiro cabe em duas linhas; barra horizontal numa lista
        # de endereços só esconde a metade que importa.
        self.lista.setWordWrap(True)
        # Dois endereços de duas linhas cabem aqui; abaixo disso a lista vira
        # uma fresta e o cadastro seguinte fica escondido na rolagem.
        self.lista.setMinimumHeight(150)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista.currentRowChanged.connect(self._selecionou)
        # A altura do item depende da largura disponível, e quem sabe a largura
        # de verdade é o viewport — o resize do diálogo chega antes do layout.
        self.lista.viewport().installEventFilter(self)
        caixa.addWidget(self.lista, 1)

        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        self.btn_principal = QPushButton("Tornar principal")
        self.btn_principal.setObjectName("secundario")
        self.btn_principal.clicked.connect(self._tornar_principal)
        self.btn_remover = QPushButton("Remover")
        self.btn_remover.setObjectName("secundario")
        self.btn_remover.clicked.connect(self._remover)
        self.btn_novo = QPushButton("Novo endereço")
        self.btn_novo.setObjectName("secundario")
        self.btn_novo.clicked.connect(self._novo)
        botoes.addWidget(self.btn_novo)
        botoes.addWidget(self.btn_principal)
        botoes.addWidget(self.btn_remover)
        caixa.addLayout(botoes)
        return moldura

    def _coluna_mapa(self):
        moldura, caixa = cartao()
        caixa.addWidget(rotulo_secao("Local no mapa"))
        # Mapa navegável: dá zoom, arrasta e aceita o clique que crava o pino.
        # É o que resolve o endereço que o Nominatim erra ou não conhece.
        self.mapa = MapaWeb(seletor=True)
        self.mapa.vazio = "Busque o endereço para ver no mapa"
        # O piso do mapa acompanha a tela: em monitor normal ele já nasce em
        # tamanho de mapa, em notebook baixo ele cede altura em vez de
        # empurrar o diálogo pra fora da tela — e diálogo maior que a tela é
        # o que faz o Qt espremer os cartões e o mapa escrever por cima da
        # coordenada. Acima do piso quem manda é o esticamento da coluna.
        tela = self.screen().availableGeometry().height()
        self.mapa.setMinimumHeight(260 if tela >= 900 else 180)
        self.mapa.ponto_escolhido.connect(self._marcou_no_mapa)
        # Fator 1: o mapa é quem cresce quando a janela sobe, em vez de sobrar
        # espaço vazio no fim do cartão.
        caixa.addWidget(self.mapa, 1)

        self.lbl_coordenada = QLabel("Sem coordenada")
        self.lbl_coordenada.setObjectName("meta")
        self.lbl_coordenada.setWordWrap(True)
        # Altura travada em três linhas, e travada aqui e não no showEvent:
        # rótulo que quebra texto muda de altura a cada mensagem, e o Qt
        # aproveitava a mudança pra redimensionar o diálogo no meio do uso.
        # Fixar depois que a janela já abriu é pior ainda — o Wayland ajusta
        # a janela uma vez só, e as 28 px que faltavam viravam mapa escrito
        # por cima da coordenada. O ensurePolished é pra conta sair com a
        # fonte do tema, não com a fonte padrão do Qt.
        self.lbl_coordenada.ensurePolished()
        self.lbl_coordenada.setFixedHeight(
            3 * self.lbl_coordenada.fontMetrics().lineSpacing()
        )
        caixa.addWidget(self.lbl_coordenada)
        return moldura

    def _coluna_formulario(self):
        moldura, caixa = cartao()
        self.lbl_form = rotulo_secao("Novo endereço")
        caixa.addWidget(self.lbl_form)

        self.in_apelido = QLineEdit()
        self.in_apelido.setPlaceholderText("Ex: Restaurante, Depósito, Matriz")
        self.in_logradouro = QLineEdit()
        self.in_logradouro.setPlaceholderText("Ex: Rua do Giz, Avenida Litorânea")
        self.in_numero = QLineEdit()
        self.in_numero.setPlaceholderText("Ex: 120")
        # Sem número não é campo vazio: é informação. Quem mora em sítio ou
        # galpão sem placa precisa marcar isso, senão não consegue salvar.
        self.chk_sem_numero = QCheckBox("S/N")
        self.chk_sem_numero.setToolTip("Marque se o imóvel não tem número.")
        self.chk_sem_numero.toggled.connect(self._alternar_numero)
        # Guarda o que estava digitado antes do S/N, pra devolver ao desmarcar.
        self._numero_digitado = ""
        self.in_complemento = QLineEdit()
        self.in_complemento.setPlaceholderText("Ex: Loja 2, Galpão B")
        self.in_bairro = QLineEdit()
        self.in_bairro.setPlaceholderText("Ex: Centro")
        self.in_cidade = QLineEdit()
        self.in_cidade.setText("São Luís")
        self.in_uf = QLineEdit("MA")
        self.in_uf.setMaxLength(2)
        self.in_uf.setMaximumWidth(90)
        self.in_cep = QLineEdit()
        self.in_cep.setPlaceholderText("00000-000")
        self.in_referencia = QLineEdit()
        self.in_referencia.setPlaceholderText("Ex: esquina com a Rua da Estrela")

        # Grade em vez de formulário de uma coluna só: nove campos empilhados
        # deixam o diálogo mais alto que a tela e espremem o mapa. Os campos
        # curtos andam em pares, que é como endereço se escreve mesmo.
        formulario = QGridLayout()
        formulario.setHorizontalSpacing(12)
        formulario.setVerticalSpacing(9)
        formulario.setColumnStretch(1, 1)
        formulario.setColumnStretch(3, 1)
        self._linha_larga(formulario, 0, "Apelido", self.in_apelido)
        # "Logradouro" é palavra de formulário de cartório; quem preenche
        # pensa em rua e avenida.
        self._linha_larga(formulario, 1, "Rua / Av.", self.in_logradouro)
        self._par(
            formulario,
            2,
            "Número",
            self._caixa_numero(),
            "Complemento",
            self.in_complemento,
        )
        self._par(formulario, 3, "Bairro", self.in_bairro, "CEP", self.in_cep)
        self._par(formulario, 4, "Cidade", self.in_cidade, "UF", self.in_uf)
        self._linha_larga(formulario, 5, "Referência", self.in_referencia)
        caixa.addLayout(formulario)

        caixa.addStretch()

        acoes = QHBoxLayout()
        acoes.setSpacing(8)
        self.btn_buscar = QPushButton("Buscar no mapa")
        self.btn_buscar.setObjectName("secundario")
        self.btn_buscar.clicked.connect(self._geocodificar)
        self.btn_salvar = QPushButton("Salvar endereço")
        self.btn_salvar.clicked.connect(self._salvar)
        acoes.addWidget(self.btn_buscar)
        acoes.addStretch()
        acoes.addWidget(self.btn_salvar)
        caixa.addLayout(acoes)

        # Coordenada achada pela busca, aplicada quando salva.
        self._coordenada = None
        return moldura

    def _caixa_numero(self) -> QWidget:
        """Campo do número com a marca de S/N ao lado."""
        moldura = QWidget()
        caixa = QHBoxLayout(moldura)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(8)
        caixa.addWidget(self.in_numero, 1)
        caixa.addWidget(self.chk_sem_numero)
        return moldura

    def _alternar_numero(self, marcado: bool) -> None:
        if marcado:
            if self.in_numero.text().strip() != SEM_NUMERO:
                self._numero_digitado = self.in_numero.text()
            self.in_numero.setText(SEM_NUMERO)
        else:
            self.in_numero.setText(self._numero_digitado)
        self.in_numero.setEnabled(not marcado)

    @staticmethod
    def _linha_larga(grade: QGridLayout, linha: int, texto: str, campo) -> None:
        grade.addWidget(QLabel(texto), linha, 0)
        grade.addWidget(campo, linha, 1, 1, 3)

    @staticmethod
    def _par(grade, linha: int, texto1: str, campo1, texto2: str, campo2) -> None:
        grade.addWidget(QLabel(texto1), linha, 0)
        grade.addWidget(campo1, linha, 1)
        grade.addWidget(QLabel(texto2), linha, 2)
        grade.addWidget(campo2, linha, 3)

    # lista

    def recarregar(self) -> None:
        self.lista.blockSignals(True)
        self.lista.clear()
        for endereco in self.empresa.enderecos:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, endereco)
            if not endereco.tem_coordenada:
                item.setToolTip("Sem coordenada: não entra no mapa nem no prazo.")
            self.lista.addItem(item)
            # Widget próprio em vez de um texto com "\n": o item de lista elide
            # o texto inteiro quando ele não cabe numa linha, e o endereço
            # sumia justo da entrada selecionada, que é a mais larga.
            self.lista.setItemWidget(item, self._linha_lista(endereco))
        self.lista.blockSignals(False)
        self._ajustar_alturas()
        self._atualizar_botoes()

    def _linha_lista(self, endereco: Endereco) -> QWidget:
        """Duas linhas: o apelido em negrito e o endereço por extenso."""
        moldura = QWidget()
        # O cartão branco é desenhado pelo item; o widget por cima tem que ser
        # transparente, senão traz o cinza do fundo da aplicação junto.
        moldura.setStyleSheet("background: transparent;")
        caixa = QVBoxLayout(moldura)
        # A margem é daqui e não do QSS: o item de lista entrega o retângulo
        # inteiro pro widget, então padding no estilo só faria o texto vazar.
        caixa.setContentsMargins(
            self.MARGEM_ITEM_H,
            self.MARGEM_ITEM_V,
            self.MARGEM_ITEM_H,
            self.MARGEM_ITEM_V,
        )
        caixa.setSpacing(self.ESPACO_ITEM)

        marca = " · principal" if endereco.principal else ""
        titulo = QLabel(f"{endereco.apelido}{marca}")
        fonte = titulo.font()
        fonte.setBold(True)
        titulo.setFont(fonte)
        caixa.addWidget(titulo)

        detalhe = QLabel(endereco.linha)
        detalhe.setObjectName("meta")
        detalhe.setWordWrap(True)
        caixa.addWidget(detalhe)
        # Guardados pra conta da altura: é o rótulo quem sabe em quantas
        # linhas o endereço cabe numa dada largura.
        moldura.titulo = titulo
        moldura.detalhe = detalhe
        return moldura

    def _ajustar_alturas(self) -> None:
        """Dá a cada item a altura do texto já quebrado na largura da lista."""
        largura = self.lista.viewport().width() - self.RECUO_ITEM
        if largura <= 0:
            return
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            widget = self.lista.itemWidget(item)
            if widget is None:
                continue
            # Sem o polish o rótulo ainda está com a fonte padrão, menor que a
            # do QSS, e a conta sai curta: o texto vaza por baixo do cartão.
            widget.ensurePolished()
            widget.titulo.ensurePolished()
            widget.detalhe.ensurePolished()
            texto = largura - 2 * self.MARGEM_ITEM_H
            altura = (
                self.SOBRA_ITEM
                + 2 * self.MARGEM_ITEM_V
                + self.ESPACO_ITEM
                + widget.titulo.sizeHint().height()
                + widget.detalhe.heightForWidth(texto)
            )
            item.setSizeHint(QSize(largura, altura))

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802, nome do Qt
        if objeto is self.lista.viewport() and evento.type() is QEvent.Type.Resize:
            self._ajustar_alturas()
        return super().eventFilter(objeto, evento)

    def _selecionado(self) -> Endereco | None:
        item = self.lista.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selecionou(self) -> None:
        endereco = self._selecionado()
        self._atualizar_botoes()
        if endereco is not None:
            self._preencher(endereco)

    def _atualizar_botoes(self) -> None:
        tem = self._selecionado() is not None
        self.btn_principal.setEnabled(tem)
        # A única entrega cadastrada não pode sair: o pedido ficaria sem destino.
        self.btn_remover.setEnabled(tem and len(self.empresa.enderecos) > 1)

    # formulário

    def _campos(self) -> tuple[QLineEdit, ...]:
        return (
            self.in_apelido,
            self.in_logradouro,
            self.in_numero,
            self.in_complemento,
            self.in_bairro,
            self.in_cidade,
            self.in_uf,
            self.in_cep,
            self.in_referencia,
        )

    def _novo(self) -> None:
        self.editando = None
        self.lista.setCurrentRow(-1)
        self._numero_digitado = ""
        self.chk_sem_numero.setChecked(False)
        for campo in self._campos():
            if campo not in (self.in_cidade, self.in_uf):
                campo.clear()
        self.in_cidade.setText("São Luís")
        self.in_uf.setText("MA")
        self._coordenada = None
        self.lbl_form.setText("NOVO ENDEREÇO")
        self.btn_salvar.setText("Salvar endereço")
        self._mostrar_coordenada()

    def _preencher(self, endereco: Endereco) -> None:
        self.editando = endereco
        self.in_apelido.setText(endereco.apelido)
        self.in_logradouro.setText(endereco.logradouro)
        self.chk_sem_numero.setChecked(endereco.sem_numero)
        self.in_numero.setText(endereco.numero)
        self.in_complemento.setText(endereco.complemento or "")
        self.in_bairro.setText(endereco.bairro)
        self.in_cidade.setText(endereco.cidade)
        self.in_uf.setText(endereco.uf)
        self.in_cep.setText(endereco.cep or "")
        self.in_referencia.setText(endereco.referencia or "")
        # Campo preenchido fica rolado no fim do texto; voltar o cursor pro
        # começo é o que faz o CEP aparecer inteiro em vez de cortado.
        for campo in self._campos():
            campo.setCursorPosition(0)
        self._coordenada = endereco.coordenada
        self.lbl_form.setText(f"EDITANDO · {endereco.apelido.upper()}")
        self.btn_salvar.setText("Salvar alterações")
        self._mostrar_coordenada()

    def _marcou_no_mapa(self, coordenada) -> None:
        """Clique ou arrasto no mapa: o pino manda, e o texto só acompanha."""
        self._coordenada = coordenada
        # Sem redesenhar: a página já pôs o pino onde a pessoa soltou, e
        # recentralizar no meio do arrasto faz o mapa pular na mão dela.
        self._mostrar_coordenada("Ponto marcado por você no mapa.", redesenhar=False)

    def _mostrar_coordenada(
        self, achado: str | None = None, redesenhar: bool = True
    ) -> None:
        if redesenhar:
            self.mapa.definir_ponto(
                self._coordenada, self.in_apelido.text() or "Entrega"
            )
        if self._coordenada is None:
            self._dizer(
                "Sem coordenada: o endereço vale, mas fica fora do mapa e do "
                "cálculo do prazo. Busque pelo texto ou clique no mapa.",
                TEXTO_SUAVE,
            )
            return
        texto = f"Coordenada: {self._coordenada}"
        if achado:
            texto += f"\n{achado}"
        self._dizer(texto, VERDE)

    def _dizer(self, texto: str, cor: str) -> None:
        """Escreve no rótulo da coordenada; o texto inteiro vai na dica.

        O rótulo tem altura fixa de três linhas, então mensagem comprida —
        um endereço normalizado do Nominatim, por exemplo — sobra; quem
        quiser ler o resto passa o mouse.
        """
        self.lbl_coordenada.setText(texto)
        self.lbl_coordenada.setToolTip(texto)
        self.lbl_coordenada.setStyleSheet(f"color: {cor};")

    def _montar(self) -> Endereco:
        """Monta o Endereco com o que está no formulário. Valida no domínio."""
        return Endereco(
            apelido=self.in_apelido.text(),
            logradouro=self.in_logradouro.text(),
            numero=self.in_numero.text(),
            bairro=self.in_bairro.text(),
            cidade=self.in_cidade.text(),
            uf=self.in_uf.text(),
            cep=self.in_cep.text(),
            complemento=self.in_complemento.text(),
            referencia=self.in_referencia.text(),
            coordenada=self._coordenada,
        )

    def _geocodificar(self) -> None:
        """Busca a coordenada do endereço digitado."""
        try:
            consulta = self._montar().consulta_geocodificacao
        except DadoObrigatorio:
            # Endereço ainda incompleto: busca com o que já foi digitado.
            partes = [
                self.in_logradouro.text(),
                self.in_numero.text(),
                self.in_bairro.text(),
                self.in_cidade.text(),
                self.in_uf.text() or "MA",
                "Brasil",
            ]
            consulta = ", ".join(p.strip() for p in partes if p and p.strip())

        self.btn_buscar.setEnabled(False)
        self.btn_buscar.setText("Buscando…")
        self.repaint()
        try:
            achado = geocodificar(consulta)
        finally:
            self.btn_buscar.setEnabled(True)
            self.btn_buscar.setText("Buscar no mapa")

        if achado is None:
            self.mapa.definir_ponto(None)
            self._dizer(
                "Não encontrei este endereço. Confira a rua e a cidade, ou "
                "clique no mapa para marcar o ponto.",
                VERMELHO,
            )
            return
        self._coordenada, descricao = achado
        self._mostrar_coordenada(descricao)

    def _salvar(self) -> None:
        anterior = self.editando

        def acao() -> None:
            novo = self._montar()
            if anterior is None:
                self.empresa.adicionar_endereco(novo)
            else:
                # Edição troca os campos no objeto que já está na lista, pra
                # não perder o id nem a posição de principal.
                if novo.apelido.casefold() != anterior.apelido.casefold():
                    if self._apelido_repetido(novo.apelido, anterior):
                        raise DadoObrigatorio(
                            f"Já existe um endereço com o apelido '{novo.apelido}'."
                        )
                anterior.apelido = novo.apelido
                anterior.logradouro = novo.logradouro
                anterior.numero = novo.numero
                anterior.bairro = novo.bairro
                anterior.cidade = novo.cidade
                anterior.uf = novo.uf
                anterior.cep = novo.cep
                anterior.complemento = novo.complemento
                anterior.referencia = novo.referencia
                anterior.coordenada = novo.coordenada
            self.repo.salvar_enderecos(self.empresa)

        if protegido(self, acao):
            self.recarregar()
            self._novo()

    def _apelido_repetido(self, apelido: str, menos: Endereco) -> bool:
        return any(
            e is not menos and e.apelido.casefold() == apelido.casefold()
            for e in self.empresa.enderecos
        )

    def _tornar_principal(self) -> None:
        endereco = self._selecionado()
        if endereco is None:
            return

        def acao() -> None:
            self.empresa.definir_endereco_principal(endereco)
            self.repo.salvar_enderecos(self.empresa)

        if protegido(self, acao):
            self.recarregar()

    def _remover(self) -> None:
        endereco = self._selecionado()
        if endereco is None:
            return
        resposta = QMessageBox.question(
            self,
            "Remover endereço",
            f"Remover '{endereco.apelido}'? Os pedidos antigos continuam com o "
            "endereço que foi usado na época.",
        )
        if resposta is not QMessageBox.StandardButton.Yes:
            return

        def acao() -> None:
            self.empresa.remover_endereco(endereco)
            self.repo.salvar_enderecos(self.empresa)

        if protegido(self, acao):
            self.recarregar()
            self._novo()
