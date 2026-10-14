"""Testes das regras de negócio do domínio Marisqueiras da Ilha.

Cada teste cita a regra que verifica. Rodam sem banco e sem interface,
o que comprova que `dominio/` não depende de `repositorio/` nem de `ui/`.
"""

from datetime import time
from decimal import Decimal

import pytest

from dominio.avaliacao import Avaliacao
from dominio.empresa import EmpresaCompradora, EmpresaMarisqueira
from dominio.enums import (
    Categoria,
    OrdenacaoBusca,
    SituacaoEmpresa,
    StatusEntrega,
    StatusPedido,
    TipoNotificacao,
)
from dominio.excecoes import (
    AcessoNaoAutorizado,
    AvaliacaoInvalida,
    DadoObrigatorio,
    EmpresasDiferentesNoPedido,
    PrecoAlteradoEmVenda,
    QuantidadeIndisponivel,
    QuantidadeInvalida,
    TransicaoInvalida,
)

# Fixtures


@pytest.fixture
def maresia():
    return EmpresaMarisqueira(
        nome="Marisqueiras Vila Maresia",
        cnpj="11.111.111/0001-11",
        email="maresia@exemplo.com",
        telefone="(98) 90000-0001",
        endereco="Rua da Praia, 10",
        localizacao="Raposa/MA",
        abertura=time(0, 0),
        fechamento=time(23, 59),
    )


@pytest.fixture
def outra_marisqueira():
    return EmpresaMarisqueira(
        nome="Marisqueiras do Araçagi",
        cnpj="22.222.222/0001-22",
        email="aracagi@exemplo.com",
        telefone="(98) 90000-0002",
        endereco="Av. Litorânea, 50",
        localizacao="São Luís/MA",
        abertura=time(0, 0),
        fechamento=time(23, 59),
    )


@pytest.fixture
def compradora():
    return EmpresaCompradora(
        nome="Restaurante Maré Alta",
        cnpj="33.333.333/0001-33",
        email="compras@marealta.com",
        telefone="(98) 90000-0003",
        endereco="Rua do Comércio, 200",
        localizacao="São Luís/MA",
    )


@pytest.fixture
def sururu(maresia):
    return maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18.50"), Decimal("200")
    )


# RN04, RN05, RN06: cadastro de produto


def test_rn05_cadastro_abaixo_do_minimo_e_recusado(maresia):
    with pytest.raises(QuantidadeInvalida):
        maresia.cadastrar_produto(
            "Sururu", Categoria.FRESCO, Decimal("18.50"), Decimal("10")
        )


def test_rn06_fresco_e_congelado_sao_produtos_diferentes(maresia):
    a = maresia.cadastrar_produto(
        "Camarão", Categoria.FRESCO, Decimal("40"), Decimal("50")
    )
    b = maresia.cadastrar_produto(
        "Camarão", Categoria.CONGELADO, Decimal("35"), Decimal("50")
    )
    assert a is not b
    assert len(maresia.produtos) == 2


def test_rn06_mesmo_nome_e_mesma_categoria_e_duplicidade(maresia):
    maresia.cadastrar_produto("Ostra", Categoria.FRESCO, Decimal("30"), Decimal("50"))
    with pytest.raises(DadoObrigatorio):
        maresia.cadastrar_produto(
            "ostra", Categoria.FRESCO, Decimal("31"), Decimal("60")
        )


def test_p15_foto_e_o_unico_campo_opcional(maresia):
    p = maresia.cadastrar_produto(
        "Caranguejo", Categoria.FRESCO, Decimal("25"), Decimal("40")
    )
    assert p.foto is None
    with pytest.raises(DadoObrigatorio):
        maresia.cadastrar_produto("", Categoria.FRESCO, Decimal("25"), Decimal("40"))


# RN08, RN09: estoque


def test_rn09_estoque_zerado_mantem_produto_cadastrado(maresia, sururu):
    maresia.alterar_quantidade(sururu, Decimal("0"))
    assert sururu in maresia.produtos
    assert sururu.esta_disponivel is False


