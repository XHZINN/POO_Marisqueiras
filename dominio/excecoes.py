"""Erros de regra de negócio.

Tudo aqui herda de `ErroDeNegocio`, então a interface captura uma classe só:

    try:
        marisqueira.aceitar_pedido(pedido)
    except ErroDeNegocio as erro:
        QMessageBox.warning(self, "Não foi possível", str(erro))

TypeError, KeyError e sqlite3.Error não herdam daqui de propósito: são bug,
e bug tem que estourar no terminal. Quem lança escreve a mensagem, porque só
ele sabe o contexto.
"""

from decimal import Decimal


class ErroDeNegocio(Exception):
    """Base de todos os erros previstos pelas regras de negócio."""


class DadoObrigatorio(ErroDeNegocio):
    """P15 / RN13: campo obrigatório ausente ou vazio."""


class QuantidadeInvalida(ErroDeNegocio):
    """RN05 / RN15: quantidade negativa ou abaixo do mínimo de 25 kg."""


class QuantidadeIndisponivel(ErroDeNegocio):
    """RN17 / RN18: quantidade solicitada maior que a disponível em estoque.

    Carrega os números porque RN18 exige INFORMAR a indisponibilidade:
    não basta recusar o pedido, é preciso dizer quanto há disponível.
    """

    def __init__(self, nome_produto: str, pedida: Decimal, disponivel: Decimal) -> None:
        super().__init__(
            f"Não há {pedida} kg de '{nome_produto}' disponíveis. "
            f"Quantidade em estoque: {disponivel} kg."
        )
        self.nome_produto = nome_produto
        self.pedida = pedida
        self.disponivel = disponivel


class EmpresasDiferentesNoPedido(ErroDeNegocio):
    """RN14: um pedido não pode reunir produtos de empresas diferentes."""


class PedidoVazio(ErroDeNegocio):
    """RN13: um pedido precisa de ao menos um item."""


class TransicaoInvalida(ErroDeNegocio):
    """P7: transição de status não permitida pelo fluxo do pedido."""


class PrecoAlteradoEmVenda(ErroDeNegocio):
    """RN07: o preço não pode ser alterado durante uma venda em andamento."""


class AvaliacaoInvalida(ErroDeNegocio):
    """RN21 / P24: nota fora da escala de 1 a 5 estrelas, ou pedido não entregue."""


class AcessoNaoAutorizado(ErroDeNegocio):
    """RN12: a marisqueira só visualiza e altera os próprios produtos."""
