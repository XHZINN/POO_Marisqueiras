"""Caixa de avisos de uma empresa, usada pelos dois perfis.

As duas pontas recebem avisos: a marisqueira quando chega ou é cancelado um
pedido, a compradora quando o pedido dela anda. Por isso o painel é um só,
parametrizado pela empresa.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from dominio.empresa import Empresa
from repositorio.repositorio import Repositorio
from ui.componentes import celula, celula_suave, metrica, tabela
from ui.estilo import PRIMARIA


class PainelNotificacoes(QWidget):
    def __init__(
        self, empresa: Empresa, repo: Repositorio, ao_alterar: Callable[[], None]
    ) -> None:
        super().__init__()
        self.empresa = empresa
        self.repo = repo
        self.ao_alterar = ao_alterar

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        self.area_metricas = QHBoxLayout()
        self.area_metricas.setSpacing(14)
        layout.addLayout(self.area_metricas)

        self.tbl_notificacoes = tabela(
            ["Quando", "Evento", "Mensagem", "Pedido"],
            largura_fixa={0: 130, 1: 190, 3: 80},
        )
        layout.addWidget(self.tbl_notificacoes)

        acoes = QHBoxLayout()
        self.btn_marcar_lidas = QPushButton("Marcar todas como lidas")
        self.btn_marcar_lidas.setObjectName("secundario")
        self.btn_marcar_lidas.clicked.connect(self._marcar_lidas)
        acoes.addWidget(self.btn_marcar_lidas)
        acoes.addStretch()
        layout.addLayout(acoes)

        self.atualizar()

    def _marcar_lidas(self) -> None:
        if self.repo.marcar_notificacoes_como_lidas(self.empresa):
            self.ao_alterar()

    def atualizar(self) -> None:
        while self.area_metricas.count():
            item = self.area_metricas.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        nao_lidas = self.empresa.total_nao_lidas
        self.area_metricas.addWidget(metrica("Não lidos", str(nao_lidas)))
        self.area_metricas.addWidget(
            metrica("Total", str(len(self.empresa.notificacoes)))
        )
        self.area_metricas.addStretch()
        self.btn_marcar_lidas.setEnabled(nao_lidas > 0)

        # Mais recentes primeiro: é o que interessa numa caixa de avisos.
        notificacoes = sorted(
            self.empresa.notificacoes, key=lambda n: n.criado_em, reverse=True
        )
        self.tbl_notificacoes.setRowCount(len(notificacoes))
        for linha, notificacao in enumerate(notificacoes):
            nova = notificacao.nao_lida
            cor = PRIMARIA if nova else None
            self.tbl_notificacoes.setItem(
                linha, 0, celula(f"{notificacao.criado_em:%d/%m %H:%M}", cor)
            )
            self.tbl_notificacoes.setItem(
                linha, 1, celula(notificacao.tipo.rotulo, cor, negrito=nova)
            )
            self.tbl_notificacoes.setItem(
                linha,
                2,
                celula(notificacao.mensagem, cor)
                if nova
                else celula_suave(notificacao.mensagem),
            )
            self.tbl_notificacoes.setItem(
                linha,
                3,
                celula(
                    str(notificacao.pedido.id)
                    if notificacao.pedido is not None and notificacao.pedido.id
                    else "",
                    cor,
                ),
            )
