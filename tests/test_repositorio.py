"""Testes da camada de persistência: o grafo de objetos sobrevive ao banco."""

from decimal import Decimal

import pytest

from dominio.endereco import Endereco
from dominio.enums import Categoria, StatusEntrega, StatusPedido
from repositorio.repositorio import Repositorio
from repositorio.seed import popular


@pytest.fixture
def repo(tmp_path):
    banco = Repositorio(tmp_path / "teste.db")
    popular(banco)
    yield banco
    banco.fechar()


def test_seed_grava_e_recarrega(repo, tmp_path):
    repo.fechar()
    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    assert len(recarregado.marisqueiras) == 3
    assert len(recarregado.compradoras) == 2
    assert len(recarregado.catalogo) == 10
    recarregado.fechar()


def test_decimal_nao_perde_precisao(repo, tmp_path):
    repo.fechar()
    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    precos = {str(p.preco_por_kg) for p in recarregado.catalogo}
    assert "18.50" in precos  # TEXT preserva a escala; REAL daria 18.5
    recarregado.fechar()


def test_rn07_preco_historico_do_item_sobrevive_ao_banco(repo, tmp_path):
    maresia = next(e for e in repo.marisqueiras if "Maresia" in e.nome)
    sururu = next(
        p
        for p in maresia.produtos
        if p.nome == "Sururu" and p.categoria is Categoria.FRESCO
    )
    pedido = next(p for p in repo.pedidos.values() if p.status is StatusPedido.ENTREGUE)
    preco_original = pedido.itens[0].preco_unitario

    maresia.alterar_preco_produto(sururu, Decimal("99.00"))
    repo.salvar_produto(sururu)
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    pedido_salvo = recarregado.pedidos[pedido.id]
    assert pedido_salvo.itens[0].preco_unitario == preco_original
    assert pedido_salvo.itens[0].produto.preco_por_kg == Decimal("99.00")
    recarregado.fechar()


def test_rn09_produto_com_estoque_zero_recarrega(repo, tmp_path):
    repo.fechar()
    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    zerados = [p for p in recarregado.catalogo if p.quantidade_disponivel_kg == 0]
    assert len(zerados) == 1
    assert zerados[0].esta_disponivel is False
    recarregado.fechar()


def test_identidade_unica_por_linha(repo):
    """RN12/RN14 dependem de comparação por `is`: um objeto por linha do banco."""
    for marisqueira in repo.marisqueiras:
        for produto in marisqueira.produtos:
            assert produto is repo.produtos[produto.id]
            assert produto.empresa is marisqueira


def test_fluxo_completo_persistido(repo, tmp_path):
    compradora = repo.compradoras[0]
    marisqueira = next(e for e in repo.marisqueiras if "Araçagi" in e.nome)
    produto = marisqueira.produtos[0]
    estoque_antes = produto.quantidade_disponivel_kg

    pedido = compradora.realizar_pedido([(produto, Decimal("30"))], "Rua Teste, 1")
    repo.salvar_pedido(pedido)
    marisqueira.aceitar_pedido(pedido)
    pedido.compradora.informar_pagamento(pedido)
    marisqueira.confirmar_pagamento(pedido)
    marisqueira.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    compradora.confirmar_entrega(pedido)
    repo.salvar_pedido(pedido)
    avaliacao = compradora.avaliar_empresa(pedido, 5, "Ótimo.")
    repo.salvar_avaliacao(avaliacao)
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    salvo = recarregado.pedidos[pedido.id]
    assert salvo.status is StatusPedido.ENTREGUE
    assert salvo.itens[0].produto.quantidade_disponivel_kg == estoque_antes - Decimal(
        "30"
    )
    assert any(a.pedido.id == pedido.id for a in recarregado.avaliacoes.values())
    recarregado.fechar()


def test_avaliacao_alimenta_a_media(repo, tmp_path):
    repo.fechar()
    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    maresia = next(e for e in recarregado.marisqueiras if "Maresia" in e.nome)
    assert maresia.media_avaliacoes == Decimal("5.0")
    recarregado.fechar()


def test_notificacoes_sobrevivem_ao_banco(repo, tmp_path):
    compradora = next(e for e in repo.compradoras if "Maré" in e.nome)
    nao_lidas_antes = compradora.total_nao_lidas
    assert nao_lidas_antes > 0  # o seed gera avisos de aceite e despacho
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    salva = next(e for e in recarregado.compradoras if "Maré" in e.nome)
    assert salva.total_nao_lidas == nao_lidas_antes
    assert all(n.pedido is not None for n in salva.notificacoes)
    recarregado.fechar()


def test_marcar_como_lidas_persiste(repo, tmp_path):
    compradora = next(e for e in repo.compradoras if "Maré" in e.nome)
    quantas = repo.marcar_notificacoes_como_lidas(compradora)
    assert quantas > 0
    assert compradora.total_nao_lidas == 0
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    salva = next(e for e in recarregado.compradoras if "Maré" in e.nome)
    assert salva.total_nao_lidas == 0
    recarregado.fechar()


