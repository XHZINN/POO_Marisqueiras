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
produtos, 5 pedidos e 2 avaliações). Para recomeçar do zero, apague o
`marisqueiras.db` e rode de novo.

### Rodar os testes

```bash
.venv/bin/python -m pytest -q
```

**127 testes**, nenhum deles precisa de banco nem de janela aberta para as
regras de negócio. Cada teste cita no nome a regra que verifica
(`test_rn14_pedido_nao_reune_empresas_diferentes`).

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
│   ├── rastreabilidade.py       ficha de origem do lote (extensão)
│   └── entrega.py               posições do trajeto (extensão)
├── repositorio/                 única camada que conhece SQL
│   ├── schema.sql               5 tabelas
│   ├── conexao.py               conexão + PRAGMAs
│   ├── repositorio.py           objeto para tabela e volta
│   └── seed.py                  dados de demonstração
├── ui/                          PySide6
│   ├── estilo.py                folha de estilo (QSS)
│   ├── componentes.py           tabela, formatação, tratamento de erro
│   ├── janela_principal.py      seleção de perfil e navegação
│   ├── painel_marisqueira.py    produtos, pedidos, avaliações
│   ├── painel_compradora.py     busca, comparação, pedido, avaliação
│   ├── painel_notificacoes.py   caixa de avisos, usada pelos dois perfis
│   ├── mapa.py                  mapa do trajeto, desenhado com QPainter
│   └── dialogo_simulacao.py     simulação da entrega de A até B
└── tests/                       127 testes
```

A regra da dependência: as flechas apontam só para dentro.
`dominio/` não importa `repositorio/` nem `ui/`; `repositorio/` importa
`dominio/`; `ui/` importa os dois. É isso que permite testar todas as
regras de negócio sem abrir banco nem janela, e é o que os 44 testes de
`tests/test_dominio.py` comprovam.

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
| RN13 dados do pedido | `Pedido.__init__` |
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
    |  <---------------- aceitar_pedido ----------  | aceito (baixa estoque)
    |  <-- atualizar_status_entrega(saiu) --------  | em preparação
    |-- confirmar_entrega ----------------------->  | entregue
    |-- avaliar_empresa ------------------------->  |
```

Cada seta gera uma notificação para a outra ponta, visível na aba Avisos.

### Duas coisas que vão além da letra dos requisitos

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

---

## Extensões além dos requisitos

Os requisitos marcam estes quatro pontos como fora de escopo. Eles foram
implementados depois, por decisão de projeto, e ficam separados na pasta de
testes (`tests/test_extensoes.py`) para dar para distinguir o que é exigência
da atividade do que é acréscimo.

| Ponto | O que os requisitos dizem | O que foi feito |
|---|---|---|
| Forma de pagamento | P27 deixa fora do escopo | `FormaPagamento` e `StatusPagamento`, com fluxo em duas pontas: a compradora informa, a marisqueira confirma. Forma antecipada (PIX, transferência, boleto à vista) trava o despacho até o pagamento ser confirmado; boleto a prazo sai antes |
| Rastreabilidade e origem | P2 marca como possibilidade futura | `Rastreabilidade` com lote, data e local de coleta, responsável e método. A ficha é copiada para o item na compra, pela mesma razão de RN07 com o preço: o lote vendido não muda depois |
| Rastreamento em tempo real | P10 diz que o app só informa o status | `EventoEntrega` append-only com as posições do trajeto, mapa desenhado em `ui/mapa.py` e simulação do entregador saindo de A e chegando em B. A tela da compradora relê o trajeto num `QTimer` de 2 s |
| Geolocalização real | P10 não prevê coordenadas | `Coordenada` com distância geodésica via `geopy`. A ordenação por proximidade de RN11 passou de comparação de texto para distância em km, e entrou um filtro de raio na busca |

### A simulação da entrega

Na aba **Pedidos** da marisqueira, com um pedido em trânsito selecionado, o
botão **Acompanhar entrega** abre o mapa com o trajeto. Cada passo da
simulação chama `registrar_posicao`, que grava um `EventoEntrega` de verdade:
o que a compradora vê no mapa dela é o resultado desses passos, e sobrevive a
fechar o programa.

O mapa é um plano das coordenadas reais desenhado com `QPainter`, com escala
em km, não um mapa de ruas. Mapa de ruas exigiria baixar tiles de um
servidor, o que deixaria o programa dependente de internet para abrir uma
tela. A longitude é corrigida por `cos(latitude)`, senão o trajeto sairia
esticado na horizontal.

### Fora de escopo ainda hoje

- **Geocodificação de endereço**: as coordenadas são cadastradas, não
  resolvidas a partir do texto do endereço. `geopy` tem geocoders, mas todos
  dependem de rede.
- **Rota por malha viária**: a distância e o trajeto são em linha reta. Rota
  real precisaria de serviço de roteamento.
