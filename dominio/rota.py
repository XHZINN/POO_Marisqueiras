"""Rota entre dois pontos, com os vértices do caminho.

Quem monta a rota é `geo/roteador.py`, que fala com serviço externo. Aqui
fica só o objeto: a lista de pontos, a distância, a duração e as contas de
andar sobre essa lista.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from math import cos, radians

from dominio.coordenada import Coordenada
from dominio.excecoes import DadoObrigatorio

# Velocidade pra estimar duração quando não há rota de serviço de mapas.
# Média de trânsito urbano na Grande São Luís.
VELOCIDADE_PADRAO_KMH = 32


@dataclass(frozen=True)
class Rota:
    """Caminho de A até B como sequência de coordenadas.

    `fonte` guarda de onde veio o traçado: `"malha"` quando é rota por ruas,
    `"reta"` quando é o segmento direto. A tela mostra isso, porque uma reta
    sobre o mapa não é um percurso de verdade.
    """

    pontos: tuple[Coordenada, ...]
    distancia_km: Decimal
    duracao_minutos: int
    fonte: str = "malha"

    # Distância acumulada em cada vértice. Serve pra achar o ponto a X% do
    # caminho sem recalcular a rota toda a cada quadro da animação.
    _acumulado: tuple[Decimal, ...] = field(
        init=False, repr=False, compare=False, default=()
    )

    def __post_init__(self) -> None:
        if len(self.pontos) < 2:
            raise DadoObrigatorio("Uma rota precisa de pelo menos dois pontos.")

        acumulado = [Decimal("0")]
        for anterior, atual in zip(self.pontos, self.pontos[1:], strict=False):
            trecho = anterior.distancia_km(atual) or Decimal("0")
            acumulado.append(acumulado[-1] + trecho)
        # frozen bloqueia atribuição normal; é assim que se preenche campo
        # derivado num dataclass imutável.
        object.__setattr__(self, "_acumulado", tuple(acumulado))

    @classmethod
    def em_linha_reta(
        cls,
        origem: Coordenada,
        destino: Coordenada,
        kmh: int = VELOCIDADE_PADRAO_KMH,
    ) -> Rota:
        """Rota de dois pontos, pra quando o serviço de mapas não responde."""
        km = origem.distancia_km(destino) or Decimal("0")
        minutos = max(1, int(km / Decimal(kmh) * 60))
        return cls(
            pontos=(origem, destino),
            distancia_km=km,
            duracao_minutos=minutos,
            fonte="reta",
        )

    @property
    def origem(self) -> Coordenada:
        return self.pontos[0]

    @property
    def destino(self) -> Coordenada:
        return self.pontos[-1]

    @property
    def por_ruas(self) -> bool:
        return self.fonte == "malha"

    @property
    def extensao(self) -> Decimal:
        """Soma dos trechos. Pode diferir de `distancia_km` por arredondamento."""
        return self._acumulado[-1]

    def ponto_em(self, fracao: float) -> Coordenada:
        """Coordenada a `fracao` do caminho, medida em distância percorrida.

        Caminha pelos vértices até estourar a distância alvo e interpola
        dentro do trecho onde ela cai. É isso que faz o entregador seguir as
        curvas da rua em vez de cortar reto.
        """
        fracao = max(0.0, min(1.0, float(fracao)))
        alvo = self.extensao * Decimal(str(fracao))

        for i in range(1, len(self._acumulado)):
            if self._acumulado[i] >= alvo:
                inicio, fim = self._acumulado[i - 1], self._acumulado[i]
                trecho = fim - inicio
                if trecho <= 0:
                    return self.pontos[i]
                dentro = float((alvo - inicio) / trecho)
                return self.pontos[i - 1].interpolar(self.pontos[i], dentro)
        return self.destino

    def trecho_ate(self, fracao: float) -> tuple[Coordenada, ...]:
        """Parte da rota já percorrida, do início até `fracao`."""
        fracao = max(0.0, min(1.0, float(fracao)))
        alvo = self.extensao * Decimal(str(fracao))
        andado = [
            p for p, d in zip(self.pontos, self._acumulado, strict=False) if d <= alvo
        ]
        atual = self.ponto_em(fracao)
        if not andado:
            return (atual,)
        if andado[-1] != atual:
            andado.append(atual)
        return tuple(andado)

    def fracao_de(self, coordenada: Coordenada) -> float:
        """Em que ponto da rota `coordenada` cai, de 0 a 1.

        Projeta sobre cada trecho em vez de só olhar os vértices, senão uma
        posição no meio de um trecho longo era jogada pra ponta dele. Usado
        pra retomar a animação de onde o último ponto gravado parou.
        """
        if self.extensao <= 0:
            return 0.0

        melhor, menor_erro = 0.0, None
        for i in range(1, len(self.pontos)):
            a, b = self.pontos[i - 1], self.pontos[i]
            # Projeção escalar no trecho a→b. Em poucos quilômetros dá pra
            # tratar lat/lon como plano; o cos corrige a longitude.
            fator = max(0.1, abs(cos(radians(a.latitude))))
            ax, ay = a.longitude * fator, a.latitude
            bx, by = b.longitude * fator, b.latitude
            px, py = coordenada.longitude * fator, coordenada.latitude
            dx, dy = bx - ax, by - ay
            norma = dx * dx + dy * dy
            if norma == 0:
                t = 0.0
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / norma
                t = max(0.0, min(1.0, t))
            erro = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if menor_erro is None or erro < menor_erro:
                menor_erro = erro
                trecho = self._acumulado[i] - self._acumulado[i - 1]
                dentro = self._acumulado[i - 1] + trecho * Decimal(str(t))
                melhor = float(dentro / self.extensao)
        return melhor

    def amostrar(self, quantidade: int) -> tuple[Coordenada, ...]:
        """`quantidade` pontos igualmente espaçados, incluindo origem e destino."""
        if quantidade < 2:
            raise DadoObrigatorio("Uma amostra de rota precisa de dois pontos.")
        return tuple(self.ponto_em(i / (quantidade - 1)) for i in range(quantidade))

    def __len__(self) -> int:
        return len(self.pontos)

    def __repr__(self) -> str:
        return (
            f"<Rota {self.fonte} {len(self.pontos)} pontos "
            f"{self.distancia_km} km {self.duracao_minutos} min>"
        )
