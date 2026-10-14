"""Configuração dos testes.

A plataforma "offscreen" permite construir e manipular as telas do Qt sem
abrir janela, o que é o que torna a interface testável em terminal e em CI.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
