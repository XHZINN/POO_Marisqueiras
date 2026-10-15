"""Mapa do trajeto da entrega (extensão além de P10).

Plano das coordenadas reais desenhado com QPainter, sem tiles de servidor,
então funciona offline. A longitude é corrigida por cos(lat), senão o
trajeto sai esticado na horizontal.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from dominio.coordenada import Coordenada
from ui import estilo

AGUA = QColor("#DCE9EC")
AGUA_LINHA = QColor("#C2D6DB")


class WidgetMapa(QWidget):
    """Desenha origem, destino, rota prevista, trajeto andado e o entregador."""

    MARGEM = 34

    def __init__(self, pai=None) -> None:
        super().__init__(pai)
        self.setMinimumHeight(300)
        self.origem: Coordenada | None = None
        self.destino: Coordenada | None = None
        self.trajeto: list[Coordenada] = []
        self.posicao: Coordenada | None = None
        self.rotulo_origem = "Origem"
        self.rotulo_destino = "Destino"

    def definir_rota(
        self,
        origem: Coordenada | None,
        destino: Coordenada | None,
        trajeto: list[Coordenada] | None = None,
        posicao: Coordenada | None = None,
        rotulo_origem: str = "Origem",
        rotulo_destino: str = "Destino",
    ) -> None:
        self.origem = origem
        self.destino = destino
        self.trajeto = list(trajeto or [])
        self.posicao = posicao
        self.rotulo_origem = rotulo_origem
        self.rotulo_destino = rotulo_destino
        self.update()

    # projeção

    def _pontos(self) -> list[Coordenada]:
        tudo = [p for p in (self.origem, self.destino, self.posicao) if p]
        return tudo + self.trajeto

    def _projetor(self):
        """Devolve a função que converte Coordenada em pixel do widget."""
        pontos = self._pontos()
        if len(pontos) < 2:
            return None

        lats = [p.latitude for p in pontos]
        lons = [p.longitude for p in pontos]
        lat_media = sum(lats) / len(lats)
        # Encurtamento da longitude com a latitude.
        fator = max(0.1, math.cos(math.radians(lat_media)))

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        altura_graus = max(max_lat - min_lat, 1e-4)
        largura_graus = max((max_lon - min_lon) * fator, 1e-4)

        # Folga de 18% para os pinos e rótulos não colarem na borda.
        altura_graus *= 1.18
        largura_graus *= 1.18
        centro_lat = (min_lat + max_lat) / 2
        centro_lon = (min_lon + max_lon) / 2

        area = QRectF(
            self.MARGEM,
            self.MARGEM,
            max(1.0, self.width() - 2 * self.MARGEM),
            max(1.0, self.height() - 2 * self.MARGEM),
        )
        # Mesma escala nos dois eixos: o menor fator manda, o resto é folga.
        escala = min(area.width() / largura_graus, area.height() / altura_graus)

        def projetar(c: Coordenada) -> QPointF:
            dx = (c.longitude - centro_lon) * fator * escala
            # Latitude cresce para o norte, y da tela cresce para baixo.
            dy = -(c.latitude - centro_lat) * escala
            return QPointF(area.center().x() + dx, area.center().y() + dy)

        return projetar, escala, fator

    # pintura

    def paintEvent(self, evento) -> None:  # noqa: N802, nome exigido pelo Qt
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)

        area = QRectF(0, 0, self.width(), self.height())
        caminho = QPainterPath()
        caminho.addRoundedRect(area.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        pintor.fillPath(caminho, QBrush(AGUA))
        pintor.setPen(QPen(QColor(estilo.BORDA), 1))
        pintor.drawPath(caminho)
        pintor.setClipPath(caminho)

        projecao = self._projetor()
        if projecao is None:
            pintor.setPen(QPen(QColor(estilo.TEXTO_FRACO)))
            pintor.drawText(area, Qt.AlignmentFlag.AlignCenter, "Sem rota para mostrar")
            return
        projetar, escala, fator = projecao

        self._grade(pintor, area)
        self._rota_prevista(pintor, projetar)
        self._trajeto_andado(pintor, projetar)
        self._pinos(pintor, projetar)
        self._entregador(pintor, projetar)
        self._escala(pintor, area, escala, fator)

    def _grade(self, pintor: QPainter, area: QRectF) -> None:
        pintor.setPen(QPen(AGUA_LINHA, 1, Qt.PenStyle.DotLine))
        passo = 42
        x = area.left() + passo
        while x < area.right():
            pintor.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
            x += passo
        y = area.top() + passo
        while y < area.bottom():
            pintor.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            y += passo

    def _rota_prevista(self, pintor: QPainter, projetar) -> None:
        if not (self.origem and self.destino):
            return
        pintor.setPen(
            QPen(QColor("#9FB8BD"), 2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
        )
        pintor.drawLine(projetar(self.origem), projetar(self.destino))

    def _trajeto_andado(self, pintor: QPainter, projetar) -> None:
        pontos = list(self.trajeto)
        if self.posicao and (not pontos or pontos[-1] != self.posicao):
            pontos.append(self.posicao)
        if len(pontos) < 2:
            return
        pintor.setPen(
            QPen(
                QColor(estilo.PRIMARIA),
                3,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        caminho = QPainterPath(projetar(pontos[0]))
        for ponto in pontos[1:]:
            caminho.lineTo(projetar(ponto))
        pintor.drawPath(caminho)

        # Marcas discretas em cada posição registrada.
        pintor.setBrush(QBrush(QColor(estilo.PRIMARIA)))
        pintor.setPen(QPen(QColor("#FFFFFF"), 1))
        for ponto in pontos[:-1]:
            pintor.drawEllipse(projetar(ponto), 3.0, 3.0)

    def _pino(
        self, pintor: QPainter, centro: QPointF, cor: str, rotulo: str, acima: bool
    ) -> None:
        raio = 7.0
        pintor.setBrush(QBrush(QColor(cor)))
        pintor.setPen(QPen(QColor("#FFFFFF"), 2))
        pintor.drawEllipse(centro, raio, raio)

        fonte = QFont(pintor.font())
        fonte.setPointSize(9)
        fonte.setBold(True)
        pintor.setFont(fonte)
        metrica = pintor.fontMetrics()
        largura = metrica.horizontalAdvance(rotulo) + 14
        altura = metrica.height() + 6
        deslocamento = -(raio + 8 + altura) if acima else (raio + 8)
        caixa = QRectF(
            centro.x() - largura / 2, centro.y() + deslocamento, largura, altura
        )

        pintor.setBrush(QBrush(QColor(255, 255, 255, 235)))
        pintor.setPen(QPen(QColor(estilo.BORDA), 1))
        pintor.drawRoundedRect(caixa, 6, 6)
        pintor.setPen(QPen(QColor(cor)))
        pintor.drawText(caixa, Qt.AlignmentFlag.AlignCenter, rotulo)

    def _pinos(self, pintor: QPainter, projetar) -> None:
        if self.origem:
            self._pino(
                pintor, projetar(self.origem), estilo.PRIMARIA, self.rotulo_origem, True
            )
        if self.destino:
            self._pino(
                pintor,
                projetar(self.destino),
                estilo.VERMELHO,
                self.rotulo_destino,
                False,
            )

    def _entregador(self, pintor: QPainter, projetar) -> None:
        if not self.posicao:
            return
        centro = projetar(self.posicao)
        # Halo, para separar o entregador dos pinos fixos.
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QBrush(QColor(180, 83, 9, 55)))
        pintor.drawEllipse(centro, 16.0, 16.0)

        pintor.setBrush(QBrush(QColor(estilo.LARANJA)))
        pintor.setPen(QPen(QColor("#FFFFFF"), 2))
        pintor.drawEllipse(centro, 9.0, 9.0)

        fonte = QFont(pintor.font())
        fonte.setPointSize(9)
        pintor.setFont(fonte)
        pintor.setPen(QPen(QColor("#FFFFFF")))
        pintor.drawText(
            QRectF(centro.x() - 10, centro.y() - 10, 20, 20),
            Qt.AlignmentFlag.AlignCenter,
            "▸",
        )

    def _escala(
        self, pintor: QPainter, area: QRectF, escala: float, fator: float
    ) -> None:
        """Barra de escala: quantos pixels valem quantos km."""
        km_por_grau = 111.32
        pixels_por_km = escala / km_por_grau
        if pixels_por_km <= 0:
            return
        # Escolhe um comprimento redondo que caiba em ~22% da largura.
        for km in (1, 2, 5, 10, 20, 50, 100):
            comprimento = km * pixels_por_km
            if comprimento >= area.width() * 0.22:
                break

        base_y = area.bottom() - 16
        inicio = area.left() + 16
        fim = inicio + comprimento
        pintor.setPen(QPen(QColor(estilo.TEXTO_SUAVE), 2))
        pintor.drawLine(QPointF(inicio, base_y), QPointF(fim, base_y))
        pintor.drawLine(QPointF(inicio, base_y - 4), QPointF(inicio, base_y + 4))
        pintor.drawLine(QPointF(fim, base_y - 4), QPointF(fim, base_y + 4))

        fonte = QFont(pintor.font())
        fonte.setPointSize(8)
        pintor.setFont(fonte)
        pintor.drawText(
            QRectF(inicio, base_y - 22, comprimento, 16),
            Qt.AlignmentFlag.AlignCenter,
            f"{km} km",
        )