def test_rn08_quantidade_negativa_e_recusada(maresia, sururu):
    with pytest.raises(QuantidadeInvalida):
        maresia.alterar_quantidade(sururu, Decimal("-1"))


def test_estoque_pode_ficar_abaixo_do_minimo_apos_venda(maresia, sururu):
    maresia.alterar_quantidade(sururu, Decimal("20"))
    assert sururu.quantidade_disponivel_kg == Decimal("20")
    assert sururu.esta_disponivel is False
    assert sururu.situacao is SituacaoEmpresa.ESTOQUE_BAIXO


def test_rn12_empresa_nao_altera_produto_de_outra(outra_marisqueira, sururu):
    with pytest.raises(AcessoNaoAutorizado):
        outra_marisqueira.alterar_quantidade(sururu, Decimal("50"))


# RN15, RN18: itens e disponibilidade


def test_rn15_minimo_de_25kg_por_produto(compradora, sururu):
    with pytest.raises(QuantidadeInvalida):
        compradora.realizar_pedido([(sururu, Decimal("20"))], "Rua X, 1", 3)


def test_rn15_nao_se_burla_somando_dois_itens_do_mesmo_produto(compradora, sururu):
    with pytest.raises(QuantidadeInvalida):
        compradora.realizar_pedido(
            [(sururu, Decimal("15")), (sururu, Decimal("15"))], "Rua X, 1", 3
        )


def test_rn18_pedido_acima_do_estoque_e_impedido(compradora, maresia, sururu):
    maresia.alterar_quantidade(sururu, Decimal("30"))
    with pytest.raises(QuantidadeIndisponivel) as erro:
        compradora.realizar_pedido([(sururu, Decimal("100"))], "Rua X, 1", 3)
    assert "30" in str(erro.value)  # RN18: informa o estoque real


def test_rn17_nao_existe_quantidade_maxima_fixa(compradora, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("200"))], "Rua X, 1", 3)
    assert pedido.quantidade_total_kg == Decimal("200")


# RN14: um pedido, uma empresa


def test_rn14_pedido_nao_reune_empresas_diferentes(
    compradora, maresia, outra_marisqueira
):
    a = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    b = outra_marisqueira.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    with pytest.raises(EmpresasDiferentesNoPedido):
        compradora.realizar_pedido(
            [(a, Decimal("30")), (b, Decimal("30"))], "Rua X, 1", 3
        )


def test_rn28_pedido_aceita_varios_produtos_da_mesma_empresa(compradora, maresia):
    a = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    b = maresia.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    pedido = compradora.realizar_pedido(
        [(a, Decimal("30")), (b, Decimal("25"))], "Rua X, 1", 3
    )
    assert len(pedido.itens) == 2
    assert pedido.total == Decimal("30") * Decimal("18") + Decimal("25") * Decimal("30")


# RN07: preço congelado durante a venda


