"""Converte entre os objetos do domínio e as tabelas do SQLite.

Única camada que conhece SQL. O `dominio/` não importa nada daqui, e é isso
que deixa testar as regras sem abrir banco.

Carrega o grafo inteiro na abertura (`carregar()`) e grava a cada operação
(`salvar_*`). Garante um objeto Python por linha do banco, o que importa
porque o domínio compara empresa e produto por identidade (`is`).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

from dominio.avaliacao import Avaliacao
from dominio.empresa import Empresa, EmpresaCompradora, EmpresaMarisqueira
from dominio.enums import (
    Categoria,
    StatusEntrega,
    StatusPedido,
    TipoNotificacao,
)
from dominio.item_pedido import ItemPedido
from dominio.notificacao import Notificacao
from dominio.pedido import Pedido
from dominio.produto import Produto
from repositorio.conexao import abrir_conexao


def _hora(texto: str) -> time:
    horas, minutos = texto.split(":")
    return time(int(horas), int(minutos))


class Repositorio:
    """Carrega e grava o grafo de objetos do domínio."""

    def __init__(self, caminho: str | Path | None = None) -> None:
        self.conexao: sqlite3.Connection = abrir_conexao(caminho)
        self.empresas: dict[int, Empresa] = {}
        self.produtos: dict[int, Produto] = {}
        self.pedidos: dict[int, Pedido] = {}
        self.avaliacoes: dict[int, Avaliacao] = {}
        self.notificacoes: dict[int, Notificacao] = {}

    # Consultas de conveniência para a interface

    @property
    def marisqueiras(self) -> list[EmpresaMarisqueira]:
        return [e for e in self.empresas.values() if isinstance(e, EmpresaMarisqueira)]

    @property
    def compradoras(self) -> list[EmpresaCompradora]:
        return [e for e in self.empresas.values() if isinstance(e, EmpresaCompradora)]

    @property
    def catalogo(self) -> list[Produto]:
        """Todos os produtos de todas as empresas.

        A filtragem por visibilidade (RN12) NÃO acontece aqui: é
        responsabilidade de `Empresa.consultar_produtos`, que é polimórfico.
        O repositório entrega o catálogo bruto; o domínio decide quem vê o quê.
        """
        return list(self.produtos.values())

    # Carga

    def carregar(self) -> None:
        """Reconstrói o grafo completo de objetos a partir do banco.

        A ordem importa: empresas antes de produtos (produto aponta para
        empresa), produtos antes de pedidos (item aponta para produto),
        pedidos antes de avaliações.
        """
        self.empresas.clear()
        self.produtos.clear()
        self.pedidos.clear()
        self.avaliacoes.clear()
        self.notificacoes.clear()

        self._carregar_empresas()
        self._carregar_produtos()
        self._carregar_pedidos()
        self._carregar_avaliacoes()
        self._carregar_notificacoes()

    def _carregar_empresas(self) -> None:
        for linha in self.conexao.execute("SELECT * FROM empresa ORDER BY id"):
            # O discriminador `tipo` decide qual subclasse reconstruir.
            classe = (
                EmpresaMarisqueira
                if linha["tipo"] == "marisqueira"
                else EmpresaCompradora
            )
            self.empresas[linha["id"]] = classe(
                nome=linha["nome"],
                cnpj=linha["cnpj"],
                email=linha["email"],
                telefone=linha["telefone"],
                endereco=linha["endereco"],
                localizacao=linha["localizacao"],
                abertura=_hora(linha["abertura"]),
                fechamento=_hora(linha["fechamento"]),
                id=linha["id"],
            )

    def _carregar_produtos(self) -> None:
        for linha in self.conexao.execute("SELECT * FROM produto ORDER BY id"):
            empresa = self.empresas.get(linha["empresa_id"])
            produto = Produto(
                nome=linha["nome"],
                categoria=Categoria(linha["categoria"]),
                preco_por_kg=Decimal(linha["preco_por_kg"]),
                # RN09: aqui pode vir "0" ou menos de 25 kg, e é por isso
                # que o Produto não valida RN05 no construtor.
                quantidade_disponivel_kg=Decimal(linha["quantidade_disponivel_kg"]),
                localizacao=linha["localizacao"],
                empresa=empresa,
                foto=linha["foto"],
                id=linha["id"],
            )
            self.produtos[linha["id"]] = produto
            if isinstance(empresa, EmpresaMarisqueira):
                empresa.produtos.append(produto)

    def _carregar_pedidos(self) -> None:
        for linha in self.conexao.execute("SELECT * FROM pedido ORDER BY id"):
            compradora = self.empresas.get(linha["compradora_id"])
            marisqueira = self.empresas.get(linha["marisqueira_id"])
            pedido = Pedido(
                compradora=compradora,
                endereco_entrega=linha["endereco_entrega"],
                tempo_entrega_dias=linha["tempo_entrega_dias"],
                marisqueira=marisqueira,
                status=StatusPedido(linha["status"]),
                status_entrega=StatusEntrega(linha["status_entrega"]),
                criado_em=datetime.fromisoformat(linha["criado_em"]),
                id=linha["id"],
            )
            pedido.motivo_rejeicao = linha["motivo_rejeicao"]
            pedido.observacao_ajuste = linha["observacao_ajuste"]

            for item_linha in self.conexao.execute(
                "SELECT * FROM item_pedido WHERE pedido_id = ? ORDER BY id",
                (linha["id"],),
            ):
                produto = self.produtos.get(item_linha["produto_id"])
                if produto is None:
                    continue
                # Anexa direto, sem `adicionar_item`: já foi validado na
                # criação, e revalidar RN18 contra o estoque de hoje
                # recusaria pedido antigo que era válido na época.
                pedido.itens.append(
                    ItemPedido(
                        produto=produto,
                        quantidade_kg=Decimal(item_linha["quantidade_kg"]),
                        preco_unitario=Decimal(item_linha["preco_unitario"]),  # RN07
                        id=item_linha["id"],
                    )
                )

            self.pedidos[linha["id"]] = pedido
            if isinstance(compradora, EmpresaCompradora):
                compradora.pedidos.append(pedido)
            if isinstance(marisqueira, EmpresaMarisqueira):
                marisqueira.pedidos_recebidos.append(pedido)

    def _carregar_avaliacoes(self) -> None:
        for linha in self.conexao.execute("SELECT * FROM avaliacao ORDER BY id"):
            pedido = self.pedidos.get(linha["pedido_id"])
            if pedido is None:
                continue
            avaliacao = Avaliacao(
                pedido=pedido,
                nota=linha["nota"],
                comentario=linha["comentario"],
                criado_em=datetime.fromisoformat(linha["criado_em"]),
                id=linha["id"],
            )
            self.avaliacoes[linha["id"]] = avaliacao
            if isinstance(pedido.marisqueira, EmpresaMarisqueira):
                pedido.marisqueira.registrar_avaliacao(avaliacao)

    def _carregar_notificacoes(self) -> None:
        for linha in self.conexao.execute("SELECT * FROM notificacao ORDER BY id"):
            destinatario = self.empresas.get(linha["destinatario_id"])
            if destinatario is None:
                continue
            notificacao = Notificacao(
                destinatario=destinatario,
                tipo=TipoNotificacao(linha["tipo"]),
                mensagem=linha["mensagem"],
                pedido=self.pedidos.get(linha["pedido_id"]),
                criado_em=datetime.fromisoformat(linha["criado_em"]),
                lida=bool(linha["lida"]),
                id=linha["id"],
            )
            self.notificacoes[linha["id"]] = notificacao
            destinatario.notificacoes.append(notificacao)

    # Gravação

    def salvar_empresa(self, empresa: Empresa) -> Empresa:
        tipo = (
            "marisqueira" if isinstance(empresa, EmpresaMarisqueira) else "compradora"
        )
        dados = (
            tipo,
            empresa.nome,
            empresa.cnpj,
            empresa.email,
            empresa.telefone,
            empresa.endereco,
            empresa.localizacao,
            empresa.abertura.strftime("%H:%M"),
            empresa.fechamento.strftime("%H:%M"),
        )
        if empresa.id is None:
            cursor = self.conexao.execute(
                """INSERT INTO empresa
                   (tipo, nome, cnpj, email, telefone, endereco, localizacao,
                    abertura, fechamento)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                dados,
            )
            empresa.id = cursor.lastrowid
        else:
            self.conexao.execute(
                """UPDATE empresa SET tipo = ?, nome = ?, cnpj = ?, email = ?,
                   telefone = ?, endereco = ?, localizacao = ?, abertura = ?,
                   fechamento = ? WHERE id = ?""",
                (*dados, empresa.id),
            )
        self.conexao.commit()
        self.empresas[empresa.id] = empresa
        return empresa

    def salvar_produto(self, produto: Produto) -> Produto:
        if produto.empresa is None or produto.empresa.id is None:
            raise ValueError("O produto precisa de uma empresa já gravada.")
        dados = (
            produto.empresa.id,
            produto.nome,
            produto.categoria.value,
            str(produto.preco_por_kg),
            str(produto.quantidade_disponivel_kg),
            produto.localizacao,
            produto.foto,
        )
        if produto.id is None:
            cursor = self.conexao.execute(
                """INSERT INTO produto
                   (empresa_id, nome, categoria, preco_por_kg,
                    quantidade_disponivel_kg, localizacao, foto)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                dados,
            )
            produto.id = cursor.lastrowid
        else:
            self.conexao.execute(
                """UPDATE produto SET empresa_id = ?, nome = ?, categoria = ?,
                   preco_por_kg = ?, quantidade_disponivel_kg = ?,
                   localizacao = ?, foto = ? WHERE id = ?""",
                (*dados, produto.id),
            )
        self.conexao.commit()
        self.produtos[produto.id] = produto
        return produto

    def salvar_pedido(self, pedido: Pedido) -> Pedido:
        """Grava o pedido e seus itens, e os estoques afetados.

        Os itens são apagados e reinseridos. Para pedidos com poucos itens
        isso é mais simples e menos sujeito a erro que reconciliar linha por
        linha, e acontece dentro da mesma transação.
        """
        if pedido.compradora.id is None or pedido.marisqueira is None:
            raise ValueError("Pedido sem compradora ou marisqueira gravadas.")
        dados = (
            pedido.compradora.id,
            pedido.marisqueira.id,
            pedido.status.value,
            pedido.status_entrega.value,
            pedido.endereco_entrega,
            pedido.tempo_entrega_dias,
            pedido.criado_em.isoformat(timespec="seconds"),
            pedido.motivo_rejeicao,
            pedido.observacao_ajuste,
        )
        if pedido.id is None:
            cursor = self.conexao.execute(
                """INSERT INTO pedido
                   (compradora_id, marisqueira_id, status, status_entrega,
                    endereco_entrega, tempo_entrega_dias, criado_em,
                    motivo_rejeicao, observacao_ajuste)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                dados,
            )
            pedido.id = cursor.lastrowid
        else:
            self.conexao.execute(
                """UPDATE pedido SET compradora_id = ?, marisqueira_id = ?,
                   status = ?, status_entrega = ?, endereco_entrega = ?,
                   tempo_entrega_dias = ?, criado_em = ?, motivo_rejeicao = ?,
                   observacao_ajuste = ? WHERE id = ?""",
                (*dados, pedido.id),
            )

        self.conexao.execute(
            "DELETE FROM item_pedido WHERE pedido_id = ?", (pedido.id,)
        )
        for item in pedido.itens:
            if item.produto.id is None:
                self.salvar_produto(item.produto)
            cursor = self.conexao.execute(
                """INSERT INTO item_pedido
                   (pedido_id, produto_id, quantidade_kg, preco_unitario)
                   VALUES (?, ?, ?, ?)""",
                (
                    pedido.id,
                    item.produto.id,
                    str(item.quantidade_kg),
                    str(item.preco_unitario),  # RN07: preço histórico
                ),
            )
            item.id = cursor.lastrowid

        self.conexao.commit()

        # O aceite baixa o estoque (RN18): persiste a nova quantidade.
        for item in pedido.itens:
            self.salvar_produto(item.produto)

        self.pedidos[pedido.id] = pedido
        self.sincronizar_notificacoes()
        return pedido

    def salvar_avaliacao(self, avaliacao: Avaliacao) -> Avaliacao:
        if avaliacao.pedido.id is None:
            raise ValueError("A avaliação precisa de um pedido já gravado.")
        dados = (
            avaliacao.pedido.id,
            avaliacao.nota,
            avaliacao.comentario,
            avaliacao.criado_em.isoformat(timespec="seconds"),
        )
        if avaliacao.id is None:
            cursor = self.conexao.execute(
                """INSERT INTO avaliacao (pedido_id, nota, comentario, criado_em)
                   VALUES (?, ?, ?, ?)""",
                dados,
            )
            avaliacao.id = cursor.lastrowid
        else:
            self.conexao.execute(
                """UPDATE avaliacao SET pedido_id = ?, nota = ?, comentario = ?,
                   criado_em = ? WHERE id = ?""",
                (*dados, avaliacao.id),
            )
        self.conexao.commit()
        self.avaliacoes[avaliacao.id] = avaliacao
        self.sincronizar_notificacoes()
        return avaliacao

    def salvar_notificacao(self, notificacao: Notificacao) -> Notificacao:
        if notificacao.destinatario.id is None:
            raise ValueError("A notificação precisa de um destinatário gravado.")
        dados = (
            notificacao.destinatario.id,
            notificacao.tipo.value,
            notificacao.mensagem,
            notificacao.pedido.id if notificacao.pedido is not None else None,
            notificacao.criado_em.isoformat(timespec="seconds"),
            1 if notificacao.lida else 0,
        )
        if notificacao.id is None:
            cursor = self.conexao.execute(
                """INSERT INTO notificacao
                   (destinatario_id, tipo, mensagem, pedido_id, criado_em, lida)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                dados,
            )
            notificacao.id = cursor.lastrowid
        else:
            self.conexao.execute(
                """UPDATE notificacao SET destinatario_id = ?, tipo = ?,
                   mensagem = ?, pedido_id = ?, criado_em = ?, lida = ?
                   WHERE id = ?""",
                (*dados, notificacao.id),
            )
        self.conexao.commit()
        self.notificacoes[notificacao.id] = notificacao
        return notificacao

    def sincronizar_notificacoes(self) -> int:
        """Grava as notificações que o domínio criou e ainda não têm id.

        O domínio cria aviso como efeito das operações (aceitar pedido avisa a
        compradora). Em vez de cada tela lembrar de gravar, o repositório recolhe
        os pendentes depois do pedido, quando o `pedido_id` já existe.
        """
        gravadas = 0
        for empresa in self.empresas.values():
            for notificacao in empresa.notificacoes:
                if notificacao.id is None:
                    self.salvar_notificacao(notificacao)
                    gravadas += 1
        return gravadas

    def marcar_notificacoes_como_lidas(self, empresa) -> int:
        alteradas = empresa.marcar_notificacoes_como_lidas()
        for notificacao in alteradas:
            self.salvar_notificacao(notificacao)
        return len(alteradas)

    def esta_vazio(self) -> bool:
        linha = self.conexao.execute("SELECT COUNT(*) AS n FROM empresa").fetchone()
        return linha["n"] == 0

    def fechar(self) -> None:
        self.conexao.close()
