"""Testes das extensões ao que a atividade pede.

P27 pagamento, P2 origem, P10 rastreio e distância ficam aqui porque os
requisitos marcam esses pontos como fora de escopo. Junto deles vêm as
extensões que corrigem RN13: endereço de entrega como cadastro em vez de
campo de texto, prazo decidido por quem vende em vez de por quem compra, e
rota por ruas em vez de linha reta. Os outros arquivos cobrem o exigido.
"""

from dataclasses import FrozenInstanceError
from datetime import date, time, timedelta
from decimal import Decimal

import pytest

from dominio.coordenada import ARACAGI, RAPOSA, SAO_LUIS_CENTRO, Coordenada
from dominio.empresa import EmpresaCompradora, EmpresaMarisqueira
from dominio.endereco import Endereco
from dominio.enums import (
    Categoria,
    FormaPagamento,
    MetodoColeta,
    OrdenacaoBusca,
    StatusEntrega,
    StatusPagamento,
    StatusPedido,
    TipoNotificacao,
)
from dominio.excecoes import (
    AcessoNaoAutorizado,
    DadoObrigatorio,
    ForaDeAreaDeEntrega,
    TransicaoInvalida,
)
from dominio.rastreabilidade import Rastreabilidade
from dominio.rota import Rota


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
        [(sururu, Decimal("30"))], "Rua X, 1", FormaPagamento.BOLETO_PRAZO
    )
    assert pedido.forma_pagamento is FormaPagamento.BOLETO_PRAZO
    assert pedido.status_pagamento is StatusPagamento.PENDENTE
    assert pedido.pago_em is None


def test_marisqueira_pode_recusar_forma_de_pagamento(compradora, maresia, sururu):
    maresia.formas_pagamento_aceitas = {FormaPagamento.PIX}
    with pytest.raises(DadoObrigatorio) as erro:
        compradora.realizar_pedido(
            [(sururu, Decimal("30"))], "Rua X, 1", FormaPagamento.BOLETO
        )
    assert "não aceita" in str(erro.value)