def test_rn07_item_guarda_copia_do_preco(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    maresia.aceitar_pedido(pedido)
    maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    compradora.confirmar_entrega(pedido)
    maresia.alterar_preco_produto(sururu, Decimal("99.00"))
    assert pedido.itens[0].preco_unitario == Decimal("18.50")
    assert pedido.total == Decimal("555.00")


def test_rn07_preco_travado_com_venda_em_andamento(compradora, maresia, sururu):
    compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    with pytest.raises(PrecoAlteradoEmVenda):
        maresia.alterar_preco_produto(sururu, Decimal("25.00"))


# P7: fluxo do pedido


def test_p7_fluxo_completo_ate_entrega(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    assert pedido.status is StatusPedido.AGUARDANDO_ANALISE

    maresia.aceitar_pedido(pedido)
    assert pedido.status is StatusPedido.ACEITO
    assert sururu.quantidade_disponivel_kg == Decimal("150")  # RN18: estoque baixado

    maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    compradora.confirmar_entrega(pedido)
    assert pedido.status is StatusPedido.ENTREGUE


def test_p7_rejeicao_exige_motivo(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    with pytest.raises(DadoObrigatorio):
        maresia.rejeitar_pedido(pedido, "   ")
    maresia.rejeitar_pedido(pedido, "Sem capacidade de entrega nesta semana.")
    assert pedido.status is StatusPedido.REJEITADO


def test_p7_pedido_rejeitado_nao_pode_ser_aceito(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    maresia.rejeitar_pedido(pedido, "Fora de temporada.")
    with pytest.raises(TransicaoInvalida):
        maresia.aceitar_pedido(pedido)


def test_p7_solicitar_ajuste(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    maresia.solicitar_ajuste(pedido, "Consigo entregar 25 kg nesta data.")
    assert pedido.status is StatusPedido.AJUSTE_SOLICITADO
    assert pedido.observacao_ajuste


def test_rn22_entrega_nao_atualiza_antes_do_aceite(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    with pytest.raises(TransicaoInvalida):
        maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)


def test_rn12_marisqueira_nao_aceita_pedido_de_outra(
    compradora, maresia, outra_marisqueira, sururu
):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    with pytest.raises(AcessoNaoAutorizado):
        outra_marisqueira.aceitar_pedido(pedido)


def test_rn13_dados_obrigatorios_do_pedido(compradora, sururu):
    with pytest.raises(DadoObrigatorio):
        compradora.realizar_pedido([(sururu, Decimal("30"))], "", 3)
    with pytest.raises(DadoObrigatorio):
        compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 0)


# RN10, RN11, RN12: busca, ordenação e visibilidade


def test_rn12_marisqueira_ve_somente_os_proprios_produtos(maresia, outra_marisqueira):
    meu = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    dela = outra_marisqueira.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    catalogo = [meu, dela]
    assert maresia.consultar_produtos(catalogo) == [meu]
    assert outra_marisqueira.consultar_produtos(catalogo) == [dela]


def test_rn12_compradora_ve_de_todas_as_empresas(
    compradora, maresia, outra_marisqueira
):
    meu = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    dela = outra_marisqueira.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    assert len(compradora.consultar_produtos([meu, dela])) == 2


def test_rn10_filtros_de_p21(compradora, maresia, outra_marisqueira):
    a = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    b = maresia.cadastrar_produto(
        "Sururu", Categoria.CONGELADO, Decimal("16"), Decimal("100")
    )
    c = outra_marisqueira.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    catalogo = [a, b, c]

    assert compradora.consultar_produtos(catalogo, nome="suru") == [a, b]
    assert compradora.consultar_produtos(catalogo, categoria=Categoria.CONGELADO) == [b]
    assert compradora.consultar_produtos(catalogo, localizacao="Raposa") == [a, b]
    assert compradora.consultar_produtos(catalogo, empresa=outra_marisqueira) == [c]


def test_rn11_ordenacoes_de_p22(compradora, maresia):
    a = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    b = maresia.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    catalogo = [a, b]
    assert compradora.consultar_produtos(
        catalogo, ordenar_por=OrdenacaoBusca.MENOR_PRECO
    ) == [a, b]
    assert compradora.consultar_produtos(
        catalogo, ordenar_por=OrdenacaoBusca.MAIOR_PRECO
    ) == [b, a]


def test_rn09_produto_sem_estoque_continua_na_busca(compradora, maresia, sururu):
    maresia.alterar_quantidade(sururu, Decimal("0"))
    resultado = compradora.consultar_produtos([sururu])
    assert resultado == [sururu]
    assert resultado[0].esta_disponivel is False


def test_p26_comparar_produtos_de_empresas_diferentes(
    compradora, maresia, outra_marisqueira
):
    a = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("100")
    )
    b = outra_marisqueira.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    comparacao = compradora.comparar_produtos([a, b])
    assert len(comparacao) == 2
    assert comparacao[0]["melhor_preco"] is True
    assert comparacao[1]["melhor_preco"] is False


def test_p26_comparacao_exige_dois_produtos(compradora, sururu):
    with pytest.raises(DadoObrigatorio):
        compradora.comparar_produtos([sururu])


# RN21, P24: avaliação


def _pedido_entregue(compradora, maresia, produto):
    pedido = compradora.realizar_pedido([(produto, Decimal("30"))], "Rua X, 1", 3)
    maresia.aceitar_pedido(pedido)
    maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    compradora.confirmar_entrega(pedido)
    return pedido


def test_rn21_avaliacao_somente_apos_a_entrega(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    with pytest.raises(AvaliacaoInvalida):
        compradora.avaliar_empresa(pedido, 5)


def test_rn21_avaliacao_valida(compradora, maresia, sururu):
    pedido = _pedido_entregue(compradora, maresia, sururu)
    av = compradora.avaliar_empresa(pedido, 5, "Produto excelente.")
    assert av.nota == 5
    assert maresia.media_avaliacoes == Decimal("5.0")


@pytest.mark.parametrize("nota", [0, 6, -1, 100])
def test_p24_escala_de_1_a_5(compradora, maresia, sururu, nota):
    pedido = _pedido_entregue(compradora, maresia, sururu)
    with pytest.raises(AvaliacaoInvalida):
        compradora.avaliar_empresa(pedido, nota)


def test_uma_avaliacao_por_pedido(compradora, maresia, sururu):
    pedido = _pedido_entregue(compradora, maresia, sururu)
    compradora.avaliar_empresa(pedido, 4)
    with pytest.raises(AvaliacaoInvalida):
        compradora.avaliar_empresa(pedido, 5)


def test_media_de_avaliacoes(compradora, maresia):
    a = maresia.cadastrar_produto(
        "Sururu", Categoria.FRESCO, Decimal("18"), Decimal("500")
    )
    for nota in (5, 4, 3):
        compradora.avaliar_empresa(_pedido_entregue(compradora, maresia, a), nota)
    assert maresia.media_avaliacoes == Decimal("4.0")


def test_registrar_nota_valida_a_escala(compradora, maresia, sururu):
    pedido = _pedido_entregue(compradora, maresia, sururu)
    av = Avaliacao(pedido, 3)
    av.registrar_nota(5)
    assert av.nota == 5
    assert av.estrelas == "★★★★★"
    with pytest.raises(AvaliacaoInvalida):
        av.registrar_nota(9)


# RN19, RN20: situação da empresa


def test_rn19_empresa_permanece_cadastrada_sem_estoque(maresia, sururu):
    maresia.alterar_quantidade(sururu, Decimal("0"))
    assert maresia.situacao is SituacaoEmpresa.ESTOQUE_BAIXO


def test_rn20_fora_do_horario(sururu):
    fechada = EmpresaMarisqueira(
        nome="Fechada",
        cnpj="44.444.444/0001-44",
        email="f@f.com",
        telefone="(98) 90000-0004",
        endereco="Rua Y, 2",
        localizacao="Raposa/MA",
        abertura=time(0, 0),
        fechamento=time(0, 1),
    )
    assert fechada.situacao is SituacaoEmpresa.FORA_DE_HORARIO


def test_rn20_empresa_com_estoque_esta_disponivel(maresia, sururu):
    assert maresia.situacao is SituacaoEmpresa.DISPONIVEL


# RN01 / herança e polimorfismo


def test_empresa_e_abstrata():
    from dominio.empresa import Empresa

    with pytest.raises(TypeError):
        Empresa("X", "1", "a@a.com", "9", "rua", "local")


def test_polimorfismo_de_tipo_e_consulta(maresia, compradora, sururu):
    for empresa in (maresia, compradora):
        assert isinstance(empresa.tipo(), str)
        assert isinstance(empresa.consultar_produtos([sururu]), list)


# P7: resposta da compradora ao pedido de ajuste


def test_compradora_responde_ao_ajuste_e_reenvia(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("100"))], "Rua X, 1", 3)
    maresia.solicitar_ajuste(pedido, "Consigo 60 kg nesta data.")
    assert pedido.aguarda_resposta_da_compradora

    compradora.responder_ajuste(pedido, [(sururu, Decimal("60"))])

    assert pedido.status is StatusPedido.AGUARDANDO_ANALISE
    assert pedido.quantidade_total_kg == Decimal("60")
    assert pedido.observacao_ajuste is None
    maresia.aceitar_pedido(pedido)  # agora a marisqueira consegue seguir
    assert pedido.status is StatusPedido.ACEITO


def test_ajuste_revalida_rn15(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("100"))], "Rua X, 1", 3)
    maresia.solicitar_ajuste(pedido, "Consigo pouco.")
    with pytest.raises(QuantidadeInvalida):
        compradora.responder_ajuste(pedido, [(sururu, Decimal("10"))])
    # O pedido original fica intacto quando o ajuste é inválido.
    assert pedido.quantidade_total_kg == Decimal("100")
    assert pedido.status is StatusPedido.AJUSTE_SOLICITADO


