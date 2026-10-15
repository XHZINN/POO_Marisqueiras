# Marisquês: Sistema Marisqueiras da Ilha

Implementação das classes e métodos do projeto **Marisqueiras da Ilha**
(POO, 4º período, docente Aline Maya), com interface gráfica em PySide6 e
persistência em SQLite.

Comercialização direta de mariscos entre **empresas** das marisqueiras e
**empresas compradoras** (modelo B2B, RN01), tendo Vila Maresia, Raposa/MA
como caso inicial (P4).

---

## Como executar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python main.py
```

Na primeira execução o arquivo `marisqueiras.db` é criado e populado com
dados de demonstração (3 empresas das marisqueiras, 2 compradoras, 10
produtos, 3 endereços de entrega, 5 pedidos e 2 avaliações). Para recomeçar
do zero, apague o `marisqueiras.db` e rode de novo.

O mapa de ruas é carregado da internet (*tiles* do OpenStreetMap). Sem
conexão nada quebra: o sistema cai para o mapa desenhado localmente com a
malha viária de `dados/`, e as rotas do seed também já vêm no arquivo.

### Rodar os testes

```bash
.venv/bin/python -m pytest -q
```

**173 testes** (63 de domínio, 61 das extensões, 34 de interface e 15 de
repositório), nenhum deles precisa de banco nem de janela aberta para as
regras de negócio. Cada teste cita no nome a regra que verifica
(`test_rn14_pedido_nao_reune_empresas_diferentes`). Os de interface rodam
com `QT_QPA_PLATFORM=offscreen` e os de rota usam o cache de `dados/`, então
a suíte roda inteira sem internet.

---

## As 7 classes e os 17 métodos exigidos

| Classe | Métodos da atividade | Arquivo |
|---|---|---|
| `Empresa` *(abstrata)* | `tipo()`, `consultar_produtos()` *(abstratos)* | `dominio/empresa.py` |
| `EmpresaMarisqueira` | `cadastrar_produto`, `alterar_quantidade`, `receber_pedido`, `aceitar_pedido`, `rejeitar_pedido`, `solicitar_ajuste`, `atualizar_status_entrega` | `dominio/empresa.py` |
| `EmpresaCompradora` | `consultar_produtos`, `comparar_produtos`, `realizar_pedido`, `avaliar_empresa` | `dominio/empresa.py` |
| `Produto` | `verificar_disponibilidade`, `atualizar_quantidade` | `dominio/produto.py` |
| `Pedido` | `adicionar_item` | `dominio/pedido.py` |
| `ItemPedido` | `validar_quantidade`, `verificar_disponibilidade` | `dominio/item_pedido.py` |
| `Avaliacao` | `registrar_nota` | `dominio/avaliacao.py` |

### Métodos complementares

O enunciado lista o mínimo. Acrescentei estes porque sem eles o fluxo de P7
ficava truncado:

| Classe | Método | Por quê |
|---|---|---|
| `EmpresaCompradora` | `responder_ajuste` | P7 prevê ajuste, mas sem resposta da compradora o pedido ficava parado para sempre |
| `EmpresaCompradora` | `cancelar_pedido` | saída para quando o ajuste possível não atende |
| `EmpresaCompradora` | `confirmar_entrega` | quem recebe a mercadoria é quem atesta o recebimento |
| `EmpresaMarisqueira` | `alterar_preco_produto` | RN07 exige travar o preço durante a venda |
| `Empresa` | `notificar` | RN22 fala em informar o status, e informar exige alguém sendo avisado |

`verificar_disponibilidade` aparece **duas vezes** no enunciado porque
existe em dois níveis, com perguntas diferentes:

- `Produto.verificar_disponibilidade(qtd)`: *"tenho essa quantidade em estoque?"*
- `ItemPedido.verificar_disponibilidade()`: *"a minha linha cabe no estoque do meu produto?"* (delega ao de cima)

Mesma lógica em `EmpresaMarisqueira.alterar_quantidade` (porta de entrada
que autoriza) vs `Produto.atualizar_quantidade` (o produto é dono do próprio
estado).

---

## Arquitetura

```
Sistema/
├── main.py                      liga as camadas; nada mais
├── dominio/                     regras de negócio, Python puro
│   ├── enums.py                 conjuntos fechados (categoria, status, situação)
│   ├── excecoes.py              hierarquia de erros de negócio
│   ├── empresa.py               Empresa (ABC) + Marisqueira + Compradora
│   ├── produto.py               RN04 a RN09
│   ├── item_pedido.py           RN07, RN15, RN18
│   ├── pedido.py                RN13, RN14, máquina de estados (P7)
│   ├── avaliacao.py             RN21, P24
│   ├── notificacao.py           avisos entre as duas pontas (RN22)
│   ├── coordenada.py            latitude/longitude e distância (extensão)
│   ├── endereco.py              endereço de entrega cadastrado (extensão)
│   ├── rota.py                  traçado por ruas, pontos e distância (extensão)
│   ├── rastreabilidade.py       ficha de origem do lote (extensão)
│   └── entrega.py               posições do trajeto (extensão)
├── geo/                         serviços geográficos externos (extensão)
│   ├── geocodificacao.py        endereço em texto → coordenada (Nominatim)
│   ├── roteador.py              rota por ruas (OSRM) + cache em disco
│   └── malha.py                 vias do OpenStreetMap para desenhar o mapa
├── dados/                       insumos geográficos versionados
│   ├── malha_viaria.json.gz     ~22 mil vias da região, 220 KB
│   ├── rotas.json               rotas já consultadas (abre sem internet)
│   └── baixar_malha.py          regera a malha a partir do Overpass
├── repositorio/                 única camada que conhece SQL
│   ├── schema.sql               10 tabelas
│   ├── conexao.py               conexão + PRAGMAs + migração de colunas
│   ├── repositorio.py           objeto para tabela e volta
│   └── seed.py                  dados de demonstração
├── ui/                          PySide6
│   ├── estilo.py                folha de estilo (QSS)
│   ├── componentes.py           tabela, formatação, tratamento de erro
│   ├── janela_principal.py      seleção de perfil e navegação
│   ├── painel_marisqueira.py    produtos, pedidos, prazo, avaliações
│   ├── painel_compradora.py     busca, comparação, pedido, avaliação
│   ├── painel_notificacoes.py   caixa de avisos, usada pelos dois perfis
│   ├── dialogo_enderecos.py     cadastro de endereços de entrega
│   ├── mapa_web.py              mapa navegável (Leaflet sobre QtWebEngine)
│   ├── mapa.py                  mapa desenhado com QPainter, usado sem internet
│   └── dialogo_simulacao.py     simulação da entrega seguindo a rota
└── tests/                       173 testes
```

A regra da dependência: as flechas apontam só para dentro.
`dominio/` não importa `repositorio/`, `geo/` nem `ui/`; `repositorio/` e
`geo/` importam `dominio/`; `ui/` importa todos. `geo/` é a única pasta que
fala com serviço de fora, e entrega sempre objeto de domínio (`Coordenada`,
`Rota`) — é o que permite testar o prazo e o trajeto sem rede. Isso é o que
deixa testar todas as regras de negócio sem abrir banco nem janela, e é o
que os 63 testes de `tests/test_dominio.py` comprovam.

---

## Onde cada regra de negócio está implementada

| Regra | Onde |
|---|---|
| RN01 B2B, sem consumidor final | `Empresa` só tem duas subclasses |
| RN02 1 habitação = 1 empresa | `empresa.cnpj` com `UNIQUE` no banco |
| RN03 marisqueira individual | `EmpresaMarisqueira` não exige nº de integrantes |
| RN04 venda por kg | `Produto.preco_por_kg`, `ItemPedido.quantidade_kg` |
| RN05 mínimo 25 kg | `Produto.QUANTIDADE_MINIMA_KG` |
| RN06 fresco ≠ congelado | `Categoria` + `UNIQUE (empresa_id, nome, categoria)` |
| RN07 preço travado na venda | `ItemPedido.preco_unitario` (cópia) + `alterar_preco_produto` |
| RN08 estoque alterável | `Produto.atualizar_quantidade` |
| RN09 estoque zero = indisponível | `Produto.esta_disponivel`; aceita `0` |
| RN10 filtros de busca | `EmpresaCompradora.consultar_produtos` |
| RN11 ordenações | `EmpresaCompradora._ordenar` |
| RN12 visibilidade | `consultar_produtos` **abstrato** em `Empresa` (polimorfismo) |
| RN13 dados do pedido | `Pedido.__init__`; o endereço vem do cadastro (`Endereco`) e o prazo é estimado pelo sistema, não digitado pela compradora — ver *Extensões* |
| RN14 uma empresa por pedido | `Pedido.adicionar_item` |
| RN15 25 kg por item | `ItemPedido.validar_quantidade` |
| RN16 sem mínimo em dinheiro | `Pedido.total` não valida piso |
| RN17 sem máximo fixo | limite é só o estoque |
| RN18 impedir e informar | `QuantidadeIndisponivel` carrega os números |
| RN19 empresa fica sem estoque | `EmpresaMarisqueira.situacao` |
| RN20 verde/laranja/vermelho | `SituacaoEmpresa` (cor no próprio enum) |
| RN21 avaliar após a compra | `avaliar_empresa` exige status `ENTREGUE`, que só a compradora atinge |
| RN22 status de entrega | `definir_status_entrega` (marisqueira) + `confirmar_entrega` (compradora) |
| RN23 frete no preço | sem campo de frete separado |

---

## Fluxo do pedido implementado (P7)

```
compradora                                     marisqueira
    |                                               |
    |-- realizar_pedido ------------------------->  | aguardando análise
    |                                               |
    |  <---------------- solicitar_ajuste --------  | ajuste solicitado
    |-- responder_ajuste ------------------------>  | aguardando análise
    |-- cancelar_pedido                             | cancelado
    |                                               |
    |  <---------------- rejeitar_pedido ---------  | rejeitado
    |  <-- aceitar_pedido(prazo) -----------------  | aceito (baixa estoque,
    |                                               |  confirma o prazo)
    |  <-- atualizar_status_entrega(saiu) --------  | em preparação
    |-- confirmar_entrega ----------------------->  | entregue
    |-- avaliar_empresa ------------------------->  |
