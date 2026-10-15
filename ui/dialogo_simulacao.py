"""Simulação da entrega seguindo a rota por ruas (extensão além de P10).

A animação roda sozinha ao abrir: quem acompanha entrega não fica clicando
em "próximo ponto". A cada quadro o entregador anda um pedaço da rota de
verdade (`Rota.ponto_em`), e só de tempos em tempos a posição vira
`EventoEntrega` no banco — gravar todo quadro encheria a tabela de milhares
de linhas para um trajeto de meia hora.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

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
from geo.roteador import roteador
from repositorio.repositorio import Repositorio
from ui.componentes import divisor, estilo_barra, protegido, rotulo_secao
from ui.estilo import LARANJA, TEXTO_SUAVE, VERDE
from ui.mapa_web import MapaWeb

# Quadro da animação. 70 ms dá movimento contínuo sem pesar na repintura.
QUADRO_MS = 70

# Quantas posições ficam gravadas no histórico do pedido. 18 pontos contam a
# viagem sem transformar o trajeto em milhares de linhas no banco.
CHECKPOINTS = 18

# Quanto tempo a entrega inteira leva na tela, em velocidade 1x.
TRAVESSIA_SEGUNDOS = 26.0

VELOCIDADES = (("1×", 1.0), ("2×", 2.0), ("4×", 4.0), ("8×", 8.0))

# Uma casa decimal, que é a precisão com que a distância é mostrada.
DECIMAL_KM = Decimal("0.1")


class DialogoSimulacao(QDialog):
    """Acompanha o entregador andando pela rota, do despacho à chegada."""

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

        # Rota por ruas. Se o pedido já tem uma, reaproveita; senão pede ao
        # roteador, que responde do cache quando já traçou este trajeto.
        if pedido.rota is None:
            pedido.definir_rota(
                roteador().rota(pedido.coordenada_origem, pedido.coordenada_entrega)
            )
        self.rota = pedido.rota

        # Retoma de onde o trajeto gravado parou, em vez de voltar à origem.
        self.fracao = pedido.fracao_percorrida
        self.checkpoints_gravados = int(self.fracao * CHECKPOINTS)

        self.setWindowTitle(f"Entrega do pedido {pedido.id}")
        self.setMinimumSize(820, 660)

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

        self.mapa = MapaWeb()
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
        for rotulo, fator in VELOCIDADES:
            self.in_velocidade.addItem(rotulo, fator)
        self.in_velocidade.setCurrentIndex(1)
        controles.addWidget(self.in_velocidade)
        controles.addStretch()

        self.btn_rodar = QPushButton("Pausar")
        self.btn_rodar.clicked.connect(self._alternar)
        self.btn_fim = QPushButton("Ir direto ao destino")
        self.btn_fim.setObjectName("secundario")
        self.btn_fim.clicked.connect(self._ate_o_fim)
        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.setObjectName("secundario")
        self.btn_fechar.clicked.connect(self.accept)
        controles.addWidget(self.btn_fim)
        controles.addWidget(self.btn_rodar)
        controles.addWidget(self.btn_fechar)
        layout.addLayout(controles)

        self.timer = QTimer(self)
        self.timer.setInterval(QUADRO_MS)
        self.timer.timeout.connect(self._quadro)

        self.atualizar()
        # Começa sozinha: a entrega já saiu, a tela só mostra o que acontece.
        if not self._chegou and self.rota is not None:
            self.timer.start()
            self.atualizar()

    # controle

    @property
    def _chegou(self) -> bool:
        return self.fracao >= 0.9999

    def _alternar(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
        elif not self._chegou:
            self.timer.start()
        self.atualizar()

    def _quadro(self) -> None:
        """Um passo da animação: anda pela rota e, de vez em quando, grava."""
        if self.rota is None:
            self.timer.stop()
            self.lbl_estado.setText(
                "Sem coordenada das duas pontas não há trajeto para simular."
            )
            return
        if self._chegou:
            self.timer.stop()
            self.atualizar()
            return

        fator = self.in_velocidade.currentData() or 1.0
        avanco = (QUADRO_MS / 1000.0) / TRAVESSIA_SEGUNDOS * fator
        self.fracao = min(1.0, self.fracao + avanco)

        # Grava a posição só quando cruza um checkpoint, e sempre na chegada.
        marca = int(self.fracao * CHECKPOINTS)
        if marca > self.checkpoints_gravados or self._chegou:
            if not self._registrar():
                return
            self.checkpoints_gravados = marca

        if self._chegou:
            self.timer.stop()
        self._desenhar()

    def _registrar(self) -> bool:
        """Grava a posição atual como evento do pedido. Falso se não deu."""
        posicao = self.rota.ponto_em(self.fracao)
        restante = self._km_restantes()
        if self._chegou:
            descricao = "Chegou no endereço de entrega"
        elif self.checkpoints_gravados == 0:
            descricao = "Saiu para entrega"
        else:
            descricao = f"Em trânsito, faltam {restante} km"

        def acao() -> None:
            self.empresa.registrar_posicao(self.pedido, posicao, descricao)
            self.repo.salvar_pedido(self.pedido)

        if not protegido(self, acao):
            self.timer.stop()
            self.atualizar()
            return False
        self.ao_alterar()
        return True

    def _km_restantes(self) -> Decimal:
        """Quanto falta rodar. Decimal porque distância não é float na regra."""
        if self.rota is None:
            return Decimal("0")
        falta = Decimal(str(1 - round(self.fracao, 4)))
        return (self.rota.extensao * falta).quantize(DECIMAL_KM)

    def _ate_o_fim(self) -> None:
        """Pula pro destino, pra quem não quer ver a viagem inteira."""
        self.timer.stop()
        if self._chegou:
            return
        self.fracao = 1.0
        self._registrar()
        self.atualizar()

    # desenho

    def _desenhar(self) -> None:
        """Só o que muda a cada quadro: mapa, barra e linha de estado."""
        pedido = self.pedido
        posicao = self.rota.ponto_em(self.fracao) if self.rota else pedido.posicao_atual
        nome_origem = pedido.marisqueira.nome if pedido.marisqueira else "Origem"

        self.mapa.definir_rota(
            origem=pedido.coordenada_origem,
            destino=pedido.coordenada_entrega,
            trajeto=[e.coordenada for e in pedido.eventos_entrega],
            posicao=posicao,
            rotulo_origem=nome_origem,
            rotulo_destino=pedido.compradora.nome,
            rota=self.rota,
        )
        self.barra.setValue(int(self.fracao * 100))
        self.lbl_estado.setText(self._texto_estado())
        cor = self._cor_estado()
        self.lbl_estado.setStyleSheet(f"color: {cor}; font-weight: 600;")

    def _texto_estado(self) -> str:
        if self.rota is None:
            return "Sem coordenada das duas pontas não há trajeto para simular."
        falta_km = self._km_restantes()
        falta_min = int(self.rota.duracao_minutos * (1 - self.fracao))
        if self._chegou:
            return "Chegou no destino. A compradora precisa confirmar o recebimento."
        andar = "Em trânsito" if self.timer.isActive() else "Parado"
        return (
            f"{andar} · {int(self.fracao * 100)}% do caminho · "
            f"faltam {falta_km} km, cerca de {falta_min} min"
        )

    def _cor_estado(self) -> str:
        if self._chegou or self.pedido.status_entrega is StatusEntrega.ENTREGUE:
            return VERDE
        return LARANJA if self.timer.isActive() else TEXTO_SUAVE

    def atualizar(self) -> None:
        """Redesenha tudo, inclusive o cabeçalho e o estado dos botões."""
        pedido = self.pedido
        nome_origem = pedido.marisqueira.nome if pedido.marisqueira else "Origem"
        if self.rota is not None:
            traco = (
                f"{self.rota.distancia_km} km por ruas, "
                f"cerca de {self.rota.duracao_minutos} min"
                if self.rota.por_ruas
                else (
                    f"{self.rota.distancia_km} km em linha reta — sem conexão "
                    "com o serviço de rotas, o trajeto real é maior"
                )
            )
        else:
            traco = "sem trajeto"
        destino = pedido.endereco_entrega
        self.lbl_rota.setText(f"{nome_origem} até {destino} · {traco}")

        self._desenhar()
        self.btn_rodar.setText("Pausar" if self.timer.isActive() else "Retomar")
        self.btn_rodar.setEnabled(not self._chegou and self.rota is not None)
        self.btn_fim.setEnabled(not self._chegou and self.rota is not None)

    def closeEvent(self, evento) -> None:  # noqa: N802, nome exigido pelo Qt
        self.timer.stop()
        super().closeEvent(evento)