def test_ajuste_revalida_rn18(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    maresia.solicitar_ajuste(pedido, "Confirme a quantidade.")
    with pytest.raises(QuantidadeIndisponivel):
        compradora.responder_ajuste(pedido, [(sururu, Decimal("5000"))])
    assert pedido.quantidade_total_kg == Decimal("50")


def test_ajuste_revalida_rn14(compradora, maresia, outra_marisqueira, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    maresia.solicitar_ajuste(pedido, "Confirme.")
    outro = outra_marisqueira.cadastrar_produto(
        "Ostra", Categoria.FRESCO, Decimal("30"), Decimal("100")
    )
    with pytest.raises(EmpresasDiferentesNoPedido):
        compradora.responder_ajuste(pedido, [(outro, Decimal("30"))])


def test_compradora_cancela_quando_o_ajuste_nao_serve(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("100"))], "Rua X, 1", 3)
    maresia.solicitar_ajuste(pedido, "Consigo só 10 kg.")
    compradora.cancelar_pedido(pedido)
    assert pedido.status is StatusPedido.CANCELADO
    with pytest.raises(TransicaoInvalida):
        maresia.aceitar_pedido(pedido)


def test_marisqueira_nao_aceita_sozinha_apos_pedir_ajuste(compradora, maresia, sururu):
    """A bola fica com a compradora: ajuste solicitado não vai direto a aceito."""
    pedido = compradora.realizar_pedido([(sururu, Decimal("100"))], "Rua X, 1", 3)
    maresia.solicitar_ajuste(pedido, "Reduza a quantidade.")
    with pytest.raises(TransicaoInvalida):
        maresia.aceitar_pedido(pedido)


