"""Mapa de tiles do OpenStreetMap dentro da aplicação (extensão além de P10).

O `ui/mapa.py` desenha a cidade à mão com QPainter e funciona sem internet,
mas é um desenho: não dá zoom, não arrasta, não tem nome de rua. Aqui entra
o mapa de verdade — Leaflet com tiles do OpenStreetMap dentro de um
QWebEngineView —, que é o que permite aproximar, afastar, arrastar e cravar
o pino no lugar certo no cadastro de endereço.

Nada disso é obrigatório: se o Qt vier sem WebEngine ou a máquina estiver
offline, a página avisa e o widget cai no mapa pintado, com os mesmos dados.
Por isso toda chamada é espelhada nos dois.

Os tiles são os do próprio OpenStreetMap (ODbL), com uma camada opcional de
satélite da Esri: nenhum dos dois pede chave de API, então o sistema abre em
qualquer máquina. O crédito aparece no canto do mapa, como as licenças exigem.
"""

from __future__ import annotations

import json
from string import Template

from PySide6.QtCore import QSize, QUrl, Signal
from PySide6.QtWidgets import QStackedLayout, QWidget

from dominio.coordenada import Coordenada
from dominio.rota import Rota
from ui import estilo
from ui.mapa import WidgetMapa

try:  # pragma: no cover - depende do Qt instalado na máquina
    from PySide6.QtWebEngineCore import QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView

    TEM_WEBENGINE = True
except ImportError:  # pragma: no cover
    TEM_WEBENGINE = False

# Base falsa só pra página contar como https: o Chromium recusa carregar o
# Leaflet de um CDN dentro de um documento sem origem.
BASE = "https://mapa.marisques.undb/"

# Identificação no User-Agent, que é o que a política de uso dos servidores
# de tile pede de quem não é navegador.
AGENTE = "marisques-undb/1.0"