```

Cada seta gera uma notificação para a outra ponta, visível na aba Avisos.

### Três coisas que vão além da letra dos requisitos

**Quem confirma a entrega.** RN22 diz que a entrega é feita pela marisqueira
e que o aplicativo permite atualizar o status. Aqui a marisqueira informa até
`Saiu para entrega` e a **compradora** confirma o recebimento. O motivo:
"entregue" é um fato sobre o recebimento, e só quem recebe pode atestá-lo.
Isso também deixa RN21 coerente, porque a avaliação passa a ser liberada por
quem recebeu. Para voltar ao comportamento literal de RN22, bastam duas
mudanças: incluir `ENTREGUE` em `PainelMarisqueira.STATUS_INFORMAVEIS` e
remover a guarda em `Pedido.definir_status_entrega`.

**Cancelamento.** P7 não prevê cancelar, mas sem isso um pedido com ajuste
solicitado que a compradora não pode atender fica parado para sempre.
`StatusPedido.CANCELADO` é um estado final, só alcançável antes do aceite.

**Prazo de entrega.** RN13 põe o prazo entre os dados que a compradora
informa; aqui quem decide é a marisqueira, que é quem tem como cumprir. O
porquê e o como estão em
*[O prazo é de quem entrega, não de quem compra](#o-prazo-é-de-quem-entrega-não-de-quem-compra)*.

---

## Extensões além dos requisitos

Os requisitos marcam estes pontos como fora de escopo. Eles foram
implementados depois, por decisão de projeto, e ficam separados na pasta de
testes (`tests/test_extensoes.py`, 61 testes) para dar para distinguir o que
é exigência da atividade do que é acréscimo.

| Ponto | O que os requisitos dizem | O que foi feito |
|---|---|---|
| Forma de pagamento | P27 deixa fora do escopo | `FormaPagamento` e `StatusPagamento`, com fluxo em duas pontas: a compradora informa, a marisqueira confirma. Forma antecipada (PIX, transferência, boleto à vista) trava o despacho até o pagamento ser confirmado; boleto a prazo sai antes |
| Rastreabilidade e origem | P2 marca como possibilidade futura | `Rastreabilidade` com lote, data e local de coleta, responsável e método. A ficha é copiada para o item na compra, pela mesma razão de RN07 com o preço: o lote vendido não muda depois |
| Geolocalização real | P10 não prevê coordenadas | `Coordenada` com distância geodésica via `geopy`. A ordenação por proximidade de RN11 passou de comparação de texto para distância em km, e entrou um filtro de raio na busca |
| Endereço de entrega | RN13 trata o endereço como campo de texto do pedido | `Endereco` com apelido, CEP, referência e coordenada, cadastrado uma vez e escolhido na compra. O pedido guarda uma **cópia** do endereço (colunas `entrega_*`), mesma razão de RN07 com o preço: editar o cadastro amanhã não reescreve para onde este pedido foi |
| Quem decide o prazo | RN13 lista o prazo entre os dados que a compradora informa | O prazo passou a ser estimado (preparo da marisqueira + tempo da rota) e **confirmado por quem entrega**, no aceite do pedido. Ver abaixo |
| Rota por ruas | P10 diz que o app só informa o status | `Rota` traçada pelo OSRM e desenhada sobre o mapa. A distância do prazo deixou de ser linha reta e passou a ser quilômetro de rua |
| Mapa navegável | Os requisitos não falam em mapa | `ui/mapa_web.py`: Leaflet com *tiles* do OpenStreetMap dentro do Qt, com zoom, arrasto, satélite e pino arrastável para marcar o endereço no clique. Sem internet, cai no mapa desenhado com `QPainter` sobre a malha local |
| Rastreamento em tempo real | P10 diz que o app só informa o status | `EventoEntrega` append-only com as posições do trajeto e simulação que anda sozinha pelo percurso. A tela da compradora relê o trajeto num `QTimer` de 2 s |

### O prazo é de quem entrega, não de quem compra

RN13 põe o prazo de entrega entre os dados do pedido, do lado da compradora.
Implementado ao pé da letra, isso é um campo onde a compradora digita
"1 dia" — e nenhuma marisqueira teria como cumprir cem pedidos pedindo
amanhã. Prazo não é preferência de quem compra, é capacidade de quem entrega.

Como ficou:

1. A marisqueira declara suas **condições de entrega** (aba Pedidos →
   *Condições de entrega*): quantas horas leva para preparar e até quantos km
   entrega (`EmpresaMarisqueira.configurar_entrega`).
2. No carrinho, a compradora **vê** a previsão calculada — preparo + tempo da
   rota até o endereço escolhido — marcada como *a confirmar*. Se o endereço
   estiver fora do raio, o aviso aparece ali, antes de montar o pedido
   inteiro (`EmpresaMarisqueira.atende`).
3. No aceite, a marisqueira confirma ou corrige o prazo
   (`Pedido.definir_prazo_entrega`), e só aí ele vira compromisso
   (`prazo_confirmado`). A compradora é notificada com a data.

`Pedido.resumo_prazo` é quem diz a diferença na tela: *"Previsão de 15/10 às
10:52 (a confirmar)"* antes do aceite, *"Entrega até … (prazo confirmado)"*
depois.

### A rota e o mapa

`geo/roteador.py` consulta o **OSRM** (`router.project-osrm.org`), o roteador
do OpenStreetMap, e guarda o traçado em `dados/rotas.json`. As rotas do seed
já estão no arquivo, então o programa abre, desenha o percurso e calcula o
prazo **sem internet**; sem rede e sem cache, cai para a linha reta e avisa
isso na tela, em vez de travar.

O mapa é o **Leaflet** rodando dentro de um `QWebEngineView`
(`ui/mapa_web.py`), com os *tiles* do OpenStreetMap e uma camada de satélite
do Esri — dá zoom, arrasta, troca de camada e mostra escala, que é o que se
espera de um mapa hoje. Nenhum dos dois provedores pede chave de API.

Sem internet (ou sem o QtWebEngine instalado) o mapa não some: a mesma classe
mantém atrás dele o mapa desenhado com `QPainter` (`ui/mapa.py`) sobre a
malha viária local — `dados/malha_viaria.json.gz` traz cerca de 22 mil vias
da região em 220 KB (coordenadas em inteiros e por diferença do ponto
anterior), e `dados/baixar_malha.py` regera o arquivo pelo Overpass. Ali a
longitude é corrigida por `cos(latitude)`, senão o trajeto sairia esticado na
horizontal. As duas versões recebem as mesmas chamadas, então a tela não
sabe qual está na frente.

O endereço vira coordenada de dois jeitos no cadastro: pelo **Nominatim**
(`geo/geocodificacao.py`), no botão *Buscar no mapa*, ou **clicando no mapa**
— o pino é arrastável, e é essa a saída para o endereço que o geocodificador
erra ou não conhece, como sítio e galpão sem número.

### A simulação da entrega

Quando a marisqueira marca *Saiu para entrega*, o sistema oferece abrir a
simulação. Ela **anda sozinha** pelo percurso — quem acompanha uma entrega
não fica clicando em "próximo ponto" —, com velocidade de 1× a 8×, barra de
progresso e o quanto falta em km e minutos. A seta do entregador aponta para
onde a rua vira.

Cada quadro move o entregador um pedaço da rota real (`Rota.ponto_em`), mas
só 18 posições viram `EventoEntrega` no banco: gravar todo quadro encheria a
tabela de milhares de linhas para uma viagem de meia hora. O que a compradora
vê no mapa dela é o resultado desses pontos, e sobrevive a fechar o programa.

### Créditos dos dados geográficos

Vias, *tiles*, geocodificação e rotas vêm do **OpenStreetMap**, sob
[ODbL](https://www.openstreetmap.org/copyright) — por isso o crédito
`© OpenStreetMap contributors (ODbL)` aparece no canto de todo mapa.
A camada de satélite é do **Esri World Imagery**, creditada no mesmo canto
quando está ativa. Nominatim e OSRM são os serviços públicos do projeto, usados aqui
em ritmo de clique humano e com resultado em cache, como as políticas de uso
deles pedem.

### Fora de escopo ainda hoje

- **Entregador de verdade**: a posição vem da simulação, não de um aparelho
  no caminhão. O que o sistema já tem pronto é o lado de receber posições
  (`registrar_posicao`), que é onde um GPS entraria.
- **Trânsito e janela de horário**: o tempo da rota usa a velocidade média do
  OSRM; não há previsão de congestionamento nem horário de funcionamento
  entrando no cálculo do prazo.
