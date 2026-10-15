"""Testes de integração das telas.

Rodam com a plataforma Qt "offscreen", sem abrir janela.

QMessageBox e QInputDialog são modais e travariam o teste esperando clique,
então a fixture `mensagens` troca por listas, o que de bônus deixa checar a
mensagem que o usuário teria visto.
"""

from decimal import Decimal

import pytest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QInputDialog,
    QMessageBox,
)

from dominio.enums import Categoria, OrdenacaoBusca, StatusEntrega, StatusPedido
from repositorio.repositorio import Repositorio
from repositorio.seed import popular
from ui.janela_principal import JanelaPrincipal
from ui.painel_compradora import PainelCompradora
from ui.painel_marisqueira import PainelMarisqueira


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def mensagens(monkeypatch):
    """Substitui as caixas modais por listas inspecionáveis."""
    capturadas: dict[str, list[str]] = {"aviso": [], "info": []}
    monkeypatch.setattr(
        "ui.componentes.QMessageBox.warning",
        lambda pai, titulo, texto, *a, **k: capturadas["aviso"].append(texto),
    )
    monkeypatch.setattr(
        "ui.componentes.QMessageBox.information",
        lambda pai, titulo, texto, *a, **k: capturadas["info"].append(texto),
    )
    return capturadas


@pytest.fixture
def repo(tmp_path):
    banco = Repositorio(tmp_path / "ui.db")
    popular(banco)
    yield banco
    banco.fechar()


def _quantidade(monkeypatch, valor: float) -> None:
    monkeypatch.setattr(QInputDialog, "getDouble", lambda *a, **k: (valor, True))


# Janela principal


def test_janela_lista_os_dois_tipos_de_empresa(app, repo):
    janela = JanelaPrincipal(repo)
    assert janela.lst_marisqueiras.count() == 3
    assert janela.lst_compradoras.count() == 2


def test_janela_monta_o_painel_certo_por_polimorfismo(app, repo):
    janela = JanelaPrincipal(repo)
    janela.lst_marisqueiras.setCurrentRow(0)
    janela._entrar(janela.lst_marisqueiras, repo.marisqueiras)
    assert isinstance(janela.painel, PainelMarisqueira)

    janela.lst_compradoras.setCurrentRow(0)
    janela._entrar(janela.lst_compradoras, repo.compradoras)
    assert isinstance(janela.painel, PainelCompradora)


# Painel da marisqueira


def test_rn12_painel_mostra_somente_os_proprios_produtos(app, repo):
    for marisqueira in repo.marisqueiras:
        painel = PainelMarisqueira(marisqueira, repo, lambda: None)
        assert painel.tbl_produtos.rowCount() == len(marisqueira.produtos)
        assert painel.tbl_produtos.rowCount() < len(repo.catalogo)


def test_cadastro_pela_tela_persiste(app, repo, tmp_path, mensagens):
    marisqueira = repo.marisqueiras[0]
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)
    antes = painel.tbl_produtos.rowCount()

    painel.in_nome.setText("Polvo")
    painel.in_categoria.setCurrentIndex(0)
    painel.in_preco.setValue(62.00)
    painel.in_quantidade.setValue(40.0)
    painel._cadastrar_produto()
    painel.atualizar()

    assert painel.tbl_produtos.rowCount() == antes + 1
    assert mensagens["info"]

    repo.fechar()
    recarregado = Repositorio(tmp_path / "ui.db")
    recarregado.carregar()
    assert any(p.nome == "Polvo" for p in recarregado.catalogo)
    recarregado.fechar()


def test_rn05_cadastro_invalido_pela_tela_vira_aviso(app, repo, mensagens):
    """O erro de negócio virou aviso, não exceção que fecha o programa."""
    marisqueira = repo.marisqueiras[0]
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)
    antes = painel.tbl_produtos.rowCount()

    painel.in_nome.setText("Lagosta")
    painel.in_quantidade.setValue(10.0)  # abaixo de RN05
    painel._cadastrar_produto()
    painel.atualizar()

    assert painel.tbl_produtos.rowCount() == antes
    assert any("25" in aviso for aviso in mensagens["aviso"])