PAGINA = Template("""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body, #mapa { height: 100%; margin: 0; }
  body { background: $FUNDO; font-family: sans-serif; }
  .leaflet-container { background: $FUNDO; }
  .etiqueta {
    background: $SUPERFICIE; color: $TEXTO; border: 1px solid $BORDA;
    border-radius: 8px; padding: 3px 8px; font-size: 12px; font-weight: 600;
    box-shadow: 0 2px 6px rgba(0,0,0,.12); white-space: nowrap;
  }
  .etiqueta::before { border-top-color: $BORDA !important; }
  .moto {
    font-size: 17px; line-height: 28px; text-align: center;
    background: $SUPERFICIE; border-radius: 50%;
    box-shadow: 0 2px 6px rgba(0,0,0,.35);
  }
  #dica {
    position: absolute; right: 10px; bottom: 26px; z-index: 500;
    background: $SUPERFICIE; color: $TEXTO_SUAVE; border: 1px solid $BORDA;
    border-radius: 999px; padding: 3px 10px; font-size: 11px;
    box-shadow: 0 2px 8px rgba(0,0,0,.12); display: none;
  }
</style></head>
<body><div id="mapa"></div>
<div id="dica">clique para marcar o local</div>
<script>
function avisar(texto) { document.title = texto; }

if (!window.L) {
  // Sem internet o Leaflet não chega; quem assume é o mapa pintado.
  avisar("falhou");
} else {
  var mapa = L.map('mapa', { zoomControl: true, attributionControl: true })
              .setView([-2.53, -44.3], 12);
  // Tiles sem chave de API de propósito: o trabalho tem que abrir na máquina
  // de quem corrigir, sem cadastro em serviço nenhum.
  var ruas = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; OpenStreetMap contributors (ODbL)'
  }).addTo(mapa);
  var satelite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/' +
    'MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, attribution: 'Imagens &copy; Esri, Maxar, Earthstar' }
  );
  L.control.layers({ 'Mapa': ruas, 'Satélite': satelite },
                   {}, { position: 'topright' }).addTo(mapa);
  L.control.scale({ imperial: false }).addTo(mapa);

  var camada = L.layerGroup().addTo(mapa);
  var alfinete = null;     // pino arrastável do modo de escolha
  var moto = null;         // marcador do entregador, movido quadro a quadro
  var escolhendo = false;

  function etiqueta(marca, texto) {
    if (texto) {
      marca.bindTooltip(texto, { permanent: true, direction: 'top',
                                 className: 'etiqueta', offset: [0, -10] });
    }
    return marca;
  }

  function bolha(lat, lon, texto, cor) {
    return etiqueta(L.circleMarker([lat, lon], {
      radius: 8, color: '#ffffff', weight: 3,
      fillColor: cor, fillOpacity: 1
    }).addTo(camada), texto);
  }

  function enquadrar(pontos, zoom) {
    if (!pontos.length) { return; }
    if (pontos.length === 1) { mapa.setView(pontos[0], zoom || 16); return; }
    mapa.fitBounds(L.latLngBounds(pontos).pad(0.18));
  }

  // Linha com contorno branco embaixo: sem isso a rota some no meio das
  // ruas coloridas do mapa, que é desenho e não enfeite.
  function traco(pontos, estilo) {
    L.polyline(pontos, { color: '#ffffff', weight: (estilo.weight || 4) + 4,
                         opacity: .75, lineCap: 'round',
                         lineJoin: 'round' }).addTo(camada);
    L.polyline(pontos, Object.assign({ color: '$PRIMARIA', lineCap: 'round',
                                       lineJoin: 'round' }, estilo))
      .addTo(camada);
  }

  window.app = {
    // Um endereço sozinho: é o mapa do cadastro.
    ponto: function (dados) {
      camada.clearLayers();
      alfinete = null;
      if (dados.lat === null) { return; }
      if (escolhendo) {
        alfinete = etiqueta(L.marker([dados.lat, dados.lon],
                                     { draggable: true }).addTo(camada),
                            dados.rotulo);
        alfinete.on('dragend', function (e) {
          var p = e.target.getLatLng();
          avisar('escolha|' + p.lat + '|' + p.lng);
        });
      } else {
        bolha(dados.lat, dados.lon, dados.rotulo, '$PRIMARIA');
      }
      enquadrar([[dados.lat, dados.lon]], dados.zoom);
    },

    // Trajeto da entrega: rota prevista, caminho andado e o entregador.
    rota: function (d) {
      camada.clearLayers();
      alfinete = null;
      var vistos = [];
      if (d.rota && d.rota.length) {
        traco(d.rota, { weight: 4, opacity: .8, dashArray: '3 7' });
        vistos = vistos.concat(d.rota);
      }
      if (d.trajeto && d.trajeto.length > 1) {
        traco(d.trajeto, { weight: 5, opacity: 1 });
        vistos = vistos.concat(d.trajeto);
      }
      if (d.origem) {
        bolha(d.origem[0], d.origem[1], d.rotulo_origem, '$PRIMARIA');
        vistos.push(d.origem);
      }
      if (d.destino) {
        bolha(d.destino[0], d.destino[1], d.rotulo_destino, '$VERMELHO');
        vistos.push(d.destino);
      }
      moto = null;
      if (d.posicao) {
        this.mover(d);
        vistos.push(d.posicao);
      }
      enquadrar(vistos);
    },

    // Só o entregador andou: mexer no marcador é bem mais barato do que
    // redesenhar uma rota de centenas de pontos a cada quadro da animação.
    mover: function (d) {
      if (!d.posicao) { return; }
      if (moto) { moto.setLatLng(d.posicao); return; }
      moto = L.marker(d.posicao, {
        zIndexOffset: 1000,
        icon: L.divIcon({ html: '\\uD83D\\uDEF5', className: 'moto',
                          iconSize: [28, 28], iconAnchor: [14, 14] })
      }).addTo(camada);
    },

    // Modo de escolha: clicar no mapa crava o pino e devolve a coordenada.
    seletor: function (ligado) {
      escolhendo = ligado;
      document.getElementById('dica').style.display = ligado ? 'block' : 'none';
    }
  };

  mapa.on('click', function (e) {
    if (!escolhendo) { return; }
    avisar('escolha|' + e.latlng.lat + '|' + e.latlng.lng);
  });

  avisar('pronto');
}
</script></body></html>
""").safe_substitute(
    FUNDO=estilo.FUNDO,
    SUPERFICIE=estilo.SUPERFICIE,
    BORDA=estilo.BORDA,
    TEXTO=estilo.TEXTO,
    TEXTO_SUAVE=estilo.TEXTO_SUAVE,
    PRIMARIA=estilo.PRIMARIA,
    VERMELHO=estilo.VERMELHO,
)