def test_ajuste_so_vale_em_pedido_com_ajuste_solicitado(compradora, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    with pytest.raises(TransicaoInvalida):
        compradora.responder_ajuste(pedido, [(sururu, Decimal("40"))])


def test_compradora_nao_mexe_em_pedido_de_outra(compradora, maresia, sururu):
    outra = EmpresaCompradora(
        nome="Outra Compradora",
        cnpj="99.999.999/0001-99",
        email="outra@exemplo.com",
        telefone="(98) 90000-0009",
        endereco="Rua Z, 9",
        localizacao="São Luís/MA",
    )
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    with pytest.raises(AcessoNaoAutorizado):
        outra.cancelar_pedido(pedido)


# RN22: a marisqueira despacha, a compradora confirma


def test_marisqueira_nao_marca_como_entregue(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    maresia.aceitar_pedido(pedido)
    maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    with pytest.raises(TransicaoInvalida) as erro:
        maresia.atualizar_status_entrega(pedido, StatusEntrega.ENTREGUE)
    assert "compradora" in str(erro.value)
    assert pedido.status is not StatusPedido.ENTREGUE


def test_compradora_confirma_o_recebimento(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    maresia.aceitar_pedido(pedido)
    maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    assert pedido.pode_confirmar_recebimento

    compradora.confirmar_entrega(pedido)

    assert pedido.status is StatusPedido.ENTREGUE
    assert pedido.status_entrega is StatusEntrega.ENTREGUE
    assert pedido.pode_ser_avaliado  # RN21 liberada por quem recebeu


def test_nao_confirma_recebimento_antes_do_despacho(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    maresia.aceitar_pedido(pedido)
    assert not pedido.pode_confirmar_recebimento
    with pytest.raises(TransicaoInvalida):
        compradora.confirmar_entrega(pedido)


# Notificações: cada transição avisa a contraparte


def test_pedido_novo_notifica_a_marisqueira(compradora, maresia, sururu):
    assert maresia.total_nao_lidas == 0
    compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    assert maresia.total_nao_lidas == 1
    assert maresia.notificacoes[-1].tipo is TipoNotificacao.PEDIDO_RECEBIDO


def test_despacho_notifica_a_compradora(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    compradora.marcar_notificacoes_como_lidas()
    maresia.aceitar_pedido(pedido)
    maresia.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)

    tipos = [n.tipo for n in compradora.notificacoes_nao_lidas]
    assert TipoNotificacao.PEDIDO_ACEITO in tipos
    assert TipoNotificacao.SAIU_PARA_ENTREGA in tipos


def test_ajuste_e_reenvio_notificam_as_duas_pontas(compradora, maresia, sururu):
    pedido = compradora.realizar_pedido([(sururu, Decimal("100"))], "Rua X, 1", 3)
    maresia.solicitar_ajuste(pedido, "Reduza para 60 kg.")
    assert any(
        n.tipo is TipoNotificacao.AJUSTE_SOLICITADO
        for n in compradora.notificacoes_nao_lidas
    )

    maresia.marcar_notificacoes_como_lidas()
    compradora.responder_ajuste(pedido, [(sururu, Decimal("60"))])
    assert any(
        n.tipo is TipoNotificacao.PEDIDO_REENVIADO
        for n in maresia.notificacoes_nao_lidas
    )


def test_rejeicao_e_cancelamento_notificam(compradora, maresia, sururu):
    rejeitado = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    maresia.rejeitar_pedido(rejeitado, "Fora de temporada.")
    assert any(
        n.tipo is TipoNotificacao.PEDIDO_REJEITADO
        for n in compradora.notificacoes_nao_lidas
    )

    cancelado = compradora.realizar_pedido([(sururu, Decimal("30"))], "Rua X, 1", 3)
    maresia.marcar_notificacoes_como_lidas()
    compradora.cancelar_pedido(cancelado)
    assert any(
        n.tipo is TipoNotificacao.PEDIDO_CANCELADO
        for n in maresia.notificacoes_nao_lidas
    )


def test_confirmacao_e_avaliacao_notificam_a_marisqueira(compradora, maresia, sururu):
    pedido = _pedido_entregue(compradora, maresia, sururu)
    maresia.marcar_notificacoes_como_lidas()
    compradora.avaliar_empresa(pedido, 5, "Ótimo.")
    tipos = [n.tipo for n in maresia.notificacoes_nao_lidas]
    assert TipoNotificacao.AVALIACAO_RECEBIDA in tipos


def test_marcar_como_lidas_zera_a_caixa(compradora, maresia, sururu):
    compradora.realizar_pedido([(sururu, Decimal("50"))], "Rua X, 1", 3)
    assert maresia.total_nao_lidas == 1
    alteradas = maresia.marcar_notificacoes_como_lidas()
    assert len(alteradas) == 1
    assert maresia.total_nao_lidas == 0
    assert len(maresia.notificacoes) == 1  # continuam no histórico
