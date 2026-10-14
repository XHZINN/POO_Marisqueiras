"""Marisquês, sistema Marisqueiras da Ilha.

Só liga as camadas: `repositorio` abre o banco e carrega os objetos,
`dominio` tem as regras e `ui` desenha as telas.

Rodar com: python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from repositorio.repositorio import Repositorio
from repositorio.seed import popular
from ui.estilo import QSS
from ui.janela_principal import JanelaPrincipal


def main() -> int:
    aplicacao = QApplication(sys.argv)
    aplicacao.setApplicationName("Marisquês")
    aplicacao.setStyleSheet(QSS)

    repo = Repositorio()
    if repo.esta_vazio():
        # Primeira execução: cria dados de demonstração (P4: Vila Maresia).
        popular(repo)
    repo.carregar()

    janela = JanelaPrincipal(repo)
    janela.show()
    return aplicacao.exec()


if __name__ == "__main__":
    sys.exit(main())