def test_p7_botoes_seguem_a_maquina_de_estados(app, repo):
    marisqueira = next(e for e in repo.marisqueiras if "Maresia" in e.nome)
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)

    linha = next(
        i
        for i, pedido in enumerate(painel._pedidos_na_tabela)
        if pedido.status is StatusPedido.AGUARDANDO_ANALISE
    )
    painel.tbl_pedidos.selectRow(linha)
    assert painel.btn_aceitar.isEnabled()
    assert painel.btn_rejeitar.isEnabled()
    assert painel.btn_ajuste.isEnabled()
    assert not painel.btn_entrega.isEnabled()  # RN22: só depois do aceite

    linha = next(
        i
        for i, pedido in enumerate(painel._pedidos_na_tabela)
        if pedido.status is StatusPedido.ENTREGUE
    )
    painel.tbl_pedidos.selectRow(linha)
    assert not painel.btn_aceitar.isEnabled()
    assert not painel.btn_rejeitar.isEnabled()


def test_aceitar_pedido_pela_tela_baixa_estoque(app, repo):
    marisqueira = next(e for e in repo.marisqueiras if "Maresia" in e.nome)
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)
    linha = next(
        i
        for i, pedido in enumerate(painel._pedidos_na_tabela)
        if pedido.status is StatusPedido.AGUARDANDO_ANALISE
    )
    painel.tbl_pedidos.selectRow(linha)
    pedido = painel._pedidos_na_tabela[linha]
    produto = pedido.itens[0].produto
    estoque_antes = produto.quantidade_disponivel_kg
    quantidade = pedido.itens[0].quantidade_kg

    painel._aceitar_pedido()

    assert pedido.status is StatusPedido.ACEITO
    assert produto.quantidade_disponivel_kg == estoque_antes - quantidade


def test_alterar_quantidade_pela_tela(app, repo, monkeypatch):
    _quantidade(monkeypatch, 0.0)  # RN09: zerar mantém cadastrado
    marisqueira = repo.marisqueiras[0]
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)
    painel.tbl_produtos.selectRow(0)
    produto = painel._produtos_na_tabela[0]

    painel._alterar_quantidade()
    painel.atualizar()

    assert produto.quantidade_disponivel_kg == Decimal("0")
    assert produto in marisqueira.produtos
    assert "Estoque baixo" in painel.tbl_produtos.item(0, 4).text()


def test_rn07_alterar_preco_bloqueado_com_venda_em_andamento(
    app, repo, monkeypatch, mensagens
):
    _quantidade(monkeypatch, 99.0)
    marisqueira = next(e for e in repo.marisqueiras if "Maresia" in e.nome)
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)
    pendente = next(
        p
        for p in marisqueira.pedidos_recebidos
        if p.status is StatusPedido.AGUARDANDO_ANALISE
    )
    produto = pendente.itens[0].produto
    linha = painel._produtos_na_tabela.index(produto)
    painel.tbl_produtos.selectRow(linha)
    preco_antes = produto.preco_por_kg

    painel._alterar_preco()

    assert produto.preco_por_kg == preco_antes
    assert any("venda em andamento" in aviso for aviso in mensagens["aviso"])


# Painel da compradora


def test_rn12_compradora_ve_catalogo_inteiro(app, repo):
    painel = PainelCompradora(repo.compradoras[0], repo, lambda: None)
    assert painel.tbl_busca.rowCount() == len(repo.catalogo)


def test_p21_filtros_da_tela(app, repo):
    painel = PainelCompradora(repo.compradoras[0], repo, lambda: None)
    total = painel.tbl_busca.rowCount()

    painel.f_nome.setText("sururu")
    assert 0 < painel.tbl_busca.rowCount() < total
    painel.f_nome.clear()

    painel.f_categoria.setCurrentIndex(painel.f_categoria.findData(Categoria.CONGELADO))
    assert all(p.categoria is Categoria.CONGELADO for p in painel._resultados)
    painel.f_categoria.setCurrentIndex(0)

    assert painel.tbl_busca.rowCount() == total


def test_p22_ordenacao_da_tela(app, repo):
    painel = PainelCompradora(repo.compradoras[0], repo, lambda: None)
    painel.f_ordenacao.setCurrentIndex(
        painel.f_ordenacao.findData(OrdenacaoBusca.MENOR_PRECO)
    )
    precos = [p.preco_por_kg for p in painel._resultados]
    assert precos == sorted(precos)

    painel.f_ordenacao.setCurrentIndex(
        painel.f_ordenacao.findData(OrdenacaoBusca.MAIOR_PRECO)
    )
    precos = [p.preco_por_kg for p in painel._resultados]
    assert precos == sorted(precos, reverse=True)