def test_ajuste_e_confirmacao_persistem(repo, tmp_path):
    compradora = next(e for e in repo.compradoras if "Maré" in e.nome)
    em_ajuste = next(
        p for p in compradora.pedidos if p.status is StatusPedido.AJUSTE_SOLICITADO
    )
    produto = em_ajuste.itens[0].produto
    marisqueira = em_ajuste.marisqueira

    compradora.responder_ajuste(em_ajuste, [(produto, Decimal("60"))])
    repo.salvar_pedido(em_ajuste)
    marisqueira.aceitar_pedido(em_ajuste)
    em_ajuste.compradora.informar_pagamento(em_ajuste)
    marisqueira.confirmar_pagamento(em_ajuste)
    marisqueira.atualizar_status_entrega(em_ajuste, StatusEntrega.SAIU_PARA_ENTREGA)
    compradora.confirmar_entrega(em_ajuste)
    repo.salvar_pedido(em_ajuste)
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    salvo = recarregado.pedidos[em_ajuste.id]
    assert salvo.status is StatusPedido.ENTREGUE
    assert salvo.quantidade_total_kg == Decimal("60")
    assert salvo.pode_ser_avaliado
    recarregado.fechar()


# Extensões sobre RN13: endereços salvos, condições de entrega e prazo


def test_enderecos_salvos_recarregam_com_apelido_e_coordenada(repo, tmp_path):
    repo.fechar()
    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    mare = next(e for e in recarregado.compradoras if "Maré" in e.nome)

    apelidos = {e.apelido for e in mare.enderecos}
    assert apelidos == {"Restaurante", "Filial Litorânea"}
    principal = mare.endereco_principal
    assert principal.apelido == "Restaurante"
    assert principal.coordenada is not None
    # Os campos opcionais também voltam, não só os obrigatórios.
    filial = next(e for e in mare.enderecos if e.apelido == "Filial Litorânea")
    assert filial.complemento == "Quiosque 4"
    assert principal.referencia is not None
    recarregado.fechar()


def test_endereco_novo_e_removido_persistem(repo, tmp_path):
    mare = next(e for e in repo.compradoras if "Maré" in e.nome)
    antigo = next(e for e in mare.enderecos if e.apelido == "Filial Litorânea")
    mare.adicionar_endereco(
        Endereco(
            apelido="Depósito",
            logradouro="Rua da Palma",
            numero="7",
            bairro="Centro",
            cidade="São Luís",
        )
    )
    mare.remover_endereco(antigo)
    repo.salvar_enderecos(mare)
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    salva = next(e for e in recarregado.compradoras if "Maré" in e.nome)
    apelidos = {e.apelido for e in salva.enderecos}
    assert apelidos == {"Restaurante", "Depósito"}
    recarregado.fechar()


def test_condicoes_de_entrega_da_marisqueira_persistem(repo, tmp_path):
    maresia = next(e for e in repo.marisqueiras if "Maresia" in e.nome)
    maresia.configurar_entrega(prazo_preparo_horas=5, raio_entrega_km=Decimal("12.5"))
    repo.salvar_empresa(maresia)
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    salva = next(e for e in recarregado.marisqueiras if "Maresia" in e.nome)
    assert salva.prazo_preparo_horas == 5
    assert salva.raio_entrega_km == Decimal("12.5")
    recarregado.fechar()


def test_pedido_guarda_a_copia_do_endereco_mesmo_depois_de_editar(repo, tmp_path):
    """Mesma garantia de RN07 com o preço, aplicada ao destino da entrega."""
    mare = next(e for e in repo.compradoras if "Maré" in e.nome)
    pedido = next(p for p in mare.pedidos if p.endereco is not None)
    numero_original = pedido.endereco.numero
    apelido_original = pedido.endereco.apelido
    texto_original = pedido.endereco_entrega

    cadastrado = next(e for e in mare.enderecos if e.apelido == apelido_original)
    cadastrado.numero = "999"
    repo.salvar_enderecos(mare)
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    salvo = recarregado.pedidos[pedido.id]
    assert salvo.endereco.numero == numero_original
    assert salvo.endereco_entrega == texto_original
    # E o cadastro, esse sim, mudou.
    salva = next(e for e in recarregado.compradoras if "Maré" in e.nome)
    assert (
        next(e for e in salva.enderecos if e.apelido == apelido_original).numero
        == "999"
    )
    recarregado.fechar()


def test_prazo_confirmado_e_previsao_persistem(repo, tmp_path):
    aguardando = next(
        p for p in repo.pedidos.values() if p.status is StatusPedido.AGUARDANDO_ANALISE
    )
    assert not aguardando.prazo_confirmado
    aguardando.marisqueira.aceitar_pedido(aguardando, prazo_dias=5)
    repo.salvar_pedido(aguardando)
    repo.fechar()

    recarregado = Repositorio(tmp_path / "teste.db")
    recarregado.carregar()
    salvo = recarregado.pedidos[aguardando.id]
    assert salvo.prazo_confirmado
    assert salvo.tempo_entrega_dias == 5
    assert salvo.previsao_entrega is not None
    assert (salvo.previsao_entrega - salvo.criado_em).days == 5
    recarregado.fechar()