def test_forma_antecipada_trava_o_despacho(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido(
        [(sururu, Decimal("30"))], "Rua X, 1", FormaPagamento.PIX
    )
    maresia.aceitar_pedido(pedido)
    assert pedido.pagamento_pendente
    with pytest.raises(TransicaoInvalida) as erro:
        maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    assert "pagamento" in str(erro.value).lower()


def test_boleto_a_prazo_sai_sem_pagar(compradora, maresia, sururu):
    """A exceção da regra: a prazo a mercadoria sai antes do dinheiro entrar."""
    pedido = compradora.realizar_pedido(
        [(sururu, Decimal("30"))], "Rua X, 1", FormaPagamento.BOLETO_PRAZO
    )
    maresia.aceitar_pedido(pedido)
    assert not pedido.pagamento_pendente
    maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    assert pedido.em_transito
    assert pedido.status_pagamento is StatusPagamento.PENDENTE


def test_fluxo_de_pagamento_em_duas_pontas(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    maresia.aceitar_pedido(pedido)

    compradora.informar_pagamento(pedido)
    assert pedido.status_pagamento is StatusPagamento.INFORMADO
    assert pedido.pagamento_pendente  # informado não é confirmado

    maresia.confirmar_pagamento(pedido)
    assert pedido.status_pagamento is StatusPagamento.CONFIRMADO
    assert pedido.pago_em is not None
    assert not pedido.pagamento_pendente


def test_nao_confirma_pagamento_duas_vezes(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    maresia.aceitar_pedido(pedido)
    maresia.confirmar_pagamento(pedido)
    with pytest.raises(TransicaoInvalida):
        maresia.confirmar_pagamento(pedido)


def test_pedido_cancelado_nao_recebe_pagamento(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
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
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")

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
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    fichas = compradora.consultar_origem(pedido)
    assert len(fichas) == 1
    assert fichas[0].lote == "SUR-003"


def test_produto_sem_ficha_nao_quebra_o_pedido(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    assert pedido.itens[0].origem is None
    assert compradora.consultar_origem(pedido) == []


# Rastreamento em tempo real (P10)


def test_trajeto_so_depois_do_despacho(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    maresia.aceitar_pedido(pedido)
    with pytest.raises(TransicaoInvalida):
        maresia.registrar_posicao(pedido, RAPOSA, "Saiu")


def test_posicoes_formam_o_trajeto(compradora, maresia, sururu):
    pedido = _pago_e_despachado(
        compradora,
        maresia,
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1"),
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
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1"),
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
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    assert pedido.posicao_atual == pedido.coordenada_origem
    assert pedido.distancia_restante_km == pedido.distancia_total_km


def test_entregue_vale_como_estando_no_destino(compradora, maresia, sururu):
    pedido = _pago_e_despachado(
        compradora,
        maresia,
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1"),
    )
    compradora.confirmar_entrega(pedido)
    assert pedido.status is StatusPedido.ENTREGUE
    assert pedido.posicao_atual == pedido.coordenada_entrega
    assert pedido.progresso_percentual == 100


def test_destino_do_pedido_vem_da_compradora(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    assert pedido.coordenada_entrega == compradora.coordenada
    assert pedido.distancia_total_km == maresia.coordenada.distancia_km(
        compradora.coordenada
    )


def test_evento_exige_descricao(compradora, maresia, sururu):
    pedido = _pago_e_despachado(
        compradora,
        maresia,
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1"),
    )
    with pytest.raises(DadoObrigatorio):
        maresia.registrar_posicao(pedido, RAPOSA, "   ")


# Endereços salvos da compradora (extensão sobre RN13)


def _endereco(apelido="Restaurante", **extra) -> Endereco:
    dados = {
        "logradouro": "Rua do Giz",
        "numero": "120",
        "bairro": "Centro",
        "cidade": "São Luís",
        "cep": "65010-680",
        "coordenada": SAO_LUIS_CENTRO,
    }
    dados.update(extra)
    return Endereco(apelido=apelido, **dados)


def test_endereco_exige_os_campos_que_identificam_o_lugar():
    with pytest.raises(DadoObrigatorio):
        _endereco(logradouro="   ")
    with pytest.raises(DadoObrigatorio):
        _endereco(numero="")


def test_endereco_sem_numero_vira_marca_e_nao_vazio():
    """Imóvel sem número existe; o campo continua obrigatório, só muda o valor."""
    for escrito in ("s/n", "SN", "sem número", "S/N"):
        endereco = _endereco(numero=escrito)
        assert endereco.numero == "S/N"
        assert endereco.sem_numero
    assert not _endereco(numero="120").sem_numero


def test_consulta_de_geocodificacao_ignora_o_sem_numero():
    """Mandar "S/N" como número de porta só atrapalha a busca do Nominatim."""
    consulta = _endereco(numero="S/N").consulta_geocodificacao
    assert "S/N" not in consulta
    assert consulta.startswith("Rua do Giz, Centro")
    assert "120" in _endereco(numero="120").consulta_geocodificacao


def test_endereco_valida_uf_e_cep():
    with pytest.raises(DadoObrigatorio):
        _endereco(uf="XX")
    with pytest.raises(DadoObrigatorio):
        _endereco(cep="1234")
    # CEP sem hífen é aceito e normalizado: ninguém digita do mesmo jeito.
    assert _endereco(cep="65010680").cep == "65010-680"


def test_primeiro_endereco_vira_principal_sozinho(compradora):
    """Cadastro com um endereço e nenhum marcado deixaria a compra sem destino."""
    salvo = compradora.adicionar_endereco(_endereco())
    assert salvo.principal
    assert compradora.endereco_principal is salvo


def test_apelido_repetido_e_recusado(compradora):
    compradora.adicionar_endereco(_endereco("Matriz"))
    with pytest.raises(DadoObrigatorio):
        compradora.adicionar_endereco(_endereco("matriz"))


def test_so_um_endereco_principal_por_vez(compradora):
    primeiro = compradora.adicionar_endereco(_endereco("Matriz"))
    segundo = compradora.adicionar_endereco(
        _endereco("Filial", logradouro="Av. Litorânea", numero="1200")
    )
    assert compradora.endereco_principal is primeiro

    compradora.definir_endereco_principal(segundo)
    assert compradora.endereco_principal is segundo
    assert not primeiro.principal


def test_nao_remove_o_unico_endereco(compradora):
    unico = compradora.adicionar_endereco(_endereco())
    with pytest.raises(DadoObrigatorio):
        compradora.remover_endereco(unico)


def test_remover_o_principal_promove_outro(compradora):
    principal = compradora.adicionar_endereco(_endereco("Matriz"))
    outro = compradora.adicionar_endereco(_endereco("Filial", numero="300"))
    compradora.remover_endereco(principal)
    assert compradora.endereco_principal is outro


def test_endereco_de_outra_empresa_nao_se_mexe(compradora, maresia):
    alheio = _endereco()
    with pytest.raises(AcessoNaoAutorizado):
        compradora.definir_endereco_principal(alheio)


def test_compra_sem_escolher_endereco_usa_o_principal(compradora, maresia, sururu):
    compradora.adicionar_endereco(_endereco("Matriz"))
    escolhido = compradora.adicionar_endereco(
        _endereco("Depósito", numero="45", principal=True)
    )
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))])
    assert pedido.endereco_entrega == escolhido.linha


def test_pedido_congela_o_endereco_escolhido(compradora, maresia, sururu):
    """Mesma ideia de RN07 com o preço: editar o cadastro não reescreve o pedido."""
    endereco = compradora.adicionar_endereco(_endereco("Restaurante"))
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], endereco)

    assert pedido.endereco is not endereco  # é cópia, não o mesmo objeto
    assert pedido.endereco.numero == "120"

    endereco.numero = "999"
    assert pedido.endereco.numero == "120"
    assert "120" in pedido.endereco_entrega


def test_endereco_salvo_leva_a_coordenada_para_o_pedido(compradora, maresia, sururu):
    endereco = compradora.adicionar_endereco(
        _endereco("Filial", coordenada=Coordenada(-2.4888, -44.2932))
    )
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], endereco)
    assert pedido.coordenada_entrega == endereco.coordenada


