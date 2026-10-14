"""Componentes e utilitários reutilizados pelas telas."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dominio.enums import SituacaoEmpresa, StatusPedido
from dominio.excecoes import ErroDeNegocio
from ui import estilo

# Cor de cada status. Fica aqui porque é apresentação; a exceção é o enum de
# RN20, que carrega cor porque o requisito nomeia as cores.
CORES_STATUS: dict[StatusPedido, tuple[str, str]] = {
    StatusPedido.AGUARDANDO_ANALISE: (estilo.LARANJA, estilo.LARANJA_FUNDO),
    StatusPedido.AJUSTE_SOLICITADO: (estilo.LARANJA, estilo.LARANJA_FUNDO),
    StatusPedido.ACEITO: (estilo.PRIMARIA, estilo.PRIMARIA_SUAVE),
    StatusPedido.EM_PREPARACAO: (estilo.PRIMARIA, estilo.PRIMARIA_SUAVE),
    StatusPedido.ENTREGUE: (estilo.VERDE, estilo.VERDE_FUNDO),
    StatusPedido.REJEITADO: (estilo.VERMELHO, estilo.VERMELHO_FUNDO),
}


def protegido(pai, acao: Callable[[], None], sucesso: str | None = None) -> bool:
    """Roda `acao` e transforma erro de negócio em aviso na tela.

    Único lugar da interface que trata erro de regra de negócio, e funciona
    porque tudo herda de `ErroDeNegocio`. TypeError e sqlite3.Error não são
    capturados de propósito: são bug, têm que estourar no terminal.
    """
    try:
        acao()
    except ErroDeNegocio as erro:
        QMessageBox.warning(pai, "Não foi possível concluir", str(erro))
        return False
    if sucesso:
        QMessageBox.information(pai, "Pronto", sucesso)
    return True


# Tabelas


def tabela(
    colunas: list[str], largura_fixa: dict[int, int] | None = None
) -> QTableWidget:
    """Cria uma tabela configurada para seleção por linha e somente leitura."""
    widget = QTableWidget(0, len(colunas))
    widget.setHorizontalHeaderLabels(colunas)
    widget.verticalHeader().setVisible(False)
    widget.verticalHeader().setDefaultSectionSize(44)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setShowGrid(False)
    widget.setFrameShape(QFrame.Shape.NoFrame)
    widget.setWordWrap(False)

    cabecalho = widget.horizontalHeader()
    cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    cabecalho.setHighlightSections(False)
    cabecalho.setFixedHeight(42)
    for indice, largura in (largura_fixa or {}).items():
        cabecalho.setSectionResizeMode(indice, QHeaderView.ResizeMode.Fixed)
        widget.setColumnWidth(indice, largura)
    return widget


def celula(
    texto: str,
    cor: str | None = None,
    negrito: bool = False,
    alinhamento: Qt.AlignmentFlag | None = None,
) -> QTableWidgetItem:
    item = QTableWidgetItem(texto)
    if cor:
        item.setForeground(QColor(cor))
    if negrito:
        fonte = item.font()
        fonte.setWeight(QFont.Weight.DemiBold)
        item.setFont(fonte)
    item.setTextAlignment(
        alinhamento
        if alinhamento is not None
        else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    return item


def celula_numero(texto: str, cor: str | None = None) -> QTableWidgetItem:
    """Números alinhados à direita, para as colunas comparáveis baterem na vertical."""
    return celula(
        texto,
        cor,
        alinhamento=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    )


def celula_suave(texto: str) -> QTableWidgetItem:
    return celula(texto, estilo.TEXTO_SUAVE)


def celula_situacao(situacao: SituacaoEmpresa) -> QTableWidgetItem:
    """RN20 e P33. A cor vem do próprio enum, não é escolhida aqui."""
    return celula(situacao.rotulo, situacao.cor, negrito=True)


def celula_status(status: StatusPedido) -> QTableWidgetItem:
    cor, _ = CORES_STATUS.get(status, (estilo.TEXTO, estilo.SUPERFICIE))
    return celula(status.rotulo, cor, negrito=True)


# Pílulas e cartões


def pilula(texto: str, cor_texto: str, cor_fundo: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setStyleSheet(
        f"background-color: {cor_fundo}; color: {cor_texto};"
        "border-radius: 11px; padding: 4px 11px;"
        "font-size: 12px; font-weight: 700;"
    )
    etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return etiqueta


def pilula_situacao(situacao: SituacaoEmpresa) -> QLabel:
    """RN20 e P33: disponível, estoque baixo, fora do horário."""
    fundos = {
        SituacaoEmpresa.DISPONIVEL: estilo.VERDE_FUNDO,
        SituacaoEmpresa.ESTOQUE_BAIXO: estilo.LARANJA_FUNDO,
        SituacaoEmpresa.FORA_DE_HORARIO: estilo.VERMELHO_FUNDO,
    }
    return pilula(situacao.rotulo, situacao.cor, fundos[situacao])


def pilula_status(status: StatusPedido) -> QLabel:
    cor, fundo = CORES_STATUS.get(status, (estilo.TEXTO, estilo.SUPERFICIE_ALT))
    return pilula(status.rotulo, cor, fundo)


def cartao(margem: int = 20, espacamento: int = 14) -> tuple[QFrame, QVBoxLayout]:
    """Superfície branca com borda, usada para agrupar conteúdo."""
    moldura = QFrame()
    moldura.setObjectName("cartao")
    layout = QVBoxLayout(moldura)
    layout.setContentsMargins(margem, margem, margem, margem)
    layout.setSpacing(espacamento)
    return moldura, layout


def metrica(rotulo: str, valor: str) -> QFrame:
    """Cartão compacto com um número em destaque e seu rótulo."""
    moldura, layout = cartao(margem=16, espacamento=2)
    etiqueta_valor = QLabel(valor)
    etiqueta_valor.setObjectName("metricaValor")
    etiqueta_rotulo = QLabel(rotulo.upper())
    etiqueta_rotulo.setObjectName("metricaRotulo")
    layout.addWidget(etiqueta_valor)
    layout.addWidget(etiqueta_rotulo)
    return moldura


def divisor() -> QFrame:
    linha = QFrame()
    linha.setObjectName("divisor")
    linha.setFixedHeight(1)
    return linha


def rotulo_secao(texto: str) -> QLabel:
    etiqueta = QLabel(texto.upper())
    etiqueta.setObjectName("secao")
    return etiqueta


def espacador(altura: int) -> QWidget:
    vazio = QWidget()
    vazio.setFixedHeight(altura)
    return vazio


# Formatação


def reais(valor: Decimal) -> str:
    """Formata no padrão brasileiro: R$ 1.234,56."""
    inteiro, _, centavos = f"{Decimal(valor):.2f}".partition(".")
    milhares = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {milhares},{centavos}"


def kg(valor: Decimal) -> str:
    valor = Decimal(valor)
    texto = (
        f"{valor.normalize():f}"
        if valor == valor.to_integral_value()
        else f"{valor:.2f}"
    )
    return f"{texto} kg"


def estrelas(nota: Decimal) -> str:
    """RN11 e P24: nota média em estrelas."""
    nota = Decimal(nota)
    if nota <= 0:
        return "Sem avaliação"
    cheias = int(nota)
    return "★" * cheias + "☆" * (5 - cheias) + f" {nota}"