def test_rn09_produto_zerado_aparece_na_busca_como_indisponivel(app, repo):
    painel = PainelCompradora(repo.compradoras[0], repo, lambda: None)
    linha = next(
        i for i, p in enumerate(painel._resultados) if p.quantidade_disponivel_kg == 0
    )
    assert "Estoque baixo" in painel.tbl_busca.item(linha, 8).text()


def test_rn14_carrinho_recusa_segunda_empresa(app, repo, monkeypatch, mensagens):
    _quantidade(monkeypatch, 30.0)
    painel = PainelCompradora(repo.compradoras[0], repo, lambda: None)
    maresia = next(e for e in repo.marisqueiras if "Maresia" in e.nome)
    outra = next(e for e in repo.marisqueiras if "Araçagi" in e.nome)

    linha = next(i for i, p in enumerate(painel._resultados) if p.empresa is maresia)
    painel.tbl_busca.selectRow(linha)
    painel._adicionar_ao_carrinho()
    assert len(painel._carrinho) == 1

    linha = next(i for i, p in enumerate(painel._resultados) if p.empresa is outra)
    painel.tbl_busca.selectRow(linha)
    painel._adicionar_ao_carrinho()

    assert len(painel._carrinho) == 1  # RN14: recusado
    assert any("empresas diferentes" in aviso for aviso in mensagens["aviso"])


def test_rn15_carrinho_recusa_abaixo_do_minimo(app, repo, monkeypatch, mensagens):
    _quantidade(monkeypatch, 10.0)
    painel = PainelCompradora(repo.compradoras[0], repo, lambda: None)
    painel.tbl_busca.selectRow(0)
    painel._adicionar_ao_carrinho()

    assert painel._carrinho == []
    assert any("mínima" in aviso for aviso in mensagens["aviso"])


def test_pedido_completo_pela_interface(app, repo, monkeypatch):
    _quantidade(monkeypatch, 30.0)
    compradora = repo.compradoras[0]
    painel = PainelCompradora(compradora, repo, lambda: None)
    pedidos_antes = len(compradora.pedidos)

    painel.tbl_busca.selectRow(0)
    painel._adicionar_ao_carrinho()
    painel.in_endereco.setText("Rua de Teste, 99")
    painel.in_prazo.setValue(2)
    painel._realizar_pedido()
    painel.atualizar()

    assert len(compradora.pedidos) == pedidos_antes + 1
    assert painel._carrinho == []

    novo = compradora.pedidos[-1]
    assert novo.id is not None
    assert novo.status is StatusPedido.AGUARDANDO_ANALISE

    # A marisqueira vê o pedido no painel dela.
    painel_m = PainelMarisqueira(novo.marisqueira, repo, lambda: None)
    assert any(p.id == novo.id for p in painel_m._pedidos_na_tabela)


def test_rn21_botao_avaliar_so_libera_apos_entrega(app, repo):
    compradora = repo.compradoras[0]
    painel = PainelCompradora(compradora, repo, lambda: None)

    linha = next(
        i
        for i, p in enumerate(painel._pedidos_na_tabela)
        if p.status is StatusPedido.AGUARDANDO_ANALISE
    )
    painel.tbl_meus_pedidos.selectRow(linha)
    assert not painel.btn_avaliar.isEnabled()

    # Pedido entregue E já avaliado pelo seed: continua desabilitado.
    linha = next(
        i
        for i, p in enumerate(painel._pedidos_na_tabela)
        if p.status is StatusPedido.ENTREGUE
    )
    painel.tbl_meus_pedidos.selectRow(linha)
    assert not painel.btn_avaliar.isEnabled()


