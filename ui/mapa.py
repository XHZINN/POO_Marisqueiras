"""Mapa do trajeto da entrega (extensão além de P10).

Desenha a malha viária de verdade: as ruas vêm do OpenStreetMap, lidas de
`geo/malha.py`, e a rota é a sequência de pontos que o roteador devolveu,
não uma reta de A a B. QPainter puro, sem tiles de servidor, então abre
offline.

A longitude é corrigida por cos(lat) em todo o módulo, senão o mapa sai
esticado na horizontal.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget

from dominio.coordenada import Coordenada
from dominio.rota import Rota
from geo.malha import malha
from ui import estilo

TERRA = QColor("#F2F1EC")
AGUA = QColor("#DCE9EC")
RUA = QColor("#FFFFFF")
RUA_BORDA = QColor("#DAD7CE")
VIA_PRINCIPAL = QColor("#FBE8C8")
VIA_PRINCIPAL_BORDA = QColor("#E4C48C")
ROTA_PREVISTA = QColor("#7F9BA0")

# Vias que ganham cor de via arterial em vez de rua branca.
ARTERIAIS = ("motorway", "trunk", "primary")

# Fonte dos dados. O ODbL exige o crédito visível onde o dado aparece.
CREDITO = "© OpenStreetMap contributors (ODbL)"


class WidgetMapa(QWidget):
    """Desenha ruas, rota prevista, trajeto andado e o entregador."""

    MARGEM = 34
    # Texto de quando não há nada pra projetar. A tela de endereços troca
    # este texto, porque lá o que falta é a coordenada e não a rota.
    vazio = "Sem rota para mostrar"
    # Folga mínima em volta da rota, em graus. Sem isso uma entrega curta
    # fica com zoom tão fechado que não aparece rua nenhuma em volta.
    FOLGA_MINIMA = 0.004

    def __init__(self, pai=None) -> None:
        super().__init__(pai)
        self.setMinimumHeight(300)
        self.origem: Coordenada | None = None
        self.destino: Coordenada | None = None
        self.trajeto: list[Coordenada] = []
        self.posicao: Coordenada | None = None
        self.rota: Rota | None = None
        self.rotulo_origem = "Origem"
        self.rotulo_destino = "Destino"
        # Modo de ponto único: mostra um endereço sozinho, sem trajeto.
        self.ponto: Coordenada | None = None
        self.rotulo_ponto = ""

    def definir_rota(
        self,
        origem: Coordenada | None,
        destino: Coordenada | None,
        trajeto: list[Coordenada] | None = None,
        posicao: Coordenada | None = None,
        rotulo_origem: str = "Origem",
        rotulo_destino: str = "Destino",
        rota: Rota | None = None,
    ) -> None:
        self.origem = origem
        self.destino = destino
        self.trajeto = list(trajeto or [])
        self.posicao = posicao
        self.rota = rota
        self.rotulo_origem = rotulo_origem
        self.rotulo_destino = rotulo_destino
        self.ponto = None
        self.update()

    def definir_ponto(self, coordenada: Coordenada | None, rotulo: str = "") -> None:
        """Mostra um endereço sozinho, sem trajeto nenhum.

        Serve ao cadastro de endereços: depois de buscar a coordenada, ver o
        pino na rua certa vale mais do que ler dois números de latitude.
        """
        self.origem = None
        self.destino = None
        self.trajeto = []
        self.posicao = None
        self.rota = None
        self.ponto = coordenada
        self.rotulo_ponto = rotulo
        self.update()

    # projeção

    def _pontos(self) -> list[Coordenada]:
        if self.ponto is not None:
            # Dois pontos iguais: a folga mínima abre a janela em volta dele.
            return [self.ponto, self.ponto]
        tudo = [p for p in (self.origem, self.destino, self.posicao) if p]
        if self.rota is not None:
            tudo += list(self.rota.pontos)
        return tudo + self.trajeto

    def _projetor(self):
        """Devolve (projetar, escala, fator, caixa) ou None se não há rota.

        `caixa` é o retângulo geográfico visível, que é o que a consulta à
        malha precisa pra não varrer o estado inteiro.
        """
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
        altura_graus = max(max_lat - min_lat, self.FOLGA_MINIMA)
        largura_graus = max((max_lon - min_lon) * fator, self.FOLGA_MINIMA)

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
        centro_x = area.center().x()
        centro_y = area.center().y()

        def projetar(c) -> QPointF:
            # Aceita Coordenada e par (lat, lon), que é como a malha guarda.
            lat, lon = (c.latitude, c.longitude) if hasattr(c, "latitude") else c
            dx = (lon - centro_lon) * fator * escala
            # Latitude cresce para o norte, y da tela cresce para baixo.
            dy = -(lat - centro_lat) * escala
            return QPointF(centro_x + dx, centro_y + dy)

        # Retângulo geográfico que a tela inteira cobre, incluindo as margens.
        meia_altura = (self.height() / 2) / escala
        meia_largura = (self.width() / 2) / escala / fator
        caixa = (
            centro_lat - meia_altura,
            centro_lon - meia_largura,
            centro_lat + meia_altura,
            centro_lon + meia_largura,
        )
        return projetar, escala, fator, caixa

    # pintura

    def paintEvent(self, evento) -> None:  # noqa: N802, nome exigido pelo Qt
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)

        area = QRectF(0, 0, self.width(), self.height())
        moldura = QPainterPath()
        moldura.addRoundedRect(area.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        pintor.fillPath(moldura, QBrush(TERRA))
        pintor.setPen(QPen(QColor(estilo.BORDA), 1))
        pintor.drawPath(moldura)
        pintor.setClipPath(moldura)

        projecao = self._projetor()
        if projecao is None:
            pintor.setPen(QPen(QColor(estilo.TEXTO_FRACO)))
            pintor.drawText(area, Qt.AlignmentFlag.AlignCenter, self.vazio)
            return
        projetar, escala, fator, caixa = projecao

        km_visiveis = self.width() / (escala * fator) * 111.32
        desenhou_ruas = self._ruas(pintor, projetar, caixa, km_visiveis)
        if not desenhou_ruas:
            self._grade(pintor, area)
        self._rota_prevista(pintor, projetar)
        self._trajeto_andado(pintor, projetar)
        self._pinos(pintor, projetar)
        self._entregador(pintor, projetar)
        self._escala(pintor, area, escala, fator)
        if desenhou_ruas:
            self._credito(pintor, area)

    def _ruas(self, pintor: QPainter, projetar, caixa, km_visiveis: float) -> bool:
        """Desenha a malha viária. Falso quando não há arquivo de vias."""
        rede = malha()
        if rede is None:
            return False
        sul, oeste, norte, leste = caixa
        vias = rede.vias_em(sul, oeste, norte, leste, km_visiveis)
        if not vias:
            return False

        # Duas passadas por via: traço escuro mais grosso embaixo faz a
        # borda, traço claro em cima faz o asfalto. É o que dá a aparência
        # de rua em vez de rabisco colorido.
        for camada in ("borda", "asfalto"):
            for via in vias:
                arterial = via.classe in ARTERIAIS
                if camada == "borda":
                    cor = VIA_PRINCIPAL_BORDA if arterial else RUA_BORDA
                    largura = via.espessura + 1.6
                else:
                    cor = VIA_PRINCIPAL if arterial else RUA
                    largura = via.espessura
                pintor.setPen(
                    QPen(
                        cor,
                        largura,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin,
                    )
                )
                pintor.drawPolyline(QPolygonF([projetar(p) for p in via.pontos]))
        return True

    def _grade(self, pintor: QPainter, area: QRectF) -> None:
        """Grade de fundo, só quando a malha viária não está disponível."""
        pintor.setPen(QPen(AGUA, 1, Qt.PenStyle.DotLine))
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
        """Caminho planejado, tracejado: a rota inteira quando ela existe."""
        if self.rota is not None:
            pontos = [projetar(p) for p in self.rota.pontos]
        elif self.origem and self.destino:
            pontos = [projetar(self.origem), projetar(self.destino)]
        else:
            return
        pintor.setPen(
            QPen(
                ROTA_PREVISTA,
                3,
                Qt.PenStyle.DashLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        pintor.drawPolyline(QPolygonF(pontos))

    def _trajeto_andado(self, pintor: QPainter, projetar) -> None:
        """Parte já percorrida, sólida e por cima da prevista.

        Com rota, o traçado andado é o recorte dela até a posição atual, e
        não a ligação entre os pontos gravados: unir checkpoint a checkpoint
        em linha reta cortaria as esquinas.
        """
        if self.rota is not None and self.posicao is not None:
            pontos = list(self.rota.trecho_ate(self.rota.fracao_de(self.posicao)))
        else:
            pontos = list(self.trajeto)
            if self.posicao and (not pontos or pontos[-1] != self.posicao):
                pontos.append(self.posicao)
        if len(pontos) < 2:
            return

        pintor.setPen(
            QPen(
                QColor(estilo.PRIMARIA),
                4,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        pintor.drawPolyline(QPolygonF([projetar(p) for p in pontos]))

        # Marcas nas posições que ficaram registradas no histórico.
        pintor.setBrush(QBrush(QColor(estilo.PRIMARIA)))
        pintor.setPen(QPen(QColor("#FFFFFF"), 1))
        for ponto in self.trajeto:
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
        if self.ponto is not None:
            self._pino(
                pintor,
                projetar(self.ponto),
                estilo.VERMELHO,
                self.rotulo_ponto,
                False,
            )
            return
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

    def _direcao(self, projetar) -> float | None:
        """Ângulo pra onde o entregador está indo, em graus de tela.

        Tira a direção do próximo ponto da rota, pra a seta apontar na curva
        em vez de ficar sempre virada pro destino final.
        """
        if self.rota is None or self.posicao is None:
            if self.posicao is None or self.destino is None:
                return None
            atual, adiante = self.posicao, self.destino
        else:
            fracao = self.rota.fracao_de(self.posicao)
            atual = self.posicao
            adiante = self.rota.ponto_em(min(1.0, fracao + 0.01))
            if adiante == atual:
                adiante = self.rota.destino
        inicio, fim = projetar(atual), projetar(adiante)
        dx, dy = fim.x() - inicio.x(), fim.y() - inicio.y()
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return None
        return math.degrees(math.atan2(dy, dx))

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

        # Seta girada na direção do movimento.
        angulo = self._direcao(projetar)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QBrush(QColor("#FFFFFF")))
        pintor.save()
        pintor.translate(centro)
        if angulo is not None:
            pintor.rotate(angulo)
        seta = [QPointF(5.5, 0.0), QPointF(-3.5, -4.0), QPointF(-3.5, 4.0)]
        pintor.drawPolygon(QPolygonF(seta))
        pintor.restore()

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

    def _credito(self, pintor: QPainter, area: QRectF) -> None:
        """Crédito do OpenStreetMap. A licença ODbL obriga a citar a fonte."""
        fonte = QFont(pintor.font())
        fonte.setPointSize(7)
        pintor.setFont(fonte)
        pintor.setPen(QPen(QColor(estilo.TEXTO_FRACO)))
        caixa = QRectF(area.left(), area.bottom() - 15, area.width() - 10, 12)
        pintor.drawText(
            caixa,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            CREDITO,
        )
