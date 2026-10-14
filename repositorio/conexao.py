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
    return conexao