def test_rn21_avaliacao_liberada_em_pedido_entregue_sem_nota(app, repo):
    compradora = repo.compradoras[1]
    marisqueira = next(e for e in repo.marisqueiras if "Araçagi" in e.nome)
    produto = marisqueira.produtos[0]
    pedido = compradora.realizar_pedido([(produto, Decimal("30"))], "Rua Y, 2", 2)
    marisqueira.aceitar_pedido(pedido)
    pedido.compradora.informar_pagamento(pedido)
    marisqueira.confirmar_pagamento(pedido)
    marisqueira.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    compradora.confirmar_entrega(pedido)
    repo.salvar_pedido(pedido)

    painel = PainelCompradora(compradora, repo, lambda: None)
    linha = next(
        i for i, p in enumerate(painel._pedidos_na_tabela) if p.id == pedido.id
    )
    painel.tbl_meus_pedidos.selectRow(linha)
    assert painel.btn_avaliar.isEnabled()


def test_p26_comparacao_recebe_os_selecionados(app, repo, monkeypatch):
    aberto: list[list[dict]] = []
    monkeypatch.setattr(
        "ui.painel_compradora.DialogoComparacao",
        lambda pai, comparacao: type(
            "DialogoFalso", (), {"exec": lambda self: aberto.append(comparacao)}
        )(),
    )
    painel = PainelCompradora(repo.compradoras[0], repo, lambda: None)
    painel.tbl_busca.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
    painel.tbl_busca.selectRow(0)
    painel.tbl_busca.selectRow(1)

    painel._comparar()

    assert aberto and len(aberto[0]) == 2
    assert sum(1 for linha in aberto[0] if linha["melhor_preco"]) >= 1


def test_p26_comparacao_exige_dois_produtos(app, repo, mensagens):
    painel = PainelCompradora(repo.compradoras[0], repo, lambda: None)
    painel.tbl_busca.selectRow(0)
    painel._comparar()
    assert any("dois produtos" in aviso for aviso in mensagens["aviso"])


# P7: a compradora responde ao ajuste pela tela


def _linha_do_pedido(painel, status):
    return next(
        i for i, p in enumerate(painel._pedidos_na_tabela) if p.status is status
    )


def test_botoes_de_resposta_ao_ajuste(app, repo):
    """Era o bug: com ajuste solicitado, a compradora não tinha ação nenhuma."""
    compradora = next(e for e in repo.compradoras if "Maré" in e.nome)
    painel = PainelCompradora(compradora, repo, lambda: None)
    linha = _linha_do_pedido(painel, StatusPedido.AJUSTE_SOLICITADO)
    painel.tbl_meus_pedidos.selectRow(linha)

    assert painel.btn_ajustar.isEnabled()
    assert painel.btn_cancelar.isEnabled()
    assert not painel.btn_confirmar.isEnabled()
    assert not painel.btn_avaliar.isEnabled()


def test_ajuste_pela_tela_reenvia_o_pedido(app, repo, monkeypatch):
    compradora = next(e for e in repo.compradoras if "Maré" in e.nome)
    painel = PainelCompradora(compradora, repo, lambda: None)
    linha = _linha_do_pedido(painel, StatusPedido.AJUSTE_SOLICITADO)
    painel.tbl_meus_pedidos.selectRow(linha)
    pedido = painel._pedidos_na_tabela[linha]

    # O diálogo é modal: devolve as quantidades sem abrir janela.
    class DialogoFalso:
        def __init__(self, pai, pedido_alvo):
            self.pedido = pedido_alvo

        def exec(self):
            return QDialog.DialogCode.Accepted

        @property
        def itens(self):
            return [(self.pedido.itens[0].produto, Decimal("60"))]

    monkeypatch.setattr("ui.painel_compradora.DialogoAjuste", DialogoFalso)
    painel._ajustar()
    painel.atualizar()

    assert pedido.status is StatusPedido.AGUARDANDO_ANALISE
    assert pedido.quantidade_total_kg == Decimal("60")

    # A marisqueira volta a conseguir decidir.
    painel_m = PainelMarisqueira(pedido.marisqueira, repo, lambda: None)
    linha_m = next(
        i for i, p in enumerate(painel_m._pedidos_na_tabela) if p.id == pedido.id
    )
    painel_m.tbl_pedidos.selectRow(linha_m)
    assert painel_m.btn_aceitar.isEnabled()