# Raio de entrega da marisqueira (extensão sobre RN13)


def test_sem_raio_a_marisqueira_entrega_em_qualquer_lugar(maresia):
    assert maresia.raio_entrega_km is None
    assert maresia.atende(SAO_LUIS_CENTRO)


def test_raio_recusa_endereco_fora_do_alcance(compradora, maresia, sururu):
    maresia.configurar_entrega(raio_entrega_km=5)  # Raposa → São Luís tem ~26 km
    endereco = compradora.adicionar_endereco(_endereco())
    with pytest.raises(ForaDeAreaDeEntrega):
        compradora.realizar_pedido([(sururu, Decimal("30"))], endereco)


def test_raio_aceita_endereco_dentro_do_alcance(compradora, maresia, sururu):
    maresia.configurar_entrega(raio_entrega_km=40)
    endereco = compradora.adicionar_endereco(_endereco())
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], endereco)
    assert pedido.status is StatusPedido.AGUARDANDO_ANALISE


def test_configurar_entrega_recusa_valores_sem_sentido(maresia):
    with pytest.raises(DadoObrigatorio):
        maresia.configurar_entrega(prazo_preparo_horas=0)
    with pytest.raises(DadoObrigatorio):
        maresia.configurar_entrega(raio_entrega_km=0)


def test_limpar_raio_volta_a_entregar_em_qualquer_lugar(maresia):
    maresia.configurar_entrega(raio_entrega_km=10)
    maresia.configurar_entrega(limpar_raio=True)
    assert maresia.raio_entrega_km is None


# Prazo decidido por quem vende (extensão sobre RN13)


