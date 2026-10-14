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
    fechamento   TEXT NOT NULL
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
    observacao_ajuste   TEXT
);

CREATE TABLE IF NOT EXISTS item_pedido (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id       INTEGER NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
    produto_id      INTEGER NOT NULL REFERENCES produto(id),
    quantidade_kg   TEXT NOT NULL,                  -- RN15: mínimo 25 por item
    -- RN07: cópia do preço no momento da compra. Se fosse um JOIN com
    -- produto.preco_por_kg, reajustar o preço reescreveria o histórico.
    preco_unitario  TEXT NOT NULL
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

CREATE INDEX IF NOT EXISTS idx_notificacao_destinatario
    ON notificacao(destinatario_id, lida);
CREATE INDEX IF NOT EXISTS idx_produto_empresa ON produto(empresa_id);
CREATE INDEX IF NOT EXISTS idx_pedido_marisqueira ON pedido(marisqueira_id);
CREATE INDEX IF NOT EXISTS idx_pedido_compradora ON pedido(compradora_id);
CREATE INDEX IF NOT EXISTS idx_item_pedido ON item_pedido(pedido_id);