def test_cancelamento_pela_tela(app, repo, monkeypatch):
    monkeypatch.setattr(
        "ui.painel_compradora.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    compradora = next(e for e in repo.compradoras if "Maré" in e.nome)
    painel = PainelCompradora(compradora, repo, lambda: None)
    linha = _linha_do_pedido(painel, StatusPedido.AJUSTE_SOLICITADO)
    painel.tbl_meus_pedidos.selectRow(linha)
    pedido = painel._pedidos_na_tabela[linha]

    painel._cancelar()

    assert pedido.status is StatusPedido.CANCELADO


# RN22: a marisqueira despacha, a compradora confirma


def test_marisqueira_nao_oferece_entregue_na_tela(app, repo):
    marisqueira = next(e for e in repo.marisqueiras if "Araçagi" in e.nome)
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)
    rotulos = [s.rotulo for s in painel.STATUS_INFORMAVEIS]
    assert StatusEntrega.ENTREGUE.rotulo not in rotulos
    assert StatusEntrega.SAIU_PARA_ENTREGA.rotulo in rotulos


def test_confirmacao_de_recebimento_pela_tela(app, repo):
    compradora = next(e for e in repo.compradoras if "Maré" in e.nome)
    painel = PainelCompradora(compradora, repo, lambda: None)
    linha = next(
        i
        for i, p in enumerate(painel._pedidos_na_tabela)
        if p.pode_confirmar_recebimento
    )
    painel.tbl_meus_pedidos.selectRow(linha)
    pedido = painel._pedidos_na_tabela[linha]
    assert painel.btn_confirmar.isEnabled()
    assert not painel.btn_avaliar.isEnabled()

    painel._confirmar_entrega()
    painel.atualizar()
    painel.tbl_meus_pedidos.selectRow(
        next(i for i, p in enumerate(painel._pedidos_na_tabela) if p.id == pedido.id)
    )

    assert pedido.status is StatusPedido.ENTREGUE
    assert painel.btn_avaliar.isEnabled()  # RN21 liberada pela confirmação


def test_botao_de_entrega_some_apos_o_despacho(app, repo):
    marisqueira = next(e for e in repo.marisqueiras if "Araçagi" in e.nome)
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)
    linha = next(
        i
        for i, p in enumerate(painel._pedidos_na_tabela)
        if p.status_entrega is StatusEntrega.SAIU_PARA_ENTREGA
    )
    painel.tbl_pedidos.selectRow(linha)
    assert not painel.btn_entrega.isEnabled()


# Notificações na tela


def test_contador_de_avisos_no_titulo_da_aba(app, repo):
    compradora = next(e for e in repo.compradoras if "Maré" in e.nome)
    painel = PainelCompradora(compradora, repo, lambda: None)
    nao_lidas = compradora.total_nao_lidas
    assert nao_lidas > 0
    assert painel.abas.tabText(painel._aba_avisos) == f"Avisos ({nao_lidas})"

    painel.painel_notificacoes._marcar_lidas()
    painel.atualizar()
    assert painel.abas.tabText(painel._aba_avisos) == "Avisos"


def test_aviso_de_despacho_chega_na_compradora(app, repo):
    """Era o segundo bug: o pedido saía para entrega e nada avisava."""
    compradora = repo.compradoras[1]
    marisqueira = next(e for e in repo.marisqueiras if "Maresia" in e.nome)
    produto = marisqueira.produtos[0]
    pedido = compradora.realizar_pedido([(produto, Decimal("30"))], "Rua K, 1", 2)
    repo.salvar_pedido(pedido)
    repo.marcar_notificacoes_como_lidas(compradora)

    marisqueira.aceitar_pedido(pedido)
    pedido.compradora.informar_pagamento(pedido)
    marisqueira.confirmar_pagamento(pedido)
    marisqueira.atualizar_status_entrega(pedido, StatusEntrega.SAIU_PARA_ENTREGA)
    repo.salvar_pedido(pedido)

    painel = PainelCompradora(compradora, repo, lambda: None)
    mensagens = [
        painel.painel_notificacoes.tbl_notificacoes.item(linha, 1).text()
        for linha in range(painel.painel_notificacoes.tbl_notificacoes.rowCount())
    ]
    assert "Pedido saiu para entrega" in mensagens
    assert "Avisos (" in painel.abas.tabText(painel._aba_avisos)


def test_marisqueira_tambem_recebe_avisos(app, repo):
    marisqueira = next(e for e in repo.marisqueiras if "Maresia" in e.nome)
    painel = PainelMarisqueira(marisqueira, repo, lambda: None)
    assert painel.painel_notificacoes.tbl_notificacoes.rowCount() > 0
