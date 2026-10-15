"""Converte entre os objetos do domínio e as tabelas do SQLite.

Única camada que conhece SQL. O `dominio/` não importa nada daqui, e é isso
que deixa testar as regras sem abrir banco.

Carrega o grafo inteiro na abertura (`carregar()`) e grava a cada operação
(`salvar_*`). Garante um objeto Python por linha do banco, o que importa
porque o domínio compara empresa e produto por identidade (`is`).
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from dominio.avaliacao import Avaliacao
from dominio.coordenada import Coordenada
from dominio.empresa import Empresa, EmpresaCompradora, EmpresaMarisqueira
from dominio.endereco import Endereco
from dominio.entrega import EventoEntrega
from dominio.enums import (
    Categoria,
    FormaPagamento,
    MetodoColeta,
    StatusEntrega,
    StatusPagamento,
    StatusPedido,
    TipoNotificacao,
)
from dominio.item_pedido import ItemPedido
from dominio.notificacao import Notificacao
from dominio.pedido import Pedido
from dominio.produto import Produto
from dominio.rastreabilidade import Rastreabilidade
from repositorio.conexao import abrir_conexao


def _coordenada(linha, prefixo: str = "") -> Coordenada | None:
    """Monta a coordenada se as duas colunas estiverem preenchidas."""
    lat = linha[f"{prefixo}latitude"]
    lon = linha[f"{prefixo}longitude"]
    if lat is None or lon is None:
        return None
    return Coordenada(float(lat), float(lon))


def _colunas_origem(origem) -> tuple:
    """As oito colunas origem_* do item, ou None em todas."""
    if origem is None:
        return (None,) * 8
    return (
        origem.lote,
        origem.data_coleta.isoformat(),
        origem.local_coleta,
        origem.responsavel,
        origem.metodo.value,
        origem.coordenada.latitude if origem.coordenada else None,
        origem.coordenada.longitude if origem.coordenada else None,
        origem.observacoes,
    )


def _colunas_entrega(endereco) -> tuple:
    """As nove colunas entrega_* do pedido, ou None em todas.

    Mesma ideia de `_colunas_origem`: a cópia do endereço fica achatada em
    colunas do próprio pedido, porque é dado congelado na compra e não um
    cadastro que vive por conta própria.
    """
    if endereco is None:
        return (None,) * 9
    return (
        endereco.apelido,
        endereco.logradouro,
        endereco.numero,
        endereco.bairro,
        endereco.cidade,
        endereco.uf,
        endereco.cep,
        endereco.complemento,
        endereco.referencia,
    )


def _endereco_congelado(linha) -> Endereco | None:
    """Reconstrói a cópia do endereço gravada no pedido."""
    if linha["entrega_logradouro"] is None:
        return None
    return Endereco(
        apelido=linha["entrega_apelido"] or "Entrega",
        logradouro=linha["entrega_logradouro"],
        numero=linha["entrega_numero"] or "s/n",
        bairro=linha["entrega_bairro"] or "-",
        cidade=linha["entrega_cidade"] or "-",
        uf=linha["entrega_uf"] or "MA",
        cep=linha["entrega_cep"],
        complemento=linha["entrega_complemento"],
        referencia=linha["entrega_referencia"],
        coordenada=_coordenada(linha, "entrega_"),
    )


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
        self._carregar_enderecos()
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
            empresa_nova = classe(
                nome=linha["nome"],
                cnpj=linha["cnpj"],
                email=linha["email"],
                telefone=linha["telefone"],
                endereco=linha["endereco"],
                localizacao=linha["localizacao"],
                abertura=_hora(linha["abertura"]),
                fechamento=_hora(linha["fechamento"]),
                coordenada=_coordenada(linha),
                id=linha["id"],
            )
            if isinstance(empresa_nova, EmpresaMarisqueira):
                if linha["preparo_horas"] is not None:
                    empresa_nova.prazo_preparo_horas = int(linha["preparo_horas"])
                if linha["raio_entrega_km"] is not None:
                    empresa_nova.raio_entrega_km = Decimal(linha["raio_entrega_km"])
            self.empresas[linha["id"]] = empresa_nova

        # Formas de pagamento aceitas por cada marisqueira (extensão de P27).
        for linha in self.conexao.execute("SELECT * FROM empresa_forma_pagamento"):
            empresa = self.empresas.get(linha["empresa_id"])
            if isinstance(empresa, EmpresaMarisqueira):
                if not hasattr(empresa, "_formas_carregadas"):
                    empresa.formas_pagamento_aceitas = set()
                    empresa._formas_carregadas = True
                empresa.formas_pagamento_aceitas.add(FormaPagamento(linha["forma"]))

    def _carregar_enderecos(self) -> None:
        """Endereços de entrega cadastrados pelas compradoras.

        Anexa direto na lista em vez de passar por `adicionar_endereco`: o que
        está no banco já foi validado quando foi cadastrado, e o método
        promoveria o primeiro a principal, trocando a escolha que está
        gravada na coluna `principal`.
        """
        for linha in self.conexao.execute(
            "SELECT * FROM endereco ORDER BY empresa_id, id"
        ):
            empresa = self.empresas.get(linha["empresa_id"])
            if not isinstance(empresa, EmpresaCompradora):
                continue
            empresa.enderecos.append(
                Endereco(
                    apelido=linha["apelido"],
                    logradouro=linha["logradouro"],
                    numero=linha["numero"],
                    bairro=linha["bairro"],
                    cidade=linha["cidade"],
                    uf=linha["uf"],
                    cep=linha["cep"],
                    complemento=linha["complemento"],
                    referencia=linha["referencia"],
                    coordenada=_coordenada(linha),
                    principal=bool(linha["principal"]),
                    id=linha["id"],
                )
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

        for linha in self.conexao.execute("SELECT * FROM rastreabilidade"):
            produto = self.produtos.get(linha["produto_id"])
            if produto is None:
                continue
            produto.rastreabilidade = Rastreabilidade(
                lote=linha["lote"],
                data_coleta=date.fromisoformat(linha["data_coleta"]),
                local_coleta=linha["local_coleta"],
                responsavel=linha["responsavel"],
                metodo=MetodoColeta(linha["metodo"]),
                coordenada=_coordenada(linha),
                observacoes=linha["observacoes"],
                id=linha["id"],
            )

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
                forma_pagamento=FormaPagamento(linha["forma_pagamento"]),
                status_pagamento=StatusPagamento(linha["status_pagamento"]),
                coordenada_entrega=_coordenada(linha, "entrega_"),
                prazo_confirmado=bool(linha["prazo_confirmado"]),
                previsao_entrega=(
                    datetime.fromisoformat(linha["previsao_entrega"])
                    if linha["previsao_entrega"]
                    else None
                ),
                criado_em=datetime.fromisoformat(linha["criado_em"]),
                id=linha["id"],
            )
            # A cópia congelada entra depois da construção pra o texto de
            # `endereco_entrega` continuar sendo exatamente o que foi gravado.
            pedido.endereco = _endereco_congelado(linha)
            pedido.motivo_rejeicao = linha["motivo_rejeicao"]
            pedido.observacao_ajuste = linha["observacao_ajuste"]
            if linha["pago_em"]:
                pedido.pago_em = datetime.fromisoformat(linha["pago_em"])

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
                origem = None
                if item_linha["origem_lote"]:
                    origem = Rastreabilidade(
                        lote=item_linha["origem_lote"],
                        data_coleta=date.fromisoformat(
                            item_linha["origem_data_coleta"]
                        ),
                        local_coleta=item_linha["origem_local"],
                        responsavel=item_linha["origem_responsavel"],
                        metodo=MetodoColeta(item_linha["origem_metodo"]),
                        coordenada=_coordenada(item_linha, "origem_"),
                        observacoes=item_linha["origem_observacoes"],
                    )
                pedido.itens.append(
                    ItemPedido(
                        produto=produto,
                        quantidade_kg=Decimal(item_linha["quantidade_kg"]),
                        preco_unitario=Decimal(item_linha["preco_unitario"]),  # RN07
                        origem=origem,
                        id=item_linha["id"],
                    )
                )

            for evento_linha in self.conexao.execute(
                "SELECT * FROM evento_entrega WHERE pedido_id = ? ORDER BY id",
                (linha["id"],),
            ):
                pedido.eventos_entrega.append(
                    EventoEntrega(
                        pedido=pedido,
                        coordenada=Coordenada(
                            float(evento_linha["latitude"]),
                            float(evento_linha["longitude"]),
                        ),
                        descricao=evento_linha["descricao"],
                        registrado_em=datetime.fromisoformat(
                            evento_linha["registrado_em"]
                        ),
                        id=evento_linha["id"],
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
            empresa.coordenada.latitude if empresa.coordenada else None,
            empresa.coordenada.longitude if empresa.coordenada else None,
            # Só a marisqueira entrega, então na compradora as duas ficam nulas.
            getattr(empresa, "prazo_preparo_horas", None),
            (
                str(empresa.raio_entrega_km)
                if getattr(empresa, "raio_entrega_km", None) is not None
                else None
            ),
        )
        if empresa.id is None:
            cursor = self.conexao.execute(
                """INSERT INTO empresa
                   (tipo, nome, cnpj, email, telefone, endereco, localizacao,
                    abertura, fechamento, latitude, longitude, preparo_horas,
                    raio_entrega_km)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                dados,
            )
            empresa.id = cursor.lastrowid
        else:
            self.conexao.execute(
                """UPDATE empresa SET tipo = ?, nome = ?, cnpj = ?, email = ?,
                   telefone = ?, endereco = ?, localizacao = ?, abertura = ?,
                   fechamento = ?, latitude = ?, longitude = ?,
                   preparo_horas = ?, raio_entrega_km = ? WHERE id = ?""",
                (*dados, empresa.id),
            )
        if isinstance(empresa, EmpresaMarisqueira):
            self.conexao.execute(
                "DELETE FROM empresa_forma_pagamento WHERE empresa_id = ?",
                (empresa.id,),
            )
            self.conexao.executemany(
                "INSERT INTO empresa_forma_pagamento (empresa_id, forma) VALUES (?, ?)",
                [(empresa.id, f.value) for f in empresa.formas_pagamento_aceitas],
            )
        if isinstance(empresa, EmpresaCompradora):
            self._gravar_enderecos(empresa)

        self.conexao.commit()
        self.empresas[empresa.id] = empresa
        return empresa

    def _gravar_enderecos(self, empresa: EmpresaCompradora) -> None:
        """Põe a tabela `endereco` igual à lista da compradora.

        Insere os novos, atualiza os que já têm id e apaga do banco os que
        saíram da lista. Não apaga tudo pra reinserir porque o id do endereço
        é o que a interface usa pra lembrar qual linha estava selecionada.
        """
        guardados: list[int] = []
        for endereco in empresa.enderecos:
            dados = (
                empresa.id,
                endereco.apelido,
                endereco.logradouro,
                endereco.numero,
                endereco.bairro,
                endereco.cidade,
                endereco.uf,
                endereco.cep,
                endereco.complemento,
                endereco.referencia,
                endereco.coordenada.latitude if endereco.coordenada else None,
                endereco.coordenada.longitude if endereco.coordenada else None,
                1 if endereco.principal else 0,
            )
            if endereco.id is None:
                cursor = self.conexao.execute(
                    """INSERT INTO endereco
                       (empresa_id, apelido, logradouro, numero, bairro,
                        cidade, uf, cep, complemento, referencia, latitude,
                        longitude, principal)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    dados,
                )
                endereco.id = cursor.lastrowid
            else:
                self.conexao.execute(
                    """UPDATE endereco SET empresa_id = ?, apelido = ?,
                       logradouro = ?, numero = ?, bairro = ?, cidade = ?,
                       uf = ?, cep = ?, complemento = ?, referencia = ?,
                       latitude = ?, longitude = ?, principal = ?
                       WHERE id = ?""",
                    (*dados, endereco.id),
                )
            guardados.append(endereco.id)

        if guardados:
            marcas = ", ".join("?" * len(guardados))
            self.conexao.execute(
                f"""DELETE FROM endereco
                    WHERE empresa_id = ? AND id NOT IN ({marcas})""",
                (empresa.id, *guardados),
            )
        else:
            self.conexao.execute(
                "DELETE FROM endereco WHERE empresa_id = ?", (empresa.id,)
            )

    def salvar_enderecos(self, empresa: EmpresaCompradora) -> EmpresaCompradora:
        """Grava só os endereços, pra tela de cadastro não reescrever a empresa."""
        if empresa.id is None:
            raise ValueError("A compradora precisa estar gravada.")
        self._gravar_enderecos(empresa)
        self.conexao.commit()
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
        ficha = produto.rastreabilidade
        if ficha is None:
            self.conexao.execute(
                "DELETE FROM rastreabilidade WHERE produto_id = ?", (produto.id,)
            )
        else:
            self.conexao.execute(
                """INSERT INTO rastreabilidade
                   (produto_id, lote, data_coleta, local_coleta, responsavel,
                    metodo, latitude, longitude, observacoes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(produto_id) DO UPDATE SET
                     lote = excluded.lote,
                     data_coleta = excluded.data_coleta,
                     local_coleta = excluded.local_coleta,
                     responsavel = excluded.responsavel,
                     metodo = excluded.metodo,
                     latitude = excluded.latitude,
                     longitude = excluded.longitude,
                     observacoes = excluded.observacoes""",
                (
                    produto.id,
                    ficha.lote,
                    ficha.data_coleta.isoformat(),
                    ficha.local_coleta,
                    ficha.responsavel,
                    ficha.metodo.value,
                    ficha.coordenada.latitude if ficha.coordenada else None,
                    ficha.coordenada.longitude if ficha.coordenada else None,
                    ficha.observacoes,
                ),
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
            pedido.forma_pagamento.value,
            pedido.status_pagamento.value,
            pedido.pago_em.isoformat(timespec="seconds") if pedido.pago_em else None,
            pedido.coordenada_entrega.latitude if pedido.coordenada_entrega else None,
            pedido.coordenada_entrega.longitude if pedido.coordenada_entrega else None,
            1 if pedido.prazo_confirmado else 0,
            (
                pedido.previsao_entrega.isoformat(timespec="seconds")
                if pedido.previsao_entrega
                else None
            ),
            *_colunas_entrega(pedido.endereco),
        )
        if pedido.id is None:
            cursor = self.conexao.execute(
                """INSERT INTO pedido
                   (compradora_id, marisqueira_id, status, status_entrega,
                    endereco_entrega, tempo_entrega_dias, criado_em,
                    motivo_rejeicao, observacao_ajuste, forma_pagamento,
                    status_pagamento, pago_em, entrega_latitude,
                    entrega_longitude, prazo_confirmado, previsao_entrega,
                    entrega_apelido, entrega_logradouro, entrega_numero,
                    entrega_bairro, entrega_cidade, entrega_uf, entrega_cep,
                    entrega_complemento, entrega_referencia)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                dados,
            )
            pedido.id = cursor.lastrowid
        else:
            self.conexao.execute(
                """UPDATE pedido SET compradora_id = ?, marisqueira_id = ?,
                   status = ?, status_entrega = ?, endereco_entrega = ?,
                   tempo_entrega_dias = ?, criado_em = ?, motivo_rejeicao = ?,
                   observacao_ajuste = ?, forma_pagamento = ?,
                   status_pagamento = ?, pago_em = ?, entrega_latitude = ?,
                   entrega_longitude = ?, prazo_confirmado = ?,
                   previsao_entrega = ?, entrega_apelido = ?,
                   entrega_logradouro = ?, entrega_numero = ?,
                   entrega_bairro = ?, entrega_cidade = ?, entrega_uf = ?,
                   entrega_cep = ?, entrega_complemento = ?,
                   entrega_referencia = ? WHERE id = ?""",
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
                   (pedido_id, produto_id, quantidade_kg, preco_unitario,
                    origem_lote, origem_data_coleta, origem_local,
                    origem_responsavel, origem_metodo, origem_latitude,
                    origem_longitude, origem_observacoes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pedido.id,
                    item.produto.id,
                    str(item.quantidade_kg),
                    str(item.preco_unitario),  # RN07: preço histórico
                    *_colunas_origem(item.origem),
                ),
            )
            item.id = cursor.lastrowid

        # Trajeto: append-only, então só grava o que ainda não tem id.
        for evento in pedido.eventos_entrega:
            if evento.id is not None:
                continue
            cursor = self.conexao.execute(
                """INSERT INTO evento_entrega
                   (pedido_id, latitude, longitude, descricao, registrado_em)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    pedido.id,
                    evento.coordenada.latitude,
                    evento.coordenada.longitude,
                    evento.descricao,
                    evento.registrado_em.isoformat(timespec="seconds"),
                ),
            )
            evento.id = cursor.lastrowid

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

    def recarregar_trajeto(self, pedido) -> int:
        """Relê do banco as posições que o outro perfil gravou.

        Os dois perfis rodam no mesmo processo, mas cada painel tem sua cópia
        do grafo só enquanto está aberto. Durante a simulação é o painel da
        marisqueira que grava; o da compradora chama isto para ver o que
        chegou, em vez de recarregar o banco inteiro.
        """
        from dominio.coordenada import Coordenada
        from dominio.entrega import EventoEntrega

        ja_tenho = {e.id for e in pedido.eventos_entrega if e.id is not None}
        novos = 0
        for linha in self.conexao.execute(
            "SELECT * FROM evento_entrega WHERE pedido_id = ? ORDER BY id",
            (pedido.id,),
        ):
            if linha["id"] in ja_tenho:
                continue
            pedido.eventos_entrega.append(
                EventoEntrega(
                    pedido=pedido,
                    coordenada=Coordenada(
                        float(linha["latitude"]), float(linha["longitude"])
                    ),
                    descricao=linha["descricao"],
                    registrado_em=datetime.fromisoformat(linha["registrado_em"]),
                    id=linha["id"],
                )
            )
            novos += 1
        return novos

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
