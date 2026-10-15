"""Endereço salvo da empresa compradora.

Uma compradora tem vários: matriz, restaurante, depósito. O pedido escolhe
um deles e guarda uma cópia, pela mesma razão de RN07 com o preço: mudar o
endereço cadastrado amanhã não pode reescrever para onde o pedido de hoje
foi entregue.
"""

from __future__ import annotations

import re

from dominio.coordenada import Coordenada
from dominio.excecoes import DadoObrigatorio

CEP = re.compile(r"^\d{5}-?\d{3}$")

# Endereço sem número existe de verdade (sítio, galpão, casa sem placa). O
# campo continua obrigatório — o que se guarda é a marca, não o vazio.
SEM_NUMERO = "S/N"

# Como as pessoas escrevem "sem número" na vida real; tudo vira SEM_NUMERO.
_SEM_NUMERO = {"s/n", "sn", "s.n.", "s/nº", "s/no", "sem numero", "sem número"}

UFS = tuple(
    "AC AL AM AP BA CE DF ES GO MA MG MS MT "
    "PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
)


class Endereco:
    """Endereço de entrega cadastrado, com apelido e coordenada."""

    def __init__(
        self,
        apelido: str,
        logradouro: str,
        numero: str,
        bairro: str,
        cidade: str,
        uf: str = "MA",
        cep: str | None = None,
        complemento: str | None = None,
        referencia: str | None = None,
        coordenada: Coordenada | None = None,
        principal: bool = False,
        id: int | None = None,
    ) -> None:
        for campo, valor in (
            ("apelido", apelido),
            ("logradouro", logradouro),
            ("número", numero),
            ("bairro", bairro),
            ("cidade", cidade),
        ):
            if not valor or not str(valor).strip():
                raise DadoObrigatorio(f"O campo {campo} do endereço é obrigatório.")

        sigla = (uf or "").strip().upper()
        if sigla not in UFS:
            raise DadoObrigatorio(f"UF inválida: {uf!r}.")

        cep_limpo = (cep or "").strip()
        if cep_limpo and not CEP.match(cep_limpo):
            raise DadoObrigatorio(f"CEP inválido: {cep!r}. Use o formato 00000-000.")

        self.id = id
        self.apelido = apelido.strip()
        self.logradouro = logradouro.strip()
        self.numero = self._normalizar_numero(numero)
        self.bairro = bairro.strip()
        self.cidade = cidade.strip()
        self.uf = sigla
        self.cep = self._formatar_cep(cep_limpo)
        self.complemento = (complemento or "").strip() or None
        self.referencia = (referencia or "").strip() or None
        self.coordenada = coordenada
        self.principal = bool(principal)

    @staticmethod
    def _normalizar_numero(numero: str) -> str:
        """Uniformiza as várias grafias de "sem número" numa só."""
        limpo = str(numero).strip()
        return SEM_NUMERO if limpo.casefold() in _SEM_NUMERO else limpo

    @staticmethod
    def _formatar_cep(cep: str) -> str | None:
        if not cep:
            return None
        digitos = cep.replace("-", "")
        return f"{digitos[:5]}-{digitos[5:]}"

    def copiar(self) -> Endereco:
        """Cópia pra congelar no pedido, sem o id e sem a marca de principal."""
        return Endereco(
            apelido=self.apelido,
            logradouro=self.logradouro,
            numero=self.numero,
            bairro=self.bairro,
            cidade=self.cidade,
            uf=self.uf,
            cep=self.cep,
            complemento=self.complemento,
            referencia=self.referencia,
            coordenada=self.coordenada,
        )

    @property
    def linha(self) -> str:
        """Endereço em uma linha, como vai no pedido."""
        inicio = f"{self.logradouro}, {self.numero}"
        if self.complemento:
            inicio += f", {self.complemento}"
        fim = f"{self.bairro}, {self.cidade}/{self.uf}"
        if self.cep:
            fim += f" · CEP {self.cep}"
        return f"{inicio} - {fim}"

    @property
    def sem_numero(self) -> bool:
        return self.numero == SEM_NUMERO

    @property
    def consulta_geocodificacao(self) -> str:
        """Texto que o geocodificador recebe pra achar a coordenada."""
        # "S/N" não é número de porta: mandar isso pro Nominatim só atrapalha
        # a busca, então o que vai é a rua com o bairro.
        numero = "" if self.sem_numero else f"{self.numero}, "
        return (
            f"{self.logradouro}, {numero}{self.bairro}, "
            f"{self.cidade}, {self.uf}, Brasil"
        )

    @property
    def tem_coordenada(self) -> bool:
        return self.coordenada is not None

    def resumo(self) -> str:
        marca = " (principal)" if self.principal else ""
        return f"{self.apelido}{marca} · {self.linha}"

    def __str__(self) -> str:
        return self.linha

    def __repr__(self) -> str:
        return f"<Endereco #{self.id} {self.apelido!r}>"
