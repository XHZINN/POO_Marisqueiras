"""Produto: oferta de uma empresa marisqueira.

Regras implementadas: RN04, RN05, RN06, RN07, RN08, RN09, RN17, RN18, RN20.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from dominio.enums import Categoria, SituacaoEmpresa
from dominio.excecoes import DadoObrigatorio, QuantidadeInvalida

if TYPE_CHECKING:  # evita import circular: só o verificador de tipos avalia
    from dominio.empresa import EmpresaMarisqueira


class Produto:
    """Um produto ofertado por uma empresa marisqueira.

    RN04: comercializado por quilograma.
    RN06: fresco e congelado são instâncias diferentes desta classe.
    RN07: o preço pertence ao par (produto, empresa).
    """

    # RN05: constante nomeada em vez de número solto no meio do código.
    QUANTIDADE_MINIMA_KG = Decimal("25")

    def __init__(
        self,
        nome: str,
        categoria: Categoria,
        preco_por_kg: Decimal,
        quantidade_disponivel_kg: Decimal,
        localizacao: str,
        empresa: EmpresaMarisqueira | None = None,
        foto: str | None = None,
        id: int | None = None,
    ) -> None:
        """Monta o produto.

        Os 25 kg de RN05 não são checados aqui de propósito: o construtor também
        reconstrói produto vindo do banco, e um estoque que caiu pra 20 kg
        vendendo (RN09) travaria a abertura do sistema. Quem exige os 25 kg é
        `cadastrar_produto` pra entrar e `validar_quantidade` pra vender.
        """
        if not nome or not nome.strip():
            raise DadoObrigatorio("O nome do produto é obrigatório.")
        if not isinstance(categoria, Categoria):
            raise DadoObrigatorio("A categoria do produto é obrigatória.")
        if preco_por_kg is None or preco_por_kg <= 0:
            raise DadoObrigatorio("O preço por kg deve ser maior que zero.")
        if not localizacao or not localizacao.strip():
            raise DadoObrigatorio("A localização do produto é obrigatória.")
        if quantidade_disponivel_kg is None or quantidade_disponivel_kg < 0:
            raise QuantidadeInvalida("A quantidade disponível não pode ser negativa.")

        self.id = id
        self.nome = nome.strip()
        self.categoria = categoria
        self.preco_por_kg = Decimal(preco_por_kg)
        self.quantidade_disponivel_kg = Decimal(quantidade_disponivel_kg)
        self.localizacao = localizacao.strip()
        self.empresa = empresa
        self.foto = foto  # P15: o único campo opcional do cadastro

    # Métodos exigidos pela atividade

    def verificar_disponibilidade(self, quantidade_kg: Decimal) -> bool:
        """RN17 e RN18: tem `quantidade_kg` em estoque?

        Consulta: não muda estado nem lança exceção. Não checa o mínimo de 25 kg,
        isso é do `ItemPedido.validar_quantidade`.
        """
        if quantidade_kg is None or quantidade_kg <= 0:
            return False
        return Decimal(quantidade_kg) <= self.quantidade_disponivel_kg

    def atualizar_quantidade(self, nova_quantidade_kg: Decimal) -> None:
        """RN08 / RN09: altera a quantidade disponível em estoque.

        Aceita zero: por RN09 o produto permanece cadastrado e visível,
        apenas marcado como indisponível. Rejeita valores negativos, que
        indicam erro de quem chamou.
        """
        if nova_quantidade_kg is None or Decimal(nova_quantidade_kg) < 0:
            raise QuantidadeInvalida("A quantidade em estoque não pode ser negativa.")
        self.quantidade_disponivel_kg = Decimal(nova_quantidade_kg)

    # Métodos complementares (não listados na atividade, exigidos pelas RNs)

    def baixar_estoque(self, quantidade_kg: Decimal) -> None:
        """Desconta `quantidade_kg` do estoque. Usado ao aceitar um pedido."""
        if not self.verificar_disponibilidade(quantidade_kg):
            from dominio.excecoes import QuantidadeIndisponivel

            raise QuantidadeIndisponivel(
                self.nome, Decimal(quantidade_kg), self.quantidade_disponivel_kg
            )
        self.atualizar_quantidade(
            self.quantidade_disponivel_kg - Decimal(quantidade_kg)
        )

    def alterar_preco(self, novo_preco: Decimal) -> None:
        """RN07: altera o preço por kg.

        A proteção contra alteração durante uma venda é aplicada por
        `EmpresaMarisqueira.alterar_preco_produto`, que é quem conhece os
        pedidos em andamento. Aqui só o valor em si é validado.
        """
        if novo_preco is None or novo_preco <= 0:
            raise DadoObrigatorio("O preço por kg deve ser maior que zero.")
        self.preco_por_kg = Decimal(novo_preco)

    # Atributos derivados: calculados, nunca armazenados

    @property
    def esta_disponivel(self) -> bool:
        """RN09 / RN15: o produto pode ser vendido?

        Exige o mínimo comercial de 25 kg: com menos que isso nenhum item de
        pedido válido pode ser montado, portanto o produto está
        efetivamente indisponível.
        """
        return self.quantidade_disponivel_kg >= self.QUANTIDADE_MINIMA_KG

    @property
    def situacao(self) -> SituacaoEmpresa:
        """RN20 / P33: indicador de cor do produto.

        Verde quando há estoque vendável; laranja quando há algum estoque,
        mas abaixo do mínimo comercial, ou quando ele zerou.
        """
        if self.esta_disponivel:
            return SituacaoEmpresa.DISPONIVEL
        return SituacaoEmpresa.ESTOQUE_BAIXO

    @property
    def nome_exibicao(self) -> str:
        """Nome com a categoria: RN06 trata fresco e congelado como distintos."""
        return f"{self.nome} ({self.categoria.rotulo})"

    def __repr__(self) -> str:
        return (
            f"<Produto {self.nome!r} {self.categoria.rotulo} "
            f"R${self.preco_por_kg}/kg {self.quantidade_disponivel_kg}kg>"
        )
