"""Aviso de um evento do pedido pra outra parte.

RN22 fala em informar o status da entrega, e informar precisa de alguém
recebendo. Cada transição de P7 deixa um aviso aqui. A caixa é da empresa
destinatária, não do pedido.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from dominio.enums import TipoNotificacao
from dominio.excecoes import DadoObrigatorio

if TYPE_CHECKING:
    from dominio.empresa import Empresa
    from dominio.pedido import Pedido


class Notificacao:
    """Um aviso endereçado a uma empresa, normalmente ligado a um pedido."""

    def __init__(
        self,
        destinatario: Empresa,
        tipo: TipoNotificacao,
        mensagem: str,
        pedido: Pedido | None = None,
        criado_em: datetime | None = None,
        lida: bool = False,
        id: int | None = None,
    ) -> None:
        if destinatario is None:
            raise DadoObrigatorio("A notificação precisa de um destinatário.")
        if not isinstance(tipo, TipoNotificacao):
            raise DadoObrigatorio("A notificação precisa de um tipo.")
        if not mensagem or not mensagem.strip():
            raise DadoObrigatorio("A notificação precisa de uma mensagem.")

        self.id = id
        self.destinatario = destinatario
        self.tipo = tipo
        self.mensagem = mensagem.strip()
        self.pedido = pedido
        self.criado_em = criado_em or datetime.now()
        self.lida = lida

    def marcar_como_lida(self) -> None:
        self.lida = True

    @property
    def nao_lida(self) -> bool:
        return not self.lida

    def __repr__(self) -> str:
        marca = " " if self.lida else "*"
        return f"<Notificacao{marca}{self.tipo.value} para {self.destinatario.nome!r}>"
