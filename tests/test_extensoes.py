"""Testes das extensões: P27 pagamento, P2 origem, P10 rastreio e distância.

Ficam em arquivo separado porque os requisitos marcam estes quatro pontos
como fora de escopo. Os outros arquivos cobrem o que a atividade exige.
"""

from dataclasses import FrozenInstanceError
from datetime import date, time, timedelta
from decimal import Decimal

import pytest

from dominio.coordenada import ARACAGI, RAPOSA, SAO_LUIS_CENTRO, Coordenada
from dominio.empresa import EmpresaCompradora, EmpresaMarisqueira
from dominio.enums import (
    Categoria,
    FormaPagamento,
    MetodoColeta,
    OrdenacaoBusca,
    StatusEntrega,
    StatusPagamento,
    StatusPedido,
)
from dominio.excecoes import DadoObrigatorio, TransicaoInvalida
from dominio.rastreabilidade import Rastreabilidade


@pytest.fixture
def maresia():
    return EmpresaMarisqueira(
        nome="Marisqueiras Vila Maresia",
        cnpj="11.111.111/0001-11",
        email="m@exemplo.com",
        telefone="(98) 90000-0001",
        endereco="Rua da Praia, 10",
        localizacao="Raposa/MA",
        coordenada=RAPOSA,
        abertura=time(0, 0),
        fechamento=time(23, 59),
    )


@pytest.fixture
def aracagi():
    return EmpresaMarisqueira(
        nome="Marisqueiras do Araçagi",
        cnpj="22.222.222/0001-22",
        email="a@exemplo.com",
        telefone="(98) 90000-0002",
        endereco="Av. Litorânea, 520",
        localizacao="São Luís/MA",
        coordenada=ARACAGI,
        abertura=time(0, 0),
        fechamento=time(23, 59),
    )


@pytest.fixture
def compradora():
    return EmpresaCompradora(
        nome="Restaurante Maré Alta",
        cnpj="33.333.333/0001-33",
        email="c@exemplo.com",
        telefone="(98) 90000-0003",
        endereco="Rua do Giz, 120",
        localizacao="São Luís/MA",
        coordenada=SAO_LUIS_CENTRO,
    )


@pytest.fixture
def sururu(maresia):
    return maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18.50"), Decimal("300")
    )


def _pago_e_despachado(compradora, marisqueira, pedido):
    marisqueira.aceitar_pedido(pedido)
    compradora.informar_pagamento(pedido)
    marisqueira.confirmar_pagamento(pedido)
    marisqueira.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    return pedido


# Geolocalização real (P10)


def test_distancia_geodesica_entre_pontos_reais():
    """Raposa a São Luís tem ~26 km em linha reta. Confere a ordem de grandeza."""
    assert Decimal("25") < RAPOSA.distancia_km(SAO_LUIS_CENTRO) < Decimal("27")
    assert RAPOSA.distancia_km(RAPOSA) == Decimal("0")
    assert RAPOSA.distancia_km(None) is None


def test_coordenada_recusa_valor_fora_da_faixa():
    with pytest.raises(DadoObrigatorio):
        Coordenada(91, 0)
    with pytest.raises(DadoObrigatorio):
        Coordenada(0, 181)


def test_coordenada_e_imutavel():
    """`frozen=True` levanta FrozenInstanceError em qualquer atribuição."""
    ponto = Coordenada(-2.5, -44.3)
    with pytest.raises(FrozenInstanceError):
        ponto.latitude = 0


def test_interpolar_anda_o_caminho():
    meio = RAPOSA.interpolar(SAO_LUIS_CENTRO, 0.5)
    total = RAPOSA.distancia_km(SAO_LUIS_CENTRO)
    assert abs(meio.distancia_km(SAO_LUIS_CENTRO) - total / 2) < Decimal("0.5")
    # Fração fora de 0..1 é presa nos extremos.
    assert RAPOSA.interpolar(SAO_LUIS_CENTRO, -5) == RAPOSA
    assert RAPOSA.interpolar(SAO_LUIS_CENTRO, 9) == SAO_LUIS_CENTRO


def test_ordenacao_por_proximidade_usa_distancia_real(compradora, maresia, aracagi):
    """Araçagi fica mais perto do centro de São Luís que a Raposa."""
    longe = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    perto = aracagi.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    ordem = compradora.consultar_produtos(
        [longe, perto], ordenar_por=OrdenacaoBusca.PROXIMIDADE
    )
    assert ordem == [perto, longe]
    assert compradora.distancia_ate_produto(perto) < compradora.distancia_ate_produto(
        longe
    )


