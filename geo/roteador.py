"""Rota por ruas entre dois pontos.

Consulta o OSRM, que é o roteador do OpenStreetMap, e guarda o resultado em
`dados/rotas.json`. As rotas do seed já vêm no arquivo, então o programa abre
e desenha o percurso sem rede; sem internet e sem cache, cai pra linha reta e
diz isso na tela.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

from dominio.coordenada import Coordenada
from dominio.rota import Rota

CACHE = Path(__file__).resolve().parent.parent / "dados" / "rotas.json"
SERVIDOR = "https://router.project-osrm.org/route/v1/driving"
AGENTE = "marisques-undb/1.0"

# 4 casas são cerca de 11 m. Arredondar faz dois pedidos pro mesmo endereço
# reaproveitarem a rota em vez de bater no servidor duas vezes.
PRECISAO = 4


class Roteador:
    """Traça a rota e lembra do que já traçou."""

    def __init__(
        self,
        cache: Path | None = None,
        tempo_limite: float = 6.0,
        online: bool = True,
    ) -> None:
        self.caminho_cache = cache or CACHE
        self.tempo_limite = tempo_limite
        self.online = online
        self._cache: dict[str, dict] = self._ler_cache()
        # Uma falha de rede já basta pra parar de tentar: sem isso, cada rota
        # nova travava a tela pelo tempo limite inteiro.
        self._rede_caiu = False

    # cache em disco

    def _ler_cache(self) -> dict[str, dict]:
        try:
            with open(self.caminho_cache, encoding="utf-8") as arquivo:
                return json.load(arquivo)
        except (OSError, ValueError):
            return {}

    def _gravar_cache(self) -> None:
        try:
            self.caminho_cache.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho_cache, "w", encoding="utf-8") as arquivo:
                json.dump(self._cache, arquivo, separators=(",", ":"))
        except OSError:
            pass

    @staticmethod
    def _chave(origem: Coordenada, destino: Coordenada) -> str:
        return (
            f"{round(origem.latitude, PRECISAO)},"
            f"{round(origem.longitude, PRECISAO)};"
            f"{round(destino.latitude, PRECISAO)},"
            f"{round(destino.longitude, PRECISAO)}"
        )

    # consulta

    def rota(
        self, origem: Coordenada | None, destino: Coordenada | None
    ) -> Rota | None:
        """Rota de `origem` até `destino`, ou `None` se faltar coordenada.

        Ordem: cache, servidor, linha reta.
        """
        if origem is None or destino is None:
            return None
        if origem == destino:
            return None

        chave = self._chave(origem, destino)
        if chave in self._cache:
            return self._montar(self._cache[chave])

        bruto = self._consultar(origem, destino)
        if bruto is not None:
            self._cache[chave] = bruto
            self._gravar_cache()
            return self._montar(bruto)

        return Rota.em_linha_reta(origem, destino)

    def _consultar(self, origem: Coordenada, destino: Coordenada) -> dict | None:
        if not self.online or self._rede_caiu:
            return None

        url = (
            f"{SERVIDOR}/{origem.longitude},{origem.latitude};"
            f"{destino.longitude},{destino.latitude}"
            "?overview=full&geometries=geojson"
        )
        pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        try:
            with urllib.request.urlopen(pedido, timeout=self.tempo_limite) as resposta:
                doc = json.load(resposta)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            self._rede_caiu = True
            return None

        if doc.get("code") != "Ok" or not doc.get("routes"):
            return None

        trecho = doc["routes"][0]
        # O GeoJSON vem em [longitude, latitude]; aqui fica [lat, lon].
        pontos = [
            [round(p[1], 5), round(p[0], 5)] for p in trecho["geometry"]["coordinates"]
        ]
        return {
            "km": round(trecho["distance"] / 1000, 1),
            "min": max(1, int(round(trecho["duration"] / 60))),
            "pontos": pontos,
        }

    @staticmethod
    def _montar(bruto: dict) -> Rota:
        pontos = tuple(Coordenada(p[0], p[1]) for p in bruto["pontos"])
        if len(pontos) < 2:
            raise ValueError("Rota em cache sem pontos suficientes.")
        return Rota(
            pontos=pontos,
            distancia_km=Decimal(str(bruto["km"])),
            duracao_minutos=int(bruto["min"]),
            fonte="malha",
        )

    @property
    def rotas_em_cache(self) -> int:
        return len(self._cache)


_roteador: Roteador | None = None


def roteador() -> Roteador:
    """Um roteador por execução, pra o cache ser compartilhado entre as telas."""
    global _roteador
    if _roteador is None:
        _roteador = Roteador()
    return _roteador
