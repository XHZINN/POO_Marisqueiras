"""Simulação da entrega do ponto A ao ponto B (extensão além de P10).

Cada passo chama `registrar_posicao`, que grava um `EventoEntrega` no banco.
A tela da compradora relê esses eventos num QTimer próprio.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from dominio.empresa import EmpresaMarisqueira
from dominio.enums import StatusEntrega
from dominio.pedido import Pedido
from repositorio.repositorio import Repositorio
from ui.componentes import divisor, estilo_barra, protegido, rotulo_secao
from ui.estilo import LARANJA, TEXTO_SUAVE, VERDE
from ui.mapa import WidgetMapa

# Quantos passos até chegar. 20 dá um trajeto visível sem poluir o banco de
# eventos nem a lista de pontos no mapa.
PASSOS = 20

VELOCIDADES = (
    ("Devagar", 900),
    ("Normal", 450),
    ("Rápido", 180),
)


class DialogoSimulacao(QDialog):
    def __init__(
        self,
        pai,
        pedido: Pedido,
        empresa: EmpresaMarisqueira,
        repo: Repositorio,
        ao_alterar: Callable[[], None],
    ) -> None:
        super().__init__(pai)
        self.pedido = pedido
        self.empresa = empresa
        self.repo = repo
        self.ao_alterar = ao_alterar
        self.passo_atual = len(pedido.eventos_entrega)

        self.setWindowTitle(f"Entrega do pedido {pedido.id}")
        self.setMinimumSize(760, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel(f"Pedido {pedido.id}")
        titulo.setObjectName("titulo")
        layout.addWidget(titulo)
        self.lbl_rota = QLabel()
        self.lbl_rota.setObjectName("subtitulo")
        self.lbl_rota.setWordWrap(True)
        layout.addWidget(self.lbl_rota)

        self.mapa = WidgetMapa()
        layout.addWidget(self.mapa, 1)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(8)
        self.barra.setStyleSheet(estilo_barra(8))
        layout.addWidget(self.barra)

        self.lbl_estado = QLabel()
        self.lbl_estado.setObjectName("meta")
        layout.addWidget(self.lbl_estado)
        layout.addWidget(divisor())

        controles = QHBoxLayout()
        controles.setSpacing(10)
        controles.addWidget(rotulo_secao("Velocidade"))
        self.in_velocidade = QComboBox()
        for rotulo, intervalo in VELOCIDADES:
            self.in_velocidade.addItem(rotulo, intervalo)
        self.in_velocidade.setCurrentIndex(1)
        self.in_velocidade.currentIndexChanged.connect(self._trocar_velocidade)
        controles.addWidget(self.in_velocidade)
        controles.addStretch()

        self.btn_rodar = QPushButton("Iniciar entrega")
        self.btn_rodar.clicked.connect(self._alternar)
        self.btn_passo = QPushButton("Avançar um ponto")
        self.btn_passo.setObjectName("secundario")
        self.btn_passo.clicked.connect(self._um_passo)
        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.setObjectName("secundario")
        self.btn_fechar.clicked.connect(self.accept)
        controles.addWidget(self.btn_passo)
        controles.addWidget(self.btn_rodar)
        controles.addWidget(self.btn_fechar)
        layout.addLayout(controles)

        self.timer = QTimer(self)
        self.timer.setInterval(self.in_velocidade.currentData())
        self.timer.timeout.connect(self._um_passo)

        self.atualizar()

    # controle

    def _trocar_velocidade(self) -> None:
        self.timer.setInterval(self.in_velocidade.currentData())

    def _alternar(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
        elif self._chegou:
            return
        else:
            self.timer.start()
        self.atualizar()

    @property
    def _chegou(self) -> bool:
        return self.passo_atual >= PASSOS

    def _um_passo(self) -> None:
        """Avança o entregador e grava a posição como evento do pedido."""
        if self._chegou:
            self.timer.stop()
            self.atualizar()
            return

        origem = self.pedido.coordenada_origem
        destino = self.pedido.coordenada_entrega
        if origem is None or destino is None:
            self.timer.stop()
            self.lbl_estado.setText(
                "As duas empresas precisam de coordenada para simular o trajeto."
            )
            return

        self.passo_atual += 1
        fracao = self.passo_atual / PASSOS
        posicao = origem.interpolar(destino, fracao)
        restante = posicao.distancia_km(destino)
        if self.passo_atual >= PASSOS:
            descricao = "Chegou no endereço de entrega"
        elif self.passo_atual == 1:
            descricao = "Saiu para entrega"
        else:
            descricao = f"Em trânsito, {restante} km restantes"

        def acao() -> None:
            self.empresa.registrar_posicao(self.pedido, posicao, descricao)
            self.repo.salvar_pedido(self.pedido)

        if not protegido(self, acao):
            self.timer.stop()
            self.passo_atual -= 1
            return

        if self._chegou:
            self.timer.stop()
        self.atualizar()
        self.ao_alterar()

    # desenho

    def atualizar(self) -> None:
        pedido = self.pedido
        origem = pedido.coordenada_origem
        destino = pedido.coordenada_entrega
        nome_origem = pedido.marisqueira.nome if pedido.marisqueira else "Origem"

        self.mapa.definir_rota(
            origem=origem,
            destino=destino,
            trajeto=[e.coordenada for e in pedido.eventos_entrega],
            posicao=pedido.posicao_atual,
            rotulo_origem=nome_origem,
            rotulo_destino=pedido.compradora.nome,
        )

        total = pedido.distancia_total_km
        restante = pedido.distancia_restante_km
        self.lbl_rota.setText(
            f"{nome_origem} até {pedido.endereco_entrega}"
            + (f" · {total} km no total" if total else "")
        )
        self.barra.setValue(pedido.progresso_percentual)

        if self._chegou or pedido.status_entrega is StatusEntrega.ENTREGUE:
            cor, texto = (
                VERDE,
                ("Chegou no destino. A compradora precisa confirmar o recebimento."),
            )
        elif self.timer.isActive():
            cor, texto = (
                LARANJA,
                (
                    f"Em trânsito · ponto {self.passo_atual} de {PASSOS}"
                    + (f" · faltam {restante} km" if restante else "")
                ),
            )
        else:
            cor, texto = (
                TEXTO_SUAVE,
                (
                    f"Parado · ponto {self.passo_atual} de {PASSOS}"
                    + (f" · faltam {restante} km" if restante else "")
                ),
            )
        self.lbl_estado.setText(texto)
        self.lbl_estado.setStyleSheet(f"color: {cor}; font-weight: 600;")

        self.btn_rodar.setText(
            "Pausar"
            if self.timer.isActive()
            else "Retomar entrega"
            if self.passo_atual
            else "Iniciar entrega"
        )
        self.btn_rodar.setEnabled(not self._chegou)
        self.btn_passo.setEnabled(not self._chegou and not self.timer.isActive())

    def closeEvent(self, evento) -> None:  # noqa: N802, nome exigido pelo Qt
        self.timer.stop()
        super().closeEvent(evento)
