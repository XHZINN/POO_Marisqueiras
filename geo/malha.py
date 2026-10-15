"""Malha viária da região, lida de `dados/malha_viaria.json.gz`.

As vias vêm do OpenStreetMap (ODbL) e estão no repositório prontas, pra o
mapa abrir sem internet. `dados/baixar_malha.py` regera o arquivo.

O arquivo guarda as coordenadas como inteiros em centésimos de milésimo de
grau e em diferença do ponto anterior, que é o que deixa 22 mil vias caberem
em 220 KB.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "dados" / "malha_viaria.json.gz"

# Largura de traço de cada tipo de via, e a partir de que largura de tela
# cada uma aparece. Mapa de cidade inteira com rua residencial desenhada
# fica um borrão cinza, então as locais só entram quando dá zoom.
ESPESSURA = {
    "motorway": 3.0,
    "trunk": 2.6,
    "primary": 2.2,
    "secondary": 1.6,
    "tertiary": 1.1,
    "residential": 0.7,
}
LIMITE_DE_ZOOM_KM = {
    "motorway": 999.0,
    "trunk": 999.0,
    "primary": 60.0,
    "secondary": 25.0,
    "tertiary": 12.0,
    "residential": 5.0,
}

# Lado da célula do índice, em graus. 0,01° é pouco mais de 1 km.
CELULA = 0.01


@dataclass(frozen=True)
class Via:
    classe: str
    pontos: tuple[tuple[float, float], ...]
    sul: float
    oeste: float
    norte: float
    leste: float

    @property
    def espessura(self) -> float:
        return ESPESSURA.get(self.classe, 0.8)


class MalhaViaria:
    """Vias da região, indexadas em grade pra consulta por retângulo.

    Sem o índice, desenhar um mapa varreria as 22 mil vias a cada repintura.
    """

    def __init__(self, vias: list[Via]) -> None:
        self.vias = vias
        self._grade: dict[tuple[int, int], list[int]] = {}
        for indice, via in enumerate(vias):
            for celula in self._celulas(via.sul, via.oeste, via.norte, via.leste):
                self._grade.setdefault(celula, []).append(indice)

    @staticmethod
    def _celulas(sul, oeste, norte, leste):
        for y in range(int(sul // CELULA), int(norte // CELULA) + 1):
            for x in range(int(oeste // CELULA), int(leste // CELULA) + 1):
                yield (y, x)

    @classmethod
    def carregar(cls, caminho: Path | None = None) -> MalhaViaria:
        caminho = caminho or ARQUIVO
        with gzip.open(caminho, "rt", encoding="utf-8") as arquivo:
            doc = json.load(arquivo)

        classes = doc["classes"]
        escala = doc["escala"]
        vias: list[Via] = []
        for linha in doc["vias"]:
            classe = classes[linha[0]]
            lat, lon = linha[1], linha[2]
            pontos = [(lat / escala, lon / escala)]
            for i in range(3, len(linha), 2):
                lat += linha[i]
                lon += linha[i + 1]
                pontos.append((lat / escala, lon / escala))
            latitudes = [p[0] for p in pontos]
            longitudes = [p[1] for p in pontos]
            vias.append(
                Via(
                    classe=classe,
                    pontos=tuple(pontos),
                    sul=min(latitudes),
                    oeste=min(longitudes),
                    norte=max(latitudes),
                    leste=max(longitudes),
                )
            )
        return cls(vias)

    def vias_em(
        self,
        sul: float,
        oeste: float,
        norte: float,
        leste: float,
        largura_km: float,
    ) -> list[Via]:
        """Vias que cruzam o retângulo, só as visíveis nessa escala."""
        permitidas = {
            classe
            for classe, limite in LIMITE_DE_ZOOM_KM.items()
            if largura_km <= limite
        }
        candidatos: set[int] = set()
        for celula in self._celulas(sul, oeste, norte, leste):
            candidatos.update(self._grade.get(celula, ()))

        achadas = []
        for indice in candidatos:
            via = self.vias[indice]
            if via.classe not in permitidas:
                continue
            if via.leste < oeste or via.oeste > leste:
                continue
            if via.norte < sul or via.sul > norte:
                continue
            achadas.append(via)
        # Via larga desenhada por cima some; as finas vêm primeiro.
        achadas.sort(key=lambda v: v.espessura)
        return achadas

    def __len__(self) -> int:
        return len(self.vias)


_malha: MalhaViaria | None = None


def malha() -> MalhaViaria | None:
    """Malha carregada uma vez por execução. `None` se o arquivo faltar."""
    global _malha
    if _malha is None:
        try:
            _malha = MalhaViaria.carregar()
        except (OSError, ValueError, KeyError):
            return None
    return _malha
