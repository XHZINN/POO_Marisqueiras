-- Esquema do banco Marisqueiras da Ilha (SQLite).
--
-- DECISÃO: valores monetários e de peso são gravados como TEXT, não REAL.
-- REAL é ponto flutuante e perde precisão (0.1 + 0.2 = 0.30000000000000004).
-- Gravando o Decimal como texto, o valor volta do banco exatamente igual.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS empresa (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Discriminador da herança: diz qual subclasse reconstruir ao carregar.
    tipo         TEXT NOT NULL CHECK (tipo IN ('marisqueira', 'compradora')),
    nome         TEXT NOT NULL,
    cnpj         TEXT NOT NULL UNIQUE,              -- RN02: 1 habitação = 1 empresa
    email        TEXT NOT NULL,
    telefone     TEXT NOT NULL,
    endereco     TEXT NOT NULL,
    localizacao  TEXT NOT NULL,                     -- P21: filtro de busca
    abertura     TEXT NOT NULL,                     -- "HH:MM" (RN20)
    fechamento   TEXT NOT NULL,
    -- Posição real. Extensão além de P10.
    latitude     REAL,
    longitude    REAL,
    -- Condições de entrega da marisqueira: quanto leva pra preparar e até
    -- onde entrega. Nulo na compradora, que não entrega nada.
    preparo_horas    INTEGER,
    raio_entrega_km  TEXT
);

-- Endereços de entrega salvos da compradora. Extensão: os requisitos tratam
-- o endereço como campo de texto do pedido (RN13), e aqui ele é cadastro.
CREATE TABLE IF NOT EXISTS endereco (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id   INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    apelido      TEXT NOT NULL,
    logradouro   TEXT NOT NULL,
    numero       TEXT NOT NULL,
    bairro       TEXT NOT NULL,
    cidade       TEXT NOT NULL,
    uf           TEXT NOT NULL,
    cep          TEXT,
    complemento  TEXT,
    referencia   TEXT,
    latitude     REAL,
    longitude    REAL,
    principal    INTEGER NOT NULL DEFAULT 0,
    -- O apelido é como a pessoa escolhe o endereço na hora da compra, então
    -- dois "Matriz" na mesma empresa não serve.
    UNIQUE (empresa_id, apelido)
);

CREATE TABLE IF NOT EXISTS produto (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id                INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    nome                      TEXT NOT NULL,
    categoria                 TEXT NOT NULL CHECK (categoria IN ('fresco', 'congelado')),
    preco_por_kg              TEXT NOT NULL,        -- RN04/RN07: Decimal como TEXT
    quantidade_disponivel_kg  TEXT NOT NULL,        -- RN08/RN09: pode ser "0"
    localizacao               TEXT NOT NULL,
    foto                      TEXT,                 -- P15: único campo opcional
    -- RN06: fresco e congelado são produtos diferentes, logo a unicidade é
    -- pelo trio (empresa, nome, categoria) e não pelo nome sozinho.
    UNIQUE (empresa_id, nome, categoria)
);

CREATE TABLE IF NOT EXISTS pedido (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    compradora_id       INTEGER NOT NULL REFERENCES empresa(id),
    -- RN14: a marisqueira é coluna do PEDIDO, não do item. É o banco
    -- reforçando que um pedido não reúne empresas diferentes.
    marisqueira_id      INTEGER NOT NULL REFERENCES empresa(id),
    status              TEXT NOT NULL,
    status_entrega      TEXT NOT NULL,              -- RN22
    endereco_entrega    TEXT NOT NULL,              -- RN13
    tempo_entrega_dias  INTEGER NOT NULL,           -- RN13
    criado_em           TEXT NOT NULL,
    motivo_rejeicao     TEXT,
    observacao_ajuste   TEXT,
    -- Pagamento. Extensão além de P27.
    forma_pagamento     TEXT NOT NULL DEFAULT 'pix',
    status_pagamento    TEXT NOT NULL DEFAULT 'pendente',
    pago_em             TEXT,
    -- Destino da entrega. Extensão além de P10.
    entrega_latitude    REAL,
    entrega_longitude   REAL,
    -- Cópia do endereço escolhido no momento da compra, mesma ideia de RN07
    -- com o preço: editar o cadastro amanhã não reescreve para onde este
    -- pedido foi. Nulo quando o endereço foi digitado como texto solto.
    entrega_apelido     TEXT,
    entrega_logradouro  TEXT,
    entrega_numero      TEXT,
    entrega_bairro      TEXT,
    entrega_cidade      TEXT,
    entrega_uf          TEXT,
    entrega_cep         TEXT,
    entrega_complemento TEXT,
    entrega_referencia  TEXT,
    -- Prazo: `tempo_entrega_dias` é estimativa até a marisqueira aceitar, e
    -- aí `prazo_confirmado` marca que virou compromisso.
    prazo_confirmado    INTEGER NOT NULL DEFAULT 0,
    previsao_entrega    TEXT
);