def test_filtro_de_raio(compradora, maresia, aracagi):
    longe = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    perto = aracagi.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    assert compradora.consultar_produtos([longe, perto], raio_km=20) == [perto]
    assert len(compradora.consultar_produtos([longe, perto], raio_km=50)) == 2


def test_produto_sem_coordenada_vai_para_o_fim(compradora, maresia):
    sem_coordenada = EmpresaMarisqueira(
        nome="Sem GPS",
        cnpj="44.444.444/0001-44",
        email="s@exemplo.com",
        telefone="(98) 90000-0004",
        endereco="Rua Y, 2",
        localizacao="Raposa/MA",
    )
    com = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    sem = sem_coordenada.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    assert compradora.distancia_ate_produto(sem) is None
    ordem = compradora.consultar_produtos(
        [sem, com], ordenar_por=OrdenacaoBusca.PROXIMIDADE
    )
    assert ordem == [com, sem]


# Forma de pagamento (P27)


def test_pedido_guarda_a_forma_escolhida(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido(
        [(sururu, Decimal("30"))], "Rua X, 1", 3, FormaPagamento.BOLETO_PRAZO
    )
    assert pedido.forma_pagamento is FormaPagamento.BOLETO_PRAZO
    assert pedido.status_pagamento is StatusPagamento.PENDENTE
    assert pedido.pago_em is None


def test_marisqueira_pode_recusar_forma_de_pagamento(compradora, maresia, sururu):
    maresia.formas_pagamento_aceitas = {FormaPagamento.PIX}
    with pytest.raises(DadoObrigatorio) as erro:
        compradora.realizar_pedido(
            [(sururu, Decimal("30"))], "Rua X, 1", 3, FormaPagamento.BOLETO
        )
    assert "não aceita" in str(erro.value)


def test_forma_antecipada_trava_o_despacho(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido(
        [(sururu, Decimal("30"))], "Rua X, 1", 3, FormaPagamento.PIX
    )
    maresia.aceitar_pedido(pedido)
    assert pedido.pagamento_pendente
    with pytest.raises(TransicaoInvalida) as erro:
        maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    assert "pagamento" in str(erro.value).lower()


def test_boleto_a_prazo_sai_sem_pagar(compradora, maresia, sururu):
    """A exceção da regra: a prazo a mercadoria sai antes do dinheiro entrar."""
    pedido = compradora.realizar_pedido(
        [(sururu, Decimal("30"))], "Rua X, 1", 3, FormaPagamento.BOLETO_PRAZO
    )
    maresia.aceitar_pedido(pedido)
    assert not pedido.pagamento_pendente
    maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    assert pedido.em_transito
    assert pedido.status_pagamento is StatusPagamento.PENDENTE


def test_fluxo_de_pagamento_em_duas_pontas(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    maresia.aceitar_pedido(pedido)

    compradora.informar_pagamento(pedido)
    assert pedido.status_pagamento is StatusPagamento.INFORMADO
    assert pedido.pagamento_pendente  # informado não é confirmado

    maresia.confirmar_pagamento(pedido)
    assert pedido.status_pagamento is StatusPagamento.CONFIRMADO
    assert pedido.pago_em is not None
    assert not pedido.pagamento_pendente


def test_nao_confirma_pagamento_duas_vezes(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    maresia.aceitar_pedido(pedido)
    maresia.confirmar_pagamento(pedido)
    with pytest.raises(TransicaoInvalida):
        maresia.confirmar_pagamento(pedido)


def test_pedido_cancelado_nao_recebe_pagamento(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    compradora.cancelar_pedido(pedido)
    with pytest.raises(TransicaoInvalida):
        compradora.informar_pagamento(pedido)


# Rastreabilidade e origem (P2)


def test_ficha_de_origem_no_produto(maresia, sururu):
    assert not sururu.tem_origem
    ficha = maresia.registrar_rastreabilidade(
        produto=sururu,
        lote="SUR-001",
        data_coleta=date.today() - timedelta(days=2),
        local_coleta="Baixio da Raposa",
        responsavel="Dona Marlene",
        metodo=MetodoColeta.CATACAO_MANUAL,
    )
    assert sururu.tem_origem
    assert ficha.lote == "SUR-001"
    assert ficha.idade_em_dias == 2
    assert ficha.dentro_da_validade_sugerida
    assert ficha.coordenada == maresia.coordenada  # herda a da empresa


def test_ficha_recusa_data_no_futuro(maresia, sururu):
    with pytest.raises(DadoObrigatorio):
        maresia.registrar_rastreabilidade(
            produto=sururu,
            lote="SUR-002",
            data_coleta=date.today() + timedelta(days=1),
            local_coleta="Baixio",
            responsavel="Alguém",
        )


def test_lote_velho_sai_da_validade_sugerida():
    ficha = Rastreabilidade(
        lote="antigo",
        data_coleta=date.today() - timedelta(days=12),
        local_coleta="Baixio",
        responsavel="Alguém",
    )
    assert ficha.idade_em_dias == 12
    assert not ficha.dentro_da_validade_sugerida


def test_item_congela_a_origem_da_compra(compradora, maresia, sururu):
    """Mesma ideia de RN07 com o preço: o lote vendido não muda depois."""
    maresia.registrar_rastreabilidade(
        produto=sururu,
        lote="LOTE-ANTIGO",
        data_coleta=date.today(),
        local_coleta="Baixio da Raposa",
        responsavel="Dona Marlene",
    )
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)

    # Lote novo no produto não reescreve o pedido já feito.
    maresia.registrar_rastreabilidade(
        produto=sururu,
        lote="LOTE-NOVO",
        data_coleta=date.today(),
        local_coleta="Croa do Boqueirão",
        responsavel="Seu Raimundo",
    )
    assert sururu.rastreabilidade.lote == "LOTE-NOVO"
    assert pedido.itens[0].origem.lote == "LOTE-ANTIGO"
    assert pedido.itens[0].origem.local_coleta == "Baixio da Raposa"


def test_compradora_consulta_a_origem_do_pedido(compradora, maresia, sururu):
    maresia.registrar_rastreabilidade(
        produto=sururu,
        lote="SUR-003",
        data_coleta=date.today(),
        local_coleta="Baixio da Raposa",
        responsavel="Dona Marlene",
    )
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    fichas = compradora.consultar_origem(pedido)
    assert len(fichas) == 1
    assert fichas[0].lote == "SUR-003"


def test_produto_sem_ficha_nao_quebra_o_pedido(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    assert pedido.itens[0].origem is None
    assert compradora.consultar_origem(pedido) == []


# Rastreamento em tempo real (P10)


def test_trajeto_so_depois_do_despacho(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    maresia.aceitar_pedido(pedido)
    with pytest.raises(TransicaoInvalida):
        maresia.registrar_posicao(pedido, RAPOSA, "Saiu")


def test_posicoes_formam_o_trajeto(compradora, maresia, sururu):
    pedido = _pago_e_despachado(
        compradora,
        maresia,
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3),
    )
    origem, destino = pedido.coordenada_origem, pedido.coordenada_entrega
    assert pedido.progresso_percentual == 0

    for fracao in (0.25, 0.5, 0.75, 1.0):
        maresia.registrar_posicao(
            pedido, origem.interpolar(destino, fracao), f"{int(fracao * 100)}%"
        )

    assert len(pedido.eventos_entrega) == 4
    assert pedido.progresso_percentual == 100
    assert pedido.distancia_restante_km == Decimal("0.0")


def test_progresso_acompanha_a_distancia(compradora, maresia, sururu):
    pedido = _pago_e_despachado(
        compradora,
        maresia,
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3),
    )
    total = pedido.distancia_total_km
    maresia.registrar_posicao(
        pedido,
        pedido.coordenada_origem.interpolar(pedido.coordenada_entrega, 0.5),
        "Metade",
    )
    assert 45 <= pedido.progresso_percentual <= 55
    assert abs(pedido.distancia_restante_km - total / 2) < Decimal("0.6")


def test_posicao_atual_cai_na_origem_sem_trajeto(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    assert pedido.posicao_atual == pedido.coordenada_origem
    assert pedido.distancia_restante_km == pedido.distancia_total_km


def test_entregue_vale_como_estando_no_destino(compradora, maresia, sururu):
    pedido = _pago_e_despachado(
        compradora,
        maresia,
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3),
    )
    compradora.confirmar_entrega(pedido)
    assert pedido.status is StatusPedido.ENTREGUE
    assert pedido.posicao_atual == pedido.coordenada_entrega
    assert pedido.progresso_percentual == 100


def test_destino_do_pedido_vem_da_compradora(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    assert pedido.coordenada_entrega == compradora.coordenada
    assert pedido.distancia_total_km == maresia.coordenada.distancia_km(
        compradora.coordenada
    )


def test_evento_exige_descricao(compradora, maresia, sururu):
    pedido = _pago_e_despachado(
        compradora,
        maresia,
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3),
    )
    with pytest.raises(DadoObrigatorio):
        maresia.registrar_posicao(pedido, RAPOSA, "   ")
