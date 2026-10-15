"""Conexão com o banco SQLite e criação do esquema."""

from __future__ import annotations

import sqlite3
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "marisqueiras.db"
CAMINHO_SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def abrir_conexao(caminho: str | Path | None = None) -> sqlite3.Connection:
    """Abre o banco e cria o schema se ainda não existir.

    `row_factory = sqlite3.Row` deixa acessar coluna por nome. O
    `foreign_keys = ON` é obrigatório: o SQLite vem com FK desligada e sem
    isso os REFERENCES do schema não valem nada.
    """
    destino = Path(caminho) if caminho is not None else CAMINHO_PADRAO
    conexao = sqlite3.connect(destino)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.executescript(CAMINHO_SCHEMA.read_text(encoding="utf-8"))
    _migrar(conexao)
    return conexao


# Colunas acrescentadas depois que o banco já existia. `CREATE TABLE IF NOT
# EXISTS` não mexe em tabela que já está lá, então um banco antigo precisa do
# ALTER. Quem já está atualizado erra com "duplicate column name" e segue.
COLUNAS_NOVAS = (
    ("empresa", "latitude", "REAL"),
    ("empresa", "longitude", "REAL"),
    ("pedido", "forma_pagamento", "TEXT NOT NULL DEFAULT 'pix'"),
    ("pedido", "status_pagamento", "TEXT NOT NULL DEFAULT 'pendente'"),
    ("pedido", "pago_em", "TEXT"),
    ("pedido", "entrega_latitude", "REAL"),
    ("pedido", "entrega_longitude", "REAL"),
    ("item_pedido", "origem_lote", "TEXT"),
    ("item_pedido", "origem_data_coleta", "TEXT"),
    ("item_pedido", "origem_local", "TEXT"),
    ("item_pedido", "origem_responsavel", "TEXT"),
    ("item_pedido", "origem_metodo", "TEXT"),
    ("item_pedido", "origem_latitude", "REAL"),
    ("item_pedido", "origem_longitude", "REAL"),
    ("item_pedido", "origem_observacoes", "TEXT"),
)


def _migrar(conexao: sqlite3.Connection) -> None:
    for tabela, coluna, tipo in COLUNAS_NOVAS:
        try:
            conexao.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        except sqlite3.OperationalError as erro:
            if "duplicate column" not in str(erro).lower():
                raise
    conexao.commit()