CREATE TABLE IF NOT EXISTS item_pedido (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id       INTEGER NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
    produto_id      INTEGER NOT NULL REFERENCES produto(id),
    quantidade_kg   TEXT NOT NULL,                  -- RN15: mínimo 25 por item
    -- RN07: cópia do preço no momento da compra. Se fosse um JOIN com
    -- produto.preco_por_kg, reajustar o preço reescreveria o histórico.
    preco_unitario  TEXT NOT NULL,
    -- Ficha de origem congelada na venda, mesma ideia de RN07 com o preço.
    -- Extensão além de P2.
    origem_lote          TEXT,
    origem_data_coleta   TEXT,
    origem_local         TEXT,
    origem_responsavel   TEXT,
    origem_metodo        TEXT,
    origem_latitude      REAL,
    origem_longitude     REAL,
    origem_observacoes   TEXT
);

CREATE TABLE IF NOT EXISTS avaliacao (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    -- UNIQUE: RN21: uma avaliação por compra.
    pedido_id   INTEGER NOT NULL UNIQUE REFERENCES pedido(id) ON DELETE CASCADE,
    nota        INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),   -- P24
    comentario  TEXT,
    criado_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notificacao (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    -- A notificação pertence a quem a recebe, por isso a chave é o
    -- destinatário e não o pedido.
    destinatario_id  INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    tipo             TEXT NOT NULL,
    mensagem         TEXT NOT NULL,
    pedido_id        INTEGER REFERENCES pedido(id) ON DELETE CASCADE,
    criado_em        TEXT NOT NULL,
    -- SQLite não tem BOOLEAN: 0 e 1 em INTEGER é a convenção.
    lida             INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS empresa_forma_pagamento (
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    forma       TEXT NOT NULL,
    PRIMARY KEY (empresa_id, forma)
);

-- Ficha do lote que está à venda agora. Extensão além de P2.
CREATE TABLE IF NOT EXISTS rastreabilidade (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    -- UNIQUE: um lote em venda por produto. Os anteriores ficam guardados
    -- nas colunas origem_* de item_pedido.
    produto_id    INTEGER NOT NULL UNIQUE REFERENCES produto(id) ON DELETE CASCADE,
    lote          TEXT NOT NULL,
    data_coleta   TEXT NOT NULL,
    local_coleta  TEXT NOT NULL,
    responsavel   TEXT NOT NULL,
    metodo        TEXT NOT NULL,
    latitude      REAL,
    longitude     REAL,
    observacoes   TEXT
);

-- Trajeto da entrega, append-only. Extensão além de P10.
CREATE TABLE IF NOT EXISTS evento_entrega (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id      INTEGER NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
    latitude       REAL NOT NULL,
    longitude      REAL NOT NULL,
    descricao      TEXT NOT NULL,
    registrado_em  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evento_pedido ON evento_entrega(pedido_id, id);
CREATE INDEX IF NOT EXISTS idx_notificacao_destinatario
    ON notificacao(destinatario_id, lida);
CREATE INDEX IF NOT EXISTS idx_produto_empresa ON produto(empresa_id);
CREATE INDEX IF NOT EXISTS idx_pedido_marisqueira ON pedido(marisqueira_id);
CREATE INDEX IF NOT EXISTS idx_pedido_compradora ON pedido(compradora_id);
CREATE INDEX IF NOT EXISTS idx_item_pedido ON item_pedido(pedido_id);
CREATE INDEX IF NOT EXISTS idx_endereco_empresa ON endereco(empresa_id);
