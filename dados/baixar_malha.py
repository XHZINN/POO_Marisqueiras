"""Regera `malha_viaria.json.gz` com as vias da região do projeto.

As vias vêm do OpenStreetMap pela Overpass API. O arquivo já está no
repositório; isto aqui é pra refazer quando quiser outra área ou dados mais
novos:

    python3 dados/baixar_malha.py

A Overpass derruba pedido grande, então a área é baixada em pedaços e cada um
é tentado algumas vezes. Depois as vias passam por Douglas-Peucker e por
diferença entre pontos consecutivos, que é o que tira o arquivo de 3 MB.
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SERVIDOR = "https://overpass-api.de/api/interpreter"
AGENTE = "marisques-undb/1.0"

# Grande São Luís: da baía até a Raposa, que é a área de P4.
SUL, NORTE = -2.62, -2.39
OESTE, LESTE = -44.36, -44.04

CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary", "residential"]
ESCALA = 100000  # 5 casas decimais, cerca de 1 m
TOLERANCIA = 0.00010  # Douglas-Peucker, cerca de 11 m
COLUNAS, LINHAS = 4, 3
SAIDA = Path(__file__).resolve().parent / "malha_viaria.json.gz"


def pedacos():
    largura = (LESTE - OESTE) / COLUNAS
    altura = (NORTE - SUL) / LINHAS
    for coluna in range(COLUNAS):
        for linha in range(LINHAS):
            yield (
                SUL + linha * altura,
                OESTE + coluna * largura,
                SUL + (linha + 1) * altura,
                OESTE + (coluna + 1) * largura,
            )


def baixar(sul, oeste, norte, leste, tentativas=4):
    consulta = (
        f'[out:json][timeout:90];way["highway"~"^({"|".join(CLASSES)})$"]'
        f"({sul:.4f},{oeste:.4f},{norte:.4f},{leste:.4f});out geom;"
    )
    pedido = urllib.request.Request(
        SERVIDOR,
        data=urllib.parse.urlencode({"data": consulta}).encode(),
        headers={"User-Agent": AGENTE},
    )
    for tentativa in range(tentativas):
        try:
            with urllib.request.urlopen(pedido, timeout=150) as resposta:
                return json.load(resposta)
        except (urllib.error.URLError, OSError, ValueError) as erro:
            print(f"    tentativa {tentativa + 1}: {erro}")
            time.sleep(10)
    return None


def simplificar(pontos, tolerancia):
    """Douglas-Peucker: tira vértice que não muda o desenho da via."""
    if len(pontos) < 3:
        return pontos

    (ax, ay), (bx, by) = pontos[0], pontos[-1]
    dx, dy = bx - ax, by - ay
    norma = dx * dx + dy * dy

    pior, corte = 0.0, 0
    for i in range(1, len(pontos) - 1):
        px, py = pontos[i]
        if norma == 0:
            desvio = (px - ax) ** 2 + (py - ay) ** 2
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / norma))
            desvio = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
        if desvio > pior:
            pior, corte = desvio, i

    if pior <= tolerancia * tolerancia:
        return [pontos[0], pontos[-1]]
    return simplificar(pontos[: corte + 1], tolerancia)[:-1] + simplificar(
        pontos[corte:], tolerancia
    )


def main() -> None:
    cruas = []
    for numero, caixa in enumerate(pedacos(), 1):
        print(f"pedaço {numero} de {COLUNAS * LINHAS}")
        doc = baixar(*caixa)
        if doc is None:
            print("    desistiu deste pedaço")
            continue
        for elemento in doc.get("elements", []):
            geometria = elemento.get("geometry")
            if not geometria:
                continue
            cruas.append(
                (
                    elemento["tags"].get("highway"),
                    [(p["lat"], p["lon"]) for p in geometria if p],
                )
            )
        print(f"    {len(cruas)} vias acumuladas")
        time.sleep(2)

    vistas, vias = set(), []
    for classe, pontos in cruas:
        if classe not in CLASSES:
            continue
        pontos = [p for i, p in enumerate(pontos) if i == 0 or p != pontos[i - 1]]
        if len(pontos) < 2:
            continue
        pontos = simplificar(pontos, TOLERANCIA)
        chave = (classe, tuple(pontos))
        if chave in vistas:
            continue
        vistas.add(chave)

        latitudes = [round(p[0] * ESCALA) for p in pontos]
        longitudes = [round(p[1] * ESCALA) for p in pontos]
        linha = [CLASSES.index(classe), latitudes[0], longitudes[0]]
        for i in range(1, len(latitudes)):
            linha.append(latitudes[i] - latitudes[i - 1])
            linha.append(longitudes[i] - longitudes[i - 1])
        vias.append(linha)

    doc = {"classes": CLASSES, "escala": ESCALA, "vias": vias}
    conteudo = json.dumps(doc, separators=(",", ":")).encode()
    with gzip.open(SAIDA, "wb", compresslevel=9) as arquivo:
        arquivo.write(conteudo)

    print(f"\n{len(vias)} vias em {SAIDA.stat().st_size // 1024} KB")
    print("Dados do OpenStreetMap, licença ODbL.")


if __name__ == "__main__":
    main()
