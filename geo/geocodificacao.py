"""Endereço em texto para coordenada, pelo Nominatim do OpenStreetMap.

Serve pro cadastro de endereço da compradora: digitado o endereço, o botão
busca a coordenada em vez de a pessoa ter que saber a latitude dela. Falha é
tratada como "não achei", porque sem coordenada o endereço continua válido,
só não entra no mapa nem na ordenação por distância.
"""

from __future__ import annotations

from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim

from dominio.coordenada import Coordenada

AGENTE = "marisques-undb/1.0"

# A política do Nominatim é de uma consulta por segundo e identificação no
# agente. Aqui a busca só sai de clique em botão, então o ritmo é humano.
TEMPO_LIMITE = 8

# Recorte do Maranhão. Sem isso, "Rua da Paz" acha uma em Minas.
CAIXA = ((-10.3, -48.8), (-1.0, -41.7))

FALHAS = (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError, OSError)

_cliente: Nominatim | None = None


def _cliente_nominatim() -> Nominatim:
    global _cliente
    if _cliente is None:
        _cliente = Nominatim(user_agent=AGENTE, timeout=TEMPO_LIMITE)
    return _cliente


def geocodificar(consulta: str) -> tuple[Coordenada, str] | None:
    """Coordenada e endereço normalizado, ou `None` se não achar."""
    if not consulta or not consulta.strip():
        return None
    try:
        achado = _cliente_nominatim().geocode(
            consulta.strip(),
            country_codes="br",
            viewbox=CAIXA,
            bounded=True,
            exactly_one=True,
        )
    except FALHAS:
        return None
    if achado is None:
        return None
    try:
        return Coordenada(achado.latitude, achado.longitude), achado.address
    except Exception:
        return None


def endereco_de(coordenada: Coordenada | None) -> str | None:
    """Caminho inverso: coordenada para endereço escrito."""
    if coordenada is None:
        return None
    try:
        achado = _cliente_nominatim().reverse(coordenada.par, exactly_one=True)
    except FALHAS:
        return None
    return achado.address if achado else None