def test_prazo_e_estimativa_ate_a_marisqueira_aceitar(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    assert not pedido.prazo_confirmado
    assert pedido.previsao_entrega is None
    assert pedido.tempo_entrega_dias >= 1


def test_preparo_da_marisqueira_muda_o_prazo_estimado(compradora, maresia, sururu):
    """O prazo sai da agenda de quem vende, não do desejo de quem compra."""
    maresia.configurar_entrega(prazo_preparo_horas=2)
    rapido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")

    maresia.configurar_entrega(prazo_preparo_horas=72)
    demorado = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")

    assert rapido.tempo_entrega_dias < demorado.tempo_entrega_dias


def test_aceite_fecha_o_prazo(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    maresia.aceitar_pedido(pedido)
    assert pedido.prazo_confirmado
    assert pedido.previsao_entrega is not None
    assert "confirmado" in pedido.resumo_prazo


def test_marisqueira_pode_dar_prazo_diferente_da_estimativa(
    compradora, maresia, sururu
):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    maresia.aceitar_pedido(pedido, prazo_dias=7)
    assert pedido.tempo_entrega_dias == 7
    assert (pedido.previsao_entrega - pedido.criado_em).days == 7


def test_compradora_e_avisada_do_prazo_fechado(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    maresia.aceitar_pedido(pedido, prazo_dias=4)
    aviso = compradora.notificacoes[-1]
    assert aviso.tipo is TipoNotificacao.PEDIDO_ACEITO
    assert "4 dia(s)" in aviso.mensagem


def test_prazo_zero_ou_negativo_nao_passa(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    with pytest.raises(DadoObrigatorio):
        maresia.aceitar_pedido(pedido, prazo_dias=0)


# Rota por ruas (extensão sobre P10)


def _rota_com_esquina() -> Rota:
    """Rota que faz esquina: a reta entre as pontas não é o caminho."""
    return Rota(
        pontos=(
            Coordenada(-2.5300, -44.3000),
            Coordenada(-2.5300, -44.2900),
            Coordenada(-2.5200, -44.2900),
        ),
        distancia_km=Decimal("2.2"),
        duracao_minutos=6,
    )


def test_rota_exige_dois_pontos():
    with pytest.raises(DadoObrigatorio):
        Rota(
            pontos=(SAO_LUIS_CENTRO,),
            distancia_km=Decimal("1"),
            duracao_minutos=1,
        )


def test_rota_em_linha_reta_se_identifica_como_tal():
    rota = Rota.em_linha_reta(RAPOSA, SAO_LUIS_CENTRO)
    assert not rota.por_ruas
    assert rota.fonte == "reta"
    assert len(rota) == 2


def test_ponto_no_meio_segue_a_esquina_em_vez_de_cortar():
    rota = _rota_com_esquina()
    meio = rota.ponto_em(0.5)
    reto = rota.origem.interpolar(rota.destino, 0.5)
    # Se cortasse reto, o ponto do meio cairia fora da rua.
    assert meio.distancia_km(reto) > Decimal("0.2")


def test_extremos_da_rota_sao_origem_e_destino():
    rota = _rota_com_esquina()
    assert rota.ponto_em(0) == rota.origem
    assert rota.ponto_em(1) == rota.destino
    # Fração fora da faixa não estoura: é presa nos extremos.
    assert rota.ponto_em(-3) == rota.origem
    assert rota.ponto_em(9) == rota.destino


def test_trecho_andado_cresce_e_termina_no_destino():
    rota = _rota_com_esquina()
    assert len(rota.trecho_ate(0.5)) < len(rota.trecho_ate(0.9))
    assert rota.trecho_ate(1.0)[-1] == rota.destino


def test_fracao_de_reconhece_onde_a_posicao_caiu():
    """É o que permite retomar a animação de onde o último ponto parou."""
    rota = _rota_com_esquina()
    for alvo in (0.25, 0.5, 0.75):
        assert abs(rota.fracao_de(rota.ponto_em(alvo)) - alvo) < 0.05


def test_amostrar_devolve_pontos_sobre_o_tracado():
    rota = _rota_com_esquina()
    amostra = rota.amostrar(5)
    assert len(amostra) == 5
    assert amostra[0] == rota.origem
    assert amostra[-1] == rota.destino
    with pytest.raises(DadoObrigatorio):
        rota.amostrar(1)


def test_rota_por_ruas_manda_na_distancia_do_pedido(compradora, maresia, sururu):
    """Com rota, o km do pedido é o rodado, não a linha reta."""
    reta = RAPOSA.distancia_km(SAO_LUIS_CENTRO)
    rota = Rota(
        pontos=(RAPOSA, Coordenada(-2.48, -44.20), SAO_LUIS_CENTRO),
        distancia_km=reta + Decimal("9"),
        duracao_minutos=55,
    )
    pedido = compradora.realizar_pedido(
        [(sururu, Decimal("30"))], "Rua X, 1", rota=rota
    )
    assert pedido.distancia_total_km > reta
    assert pedido.minutos_de_transito == 55


def test_sem_rota_o_pedido_cai_na_linha_reta(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1")
    assert pedido.rota is None
    assert pedido.distancia_total_km == RAPOSA.distancia_km(SAO_LUIS_CENTRO)


def test_progresso_sobre_rota_usa_o_tracado(compradora, maresia, sururu):
    rota = _rota_com_esquina()
    pedido = compradora.realizar_pedido(
        [(sururu, Decimal("30"))], "Rua X, 1", rota=rota
    )
    _pago_e_despachado(compradora, maresia, pedido)
    maresia.registrar_posicao(pedido, rota.ponto_em(0.5), "Meio do caminho")
    assert 40 <= pedido.progresso_percentual <= 60