class MapaWeb(QWidget):
    """Mapa navegável com tiles, e o mapa pintado como plano B.

    A API é a mesma do `WidgetMapa` de propósito: as telas chamam
    `definir_rota`/`definir_ponto` sem saber qual dos dois está na frente.
    """

    # Coordenada que a pessoa marcou clicando ou arrastando o pino.
    ponto_escolhido = Signal(object)

    def sizeHint(self) -> QSize:  # noqa: N802, nome exigido pelo Qt
        """Tamanho de conforto do mapa.

        O mínimo é piso pra tela curta; é esta medida que faz a janela que
        abriga o mapa nascer com tamanho de mapa, e não de tarja.
        """
        return QSize(520, 340)

    def __init__(self, pai=None, seletor: bool = False) -> None:
        super().__init__(pai)
        self.setMinimumHeight(220)
        self._seletor = seletor
        self._pronto = False
        # Chamadas que chegaram antes de a página carregar. Sem a fila, o
        # primeiro endereço aberto não aparecia no mapa.
        self._fila: list[tuple[str, object]] = []
        # Assinatura do último traçado desenhado. Serve pra não reenviar uma
        # rota de centenas de pontos quando só o entregador andou um metro.
        self._assinatura: tuple | None = None

        self.pintado = WidgetMapa()
        # Quem manda na altura mínima é este widget, não o mapa pintado de
        # dentro: com dois mínimos diferentes na pilha o layout do diálogo
        # encolhia 60 px quando a página carregava e espremia os campos.
        self.pintado.setMinimumHeight(0)
        self.pilha = QStackedLayout(self)
        self.pilha.setContentsMargins(0, 0, 0, 0)
        self.pilha.addWidget(self.pintado)

        self.view = self._criar_view()
        if self.view is not None:
            self.pilha.addWidget(self.view)
            self.view.setHtml(PAGINA, QUrl(BASE))

    def _criar_view(self):
        if not TEM_WEBENGINE:
            return None
        perfil = QWebEngineProfile.defaultProfile()
        if AGENTE not in perfil.httpUserAgent():
            perfil.setHttpUserAgent(f"{perfil.httpUserAgent()} {AGENTE}")
        view = QWebEngineView(self)
        # O canal de volta é o título da página: o JS escreve nele, o Qt
        # avisa aqui. Evita montar um QWebChannel só pra dois recados.
        view.titleChanged.connect(self._recado)
        return view

    # estado vindo da página

    def _recado(self, texto: str) -> None:
        if texto == "pronto":
            self._pronto = True
            self.pilha.setCurrentWidget(self.view)
            # O seletor primeiro: é ele que decide se o ponto da fila vira
            # alfinete arrastável ou bolinha fixa.
            self._js("seletor", self._seletor)
            for nome, dados in self._fila:
                self._js(nome, dados)
            self._fila.clear()
            return
        if texto == "falhou":
            # Offline: fica no mapa pintado, que não depende de servidor.
            self.pilha.setCurrentWidget(self.pintado)
            return
        if texto.startswith("escolha|"):
            _, lat, lon = texto.split("|")
            self.ponto_escolhido.emit(Coordenada(float(lat), float(lon)))

    def _js(self, nome: str, dados: object) -> None:
        if not self._pronto:
            self._fila = [(n, d) for n, d in self._fila if n != nome]
            self._fila.append((nome, dados))
            return
        self.view.page().runJavaScript(f"app.{nome}({json.dumps(dados)})")

    # API igual à do WidgetMapa

    @property
    def vazio(self) -> str:
        return self.pintado.vazio

    @vazio.setter
    def vazio(self, texto: str) -> None:
        self.pintado.vazio = texto

    def definir_ponto(self, coordenada: Coordenada | None, rotulo: str = "") -> None:
        self.pintado.definir_ponto(coordenada, rotulo)
        self._js(
            "ponto",
            {
                "lat": coordenada.latitude if coordenada else None,
                "lon": coordenada.longitude if coordenada else None,
                "rotulo": rotulo,
                "zoom": 17,
            },
        )

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
        self.pintado.definir_rota(
            origem, destino, trajeto, posicao, rotulo_origem, rotulo_destino, rota
        )
        dados = {
            "origem": _par(origem),
            "destino": _par(destino),
            "posicao": _par(posicao),
            "trajeto": [_par(c) for c in (trajeto or []) if c],
            "rota": [_par(c) for c in (rota.pontos if rota else ())],
            "rotulo_origem": rotulo_origem,
            "rotulo_destino": rotulo_destino,
        }
        assinatura = (
            dados["origem"],
            dados["destino"],
            len(dados["trajeto"]),
            len(dados["rota"]),
            rotulo_origem,
            rotulo_destino,
        )
        if assinatura == self._assinatura:
            self._js("mover", {"posicao": dados["posicao"]})
            return
        self._assinatura = assinatura
        self._js("rota", dados)

    def permitir_escolha(self, ligado: bool) -> None:
        """Liga o clique que marca o ponto no mapa."""
        self._seletor = ligado
        self._js("seletor", ligado)


def _par(coordenada: Coordenada | None) -> list[float] | None:
    return [coordenada.latitude, coordenada.longitude] if coordenada else None
