"""Enums do domínio.

Cada um é um conjunto fechado de valores que vem das regras de negócio.

Convenção: `.value` é o código técnico em snake_case que vai pro SQLite e
`.rotulo` é o texto com acento que vai pra tela.
"""

from enum import Enum


class RotuladoEnum(Enum):
    """Base para enums cujo valor é a tupla (codigo, rotulo).

    `__new__` é executado na criação de cada membro, recebendo a tupla já
    desempacotada em parâmetros. `_value_` é o atributo interno que alimenta
    o `.value` público: sem atribuí-lo, `.value` seria a tupla inteira.
    """

    def __new__(cls, codigo: str, rotulo: str):
        obj = object.__new__(cls)
        obj._value_ = codigo
        obj.rotulo = rotulo
        return obj


class Categoria(RotuladoEnum):
    """RN06 / P18: fresco e congelado são cadastrados como produtos diferentes."""

    FRESCO = ("fresco", "Fresco")
    CONGELADO = ("congelado", "Congelado")


class StatusPedido(RotuladoEnum):
    """P7 e RN13: ciclo de vida do pedido.

    análise -> (aceito | rejeitado | ajuste solicitado) -> preparação -> entregue

    AJUSTE_SOLICITADO não vai direto pra ACEITO: depois do ajuste quem decide
    é a compradora, reenviando ou cancelando.
    """

    AGUARDANDO_ANALISE = ("aguardando_analise", "Aguardando análise")
    AJUSTE_SOLICITADO = ("ajuste_solicitado", "Ajuste solicitado")
    ACEITO = ("aceito", "Aceito")
    REJEITADO = ("rejeitado", "Rejeitado")
    CANCELADO = ("cancelado", "Cancelado")
    EM_PREPARACAO = ("em_preparacao", "Em preparação")
    ENTREGUE = ("entregue", "Entregue")


class StatusEntrega(RotuladoEnum):
    """RN22: a entrega é feita pela própria marisqueira, sem rastreio em tempo real."""

    NAO_INICIADA = ("nao_iniciada", "Não iniciada")
    EM_PREPARACAO = ("em_preparacao", "Em preparação")
    SAIU_PARA_ENTREGA = ("saiu_para_entrega", "Saiu para entrega")
    ENTREGUE = ("entregue", "Entregue")


class OrdenacaoBusca(RotuladoEnum):
    """RN11 / P22: critérios de ordenação da busca de produtos."""

    MENOR_PRECO = ("menor_preco", "Menor preço")
    MAIOR_PRECO = ("maior_preco", "Maior preço")
    MELHOR_AVALIACAO = ("melhor_avaliacao", "Melhor avaliação")
    PROXIMIDADE = ("proximidade", "Proximidade")


class SituacaoEmpresa(Enum):
    """RN20 / P33: indicador visual da situação da empresa marisqueira.

    Define o próprio `__new__` porque carrega TRÊS dados, não dois. As cores
    estão no domínio porque RN20 e P33 as nomeiam explicitamente como
    requisito de negócio, não como escolha de interface.
    """

    DISPONIVEL = ("disponivel", "Disponível", "#2E7D32")
    ESTOQUE_BAIXO = ("estoque_baixo", "Estoque baixo", "#EF6C00")
    FORA_DE_HORARIO = ("fora_de_horario", "Fora do horário de funcionamento", "#C62828")

    def __new__(cls, codigo: str, rotulo: str, cor: str):
        obj = object.__new__(cls)
        obj._value_ = codigo
        obj.rotulo = rotulo
        obj.cor = cor
        return obj


class TipoNotificacao(RotuladoEnum):
    """Eventos do pedido que geram aviso para a outra parte.

    Cada tipo nasce de uma transição de P7. O destinatário é sempre a
    contraparte de quem agiu: a marisqueira age, a compradora é avisada, e
    vice-versa.
    """

    PEDIDO_RECEBIDO = ("pedido_recebido", "Novo pedido recebido")
    PEDIDO_ACEITO = ("pedido_aceito", "Pedido aceito")
    PEDIDO_REJEITADO = ("pedido_rejeitado", "Pedido rejeitado")
    AJUSTE_SOLICITADO = ("ajuste_solicitado", "Ajuste solicitado")
    PEDIDO_REENVIADO = ("pedido_reenviado", "Pedido reenviado após ajuste")
    PEDIDO_CANCELADO = ("pedido_cancelado", "Pedido cancelado")
    SAIU_PARA_ENTREGA = ("saiu_para_entrega", "Pedido saiu para entrega")
    ENTREGA_CONFIRMADA = ("entrega_confirmada", "Entrega confirmada")
    AVALIACAO_RECEBIDA = ("avaliacao_recebida", "Avaliação recebida")
    PAGAMENTO_INFORMADO = ("pagamento_informado", "Pagamento informado")
    PAGAMENTO_CONFIRMADO = ("pagamento_confirmado", "Pagamento confirmado")


class FormaPagamento(Enum):
    """Formas de pagamento aceitas na plataforma.

    Extensão além dos requisitos: P27 deixa pagamento fora do escopo. As
    opções são as usuais de B2B no Brasil.

    `antecipado` diz se o pagamento tem que estar confirmado antes do
    despacho. Boleto a prazo é a exceção: a mercadoria sai antes.
    """

    PIX = ("pix", "PIX", True)
    TRANSFERENCIA = ("transferencia", "Transferência bancária", True)
    BOLETO = ("boleto", "Boleto à vista", True)
    BOLETO_PRAZO = ("boleto_prazo", "Boleto a prazo, 30 dias", False)

    def __new__(cls, codigo: str, rotulo: str, antecipado: bool):
        obj = object.__new__(cls)
        obj._value_ = codigo
        obj.rotulo = rotulo
        obj.antecipado = antecipado
        return obj


class StatusPagamento(RotuladoEnum):
    """Andamento do pagamento, separado do andamento da entrega.

    São dois eixos independentes: um pedido pode estar pago e não entregue
    (PIX antecipado) ou entregue e não pago (boleto a prazo).
    """

    PENDENTE = ("pendente", "Pendente")
    INFORMADO = ("informado", "Informado pela compradora")
    CONFIRMADO = ("confirmado", "Confirmado")
    ESTORNADO = ("estornado", "Estornado")


class MetodoColeta(RotuladoEnum):
    """Como o marisco foi coletado. Parte da ficha de origem.

    Extensão além dos requisitos: P2 deixa rastreabilidade como
    possibilidade futura.
    """

    CATACAO_MANUAL = ("catacao_manual", "Catação manual")
    MERGULHO = ("mergulho", "Mergulho livre")
    REDE = ("rede", "Rede de arrasto")
    ARMADILHA = ("armadilha", "Armadilha e covo")
