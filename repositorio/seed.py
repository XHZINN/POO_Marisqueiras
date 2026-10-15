"""Dados de demonstração: Vila Maresia, Raposa/MA (P4).

Executado apenas quando o banco está vazio, para que o sistema abra com
conteúdo navegável em vez de telas em branco.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal

from dominio.coordenada import (
    ARACAGI,
    MERCADO_DO_PEIXE,
    RAPOSA,
    SAO_LUIS_CENTRO,
    VILA_MARESIA,
    Coordenada,
)
from dominio.empresa import EmpresaCompradora, EmpresaMarisqueira
from dominio.endereco import Endereco
from dominio.enums import (
    Categoria,
    FormaPagamento,
    MetodoColeta,
    StatusEntrega,
)
from repositorio.repositorio import Repositorio


def popular(repo: Repositorio) -> None:
    """Cria empresas, produtos, um histórico de pedidos e avaliações."""

    # Empresas das marisqueiras (RN02, RN03)
    maresia = repo.salvar_empresa(
        EmpresaMarisqueira(
            nome="Marisqueiras Vila Maresia",
            cnpj="11.111.111/0001-11",
            email="contato@vilamaresia.com.br",
            telefone="(98) 98800-1001",
            endereco="Rua da Praia, 10, Vila Maresia",
            localizacao="Raposa/MA",
            coordenada=VILA_MARESIA,
            abertura=time(6, 0),
            fechamento=time(18, 0),
        )
    )
    dona_rosa = repo.salvar_empresa(
        EmpresaMarisqueira(
            nome="Marisqueira Dona Rosa",  # RN03: atuação individual
            cnpj="22.222.222/0001-22",
            email="donarosa@vilamaresia.com.br",
            telefone="(98) 98800-1002",
            endereco="Travessa do Porto, 7, Vila Maresia",
            localizacao="Raposa/MA",
            coordenada=RAPOSA,
            abertura=time(5, 30),
            fechamento=time(17, 0),
        )
    )
    aracagi = repo.salvar_empresa(
        EmpresaMarisqueira(
            nome="Marisqueiras do Araçagi",
            cnpj="33.333.333/0001-33",
            email="aracagi@marisqueiras.com.br",
            telefone="(98) 98800-1003",
            endereco="Av. Litorânea, 520",
            localizacao="São Luís/MA",
            coordenada=ARACAGI,
            abertura=time(7, 0),
            fechamento=time(19, 0),
        )
    )

    # Empresas compradoras (RN01, P6)
    mare_alta = repo.salvar_empresa(
        EmpresaCompradora(
            nome="Restaurante Maré Alta",
            cnpj="44.444.444/0001-44",
            email="compras@marealta.com.br",
            telefone="(98) 98800-2001",
            endereco="Rua do Giz, 120, Centro",
            localizacao="São Luís/MA",
            coordenada=SAO_LUIS_CENTRO,
        )
    )
    peixaria = repo.salvar_empresa(
        EmpresaCompradora(
            nome="Peixaria Central Distribuidora",
            cnpj="55.555.555/0001-55",
            email="suprimentos@peixariacentral.com.br",
            telefone="(98) 98800-2002",
            endereco="Mercado do Peixe, Box 14",
            localizacao="Raposa/MA",
            coordenada=MERCADO_DO_PEIXE,
        )
    )

    # Condições de entrega: quem entrega é que define prazo de preparo e
    # até onde vai. Dona Rosa trabalha sozinha (RN03), então leva mais tempo
    # pra preparar e não sai da ilha; o Araçagi é entreposto e entrega longe.
    maresia.configurar_entrega(prazo_preparo_horas=12, raio_entrega_km=40)
    dona_rosa.configurar_entrega(prazo_preparo_horas=36, raio_entrega_km=30)
    aracagi.configurar_entrega(prazo_preparo_horas=8)
    for empresa in (maresia, dona_rosa, aracagi):
        repo.salvar_empresa(empresa)

    # Endereços de entrega cadastrados, pra compra não pedir endereço digitado.
    giz = mare_alta.adicionar_endereco(
        Endereco(
            apelido="Restaurante",
            logradouro="Rua do Giz",
            numero="120",
            bairro="Centro",
            cidade="São Luís",
            cep="65010-680",
            referencia="Esquina com a Rua da Estrela",
            coordenada=SAO_LUIS_CENTRO,
            principal=True,
        )
    )
    litoranea = mare_alta.adicionar_endereco(
        Endereco(
            apelido="Filial Litorânea",
            logradouro="Av. Litorânea",
            numero="1200",
            bairro="São Marcos",
            cidade="São Luís",
            cep="65077-010",
            complemento="Quiosque 4",
            coordenada=Coordenada(-2.488864, -44.293273),
        )
    )
    repo.salvar_enderecos(mare_alta)

    peixaria.adicionar_endereco(
        Endereco(
            apelido="Box do Mercado",
            logradouro="Mercado do Peixe",
            numero="14",
            bairro="Centro",
            cidade="Raposa",
            cep="65138-000",
            complemento="Box 14",
            coordenada=MERCADO_DO_PEIXE,
            principal=True,
        )
    )
    repo.salvar_enderecos(peixaria)

    # Produtos (RN04, RN05, RN06)
    # RN06: sururu fresco e congelado são dois produtos distintos.
    produtos = [
        maresia.cadastrar_produto(
            "Sururu", Categoria.FRESCO, Decimal("18.50"), Decimal("320")
        ),
        maresia.cadastrar_produto(
            "Sururu", Categoria.CONGELADO, Decimal("16.00"), Decimal("500")
        ),
        maresia.cadastrar_produto(
            "Ostra", Categoria.FRESCO, Decimal("34.00"), Decimal("180")
        ),
        maresia.cadastrar_produto(
            "Camarão", Categoria.CONGELADO, Decimal("48.00"), Decimal("240")
        ),
        dona_rosa.cadastrar_produto(
            "Sururu", Categoria.FRESCO, Decimal("17.00"), Decimal("150")
        ),
        dona_rosa.cadastrar_produto(
            "Caranguejo", Categoria.FRESCO, Decimal("29.00"), Decimal("90")
        ),
        # RN09: estoque zerado: continua cadastrado, aparece como indisponível.
        dona_rosa.cadastrar_produto(
            "Ostra", Categoria.CONGELADO, Decimal("31.00"), Decimal("25")
        ),
        aracagi.cadastrar_produto(
            "Sururu", Categoria.FRESCO, Decimal("21.00"), Decimal("400")
        ),
        aracagi.cadastrar_produto(
            "Camarão", Categoria.FRESCO, Decimal("55.00"), Decimal("120")
        ),
        aracagi.cadastrar_produto(
            "Peixe Pescada", Categoria.CONGELADO, Decimal("26.00"), Decimal("300")
        ),
    ]
    for produto in produtos:
        repo.salvar_produto(produto)

    # Fichas de origem dos lotes. Extensão além de P2.
    hoje = date.today()
    fichas = [
        (
            produtos[0],
            "SUR-2410-A",
            0,
            "Baixio da Raposa",
            "Dona Marlene",
            MetodoColeta.CATACAO_MANUAL,
        ),
        (
            produtos[1],
            "SUR-2410-B",
            2,
            "Baixio da Raposa",
            "Dona Marlene",
            MetodoColeta.CATACAO_MANUAL,
        ),
        (
            produtos[2],
            "OST-2410-A",
            1,
            "Croa do Boqueirão",
            "Seu Raimundo",
            MetodoColeta.MERGULHO,
        ),
        (
            produtos[3],
            "CAM-2410-A",
            3,
            "Canal da Raposa",
            "Dona Marlene",
            MetodoColeta.REDE,
        ),
        (
            produtos[4],
            "SUR-2410-C",
            0,
            "Manguezal do Porto",
            "Dona Rosa",
            MetodoColeta.CATACAO_MANUAL,
        ),
        (
            produtos[5],
            "CAR-2410-A",
            1,
            "Manguezal do Porto",
            "Dona Rosa",
            MetodoColeta.ARMADILHA,
        ),
        (
            produtos[7],
            "SUR-2410-D",
            2,
            "Praia do Araçagi",
            "Seu Benedito",
            MetodoColeta.CATACAO_MANUAL,
        ),
        (
            produtos[8],
            "CAM-2410-B",
            1,
            "Praia do Araçagi",
            "Seu Benedito",
            MetodoColeta.REDE,
        ),
    ]
    for produto, lote, dias, local, responsavel, metodo in fichas:
        produto.empresa.registrar_rastreabilidade(
            produto=produto,
            lote=lote,
            data_coleta=hoje - timedelta(days=dias),
            local_coleta=local,
            responsavel=responsavel,
            metodo=metodo,
        )
        repo.salvar_produto(produto)

    # Dona Rosa só trabalha com PIX e dinheiro na entrega.
    dona_rosa.formas_pagamento_aceitas = {
        FormaPagamento.PIX,
        FormaPagamento.TRANSFERENCIA,
    }
    repo.salvar_empresa(dona_rosa)  # regrava as formas aceitas

    # RN09: um produto com estoque zerado, para a busca mostrar o caso.
    ostra_congelada = produtos[6]
    dona_rosa.alterar_quantidade(ostra_congelada, Decimal("0"))
    repo.salvar_produto(ostra_congelada)

    # Histórico de pedidos (P7)
    # Pedido entregue e avaliado, para a média de estrelas existir (RN11).
    entregue = mare_alta.realizar_pedido(
        [(produtos[0], Decimal("60")), (produtos[2], Decimal("40"))],
        giz,
    )
    maresia.aceitar_pedido(entregue)
    mare_alta.informar_pagamento(entregue)
    maresia.confirmar_pagamento(entregue)  # PIX é antecipado: paga antes de sair
    maresia.atualizar_status_entrega(entregue, StatusEntrega.SAIU_PARA_ENTREGA)
    mare_alta.confirmar_entrega(entregue)  # quem recebe é quem confirma
    repo.salvar_pedido(entregue)
    repo.salvar_avaliacao(
        mare_alta.avaliar_empresa(
            entregue, 5, "Sururu muito fresco e entrega no prazo."
        )
    )

    entregue_rosa = mare_alta.realizar_pedido(
        [(produtos[4], Decimal("50"))],
        giz,
    )
    dona_rosa.aceitar_pedido(entregue_rosa)
    mare_alta.informar_pagamento(entregue_rosa)
    dona_rosa.confirmar_pagamento(entregue_rosa)
    dona_rosa.atualizar_status_entrega(entregue_rosa, StatusEntrega.SAIU_PARA_ENTREGA)
    mare_alta.confirmar_entrega(entregue_rosa)
    repo.salvar_pedido(entregue_rosa)
    repo.salvar_avaliacao(
        mare_alta.avaliar_empresa(
            entregue_rosa, 4, "Bom produto, entrega um dia depois."
        )
    )

    # Pedido aguardando análise, para a marisqueira ter o que decidir ao abrir.
    pendente = mare_alta.realizar_pedido(
        [(produtos[3], Decimal("80"))],
        giz,
    )
    repo.salvar_pedido(pendente)

    # Pedido com ajuste solicitado: a compradora precisa responder (P7).
    em_ajuste = mare_alta.realizar_pedido(
        [(produtos[8], Decimal("100"))],
        litoranea,
    )
    aracagi.solicitar_ajuste(
        em_ajuste,
        "Consigo atender 60 kg nesta data. Pode ajustar a quantidade?",
    )
    repo.salvar_pedido(em_ajuste)

    # Pedido despachado: a compradora precisa confirmar o recebimento (RN22).
    em_rota = mare_alta.realizar_pedido(
        [(produtos[9], Decimal("90"))],
        giz,
        forma_pagamento=FormaPagamento.BOLETO_PRAZO,  # sai antes de pagar
    )
    aracagi.aceitar_pedido(em_rota)
    aracagi.atualizar_status_entrega(em_rota, StatusEntrega.SAIU_PARA_ENTREGA)
    # Só a saída fica semeada. O resto do trajeto quem desenha é a simulação,
    # que anda pela rota de ruas de verdade: ponto inventado no meio do
    # caminho cairia fora da rua.
    origem = em_rota.coordenada_origem
    if origem is not None:
        aracagi.registrar_posicao(em_rota, origem, "Saída do entreposto")
    repo.salvar_pedido(em_rota)
