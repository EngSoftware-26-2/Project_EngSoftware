-- Esquema relacional do sistema de gestão de requisitos.
-- Este arquivo cria o esquema do domínio e a tabela de usuários utilizada
-- pelas relações de dono e membro. Para uma instalação completa do Django,
-- prefira executar: python manage.py migrate

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Usuários do Django Auth. A senha deve ser armazenada como hash.
CREATE TABLE auth_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    password VARCHAR(128) NOT NULL,
    last_login DATETIME NULL,
    is_superuser BOOLEAN NOT NULL,
    username VARCHAR(150) NOT NULL UNIQUE,
    last_name VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL,
    is_staff BOOLEAN NOT NULL,
    is_active BOOLEAN NOT NULL,
    date_joined DATETIME NOT NULL,
    first_name VARCHAR(150) NOT NULL
);

-- Projeto: possui um dono e pode possuir vários membros.
CREATE TABLE core_projeto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(200) NOT NULL,
    descricao TEXT NOT NULL,
    criado_em DATETIME NOT NULL,
    dono_id INTEGER NOT NULL,
    FOREIGN KEY (dono_id) REFERENCES auth_user (id) ON DELETE RESTRICT
);

-- Product Backlog: no máximo um por projeto.
CREATE TABLE core_productbacklog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id INTEGER NOT NULL UNIQUE,
    descricao TEXT NOT NULL,
    FOREIGN KEY (projeto_id) REFERENCES core_projeto (id) ON DELETE CASCADE
);

-- Sprint Backlog: vários podem pertencer ao mesmo projeto.
CREATE TABLE core_sprintbacklog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(100) NOT NULL,
    projeto_id INTEGER NOT NULL,
    data_inicio DATE NOT NULL,
    data_fim DATE NOT NULL,
    FOREIGN KEY (projeto_id) REFERENCES core_projeto (id) ON DELETE CASCADE,
    CONSTRAINT sprint_periodo_valido CHECK (data_fim >= data_inicio)
);

-- Épico: pertence a um projeto e pode agrupar várias histórias.
CREATE TABLE core_epico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo VARCHAR(200) NOT NULL,
    projeto_id INTEGER NOT NULL,
    descricao TEXT NOT NULL,
    FOREIGN KEY (projeto_id) REFERENCES core_projeto (id) ON DELETE CASCADE
);

-- História de usuário: pode estar no Product Backlog ou em um Sprint Backlog,
-- mas não nos dois simultaneamente.
CREATE TABLE core_historiausuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo VARCHAR(200) NOT NULL,
    papel VARCHAR(100) NOT NULL,
    acao VARCHAR(255) NOT NULL,
    beneficio VARCHAR(255) NOT NULL,

    -- Campos legados mantidos durante a transição para CriterioAceitacao.
    contexto TEXT NOT NULL,
    evento VARCHAR(255) NOT NULL,
    resultado TEXT NOT NULL,

    story_points INTEGER NULL,
    moscow VARCHAR(1) NOT NULL,
    reach INTEGER NULL CHECK (reach >= 0),
    impact REAL NULL,
    confidence INTEGER NULL,
    effort INTEGER NULL,

    epico_id INTEGER NULL,
    product_backlog_id INTEGER NULL,
    sprint_backlog_id INTEGER NULL,

    FOREIGN KEY (epico_id) REFERENCES core_epico (id) ON DELETE SET NULL,
    FOREIGN KEY (product_backlog_id) REFERENCES core_productbacklog (id) ON DELETE CASCADE,
    FOREIGN KEY (sprint_backlog_id) REFERENCES core_sprintbacklog (id) ON DELETE SET NULL,

    CONSTRAINT historia_apenas_um_backlog CHECK (
        product_backlog_id IS NULL OR sprint_backlog_id IS NULL
    ),
    CONSTRAINT historia_story_points_fibonacci CHECK (
        story_points IS NULL OR story_points IN (0, 1, 2, 3, 5, 8, 13, 21, 34, 55)
    ),
    CONSTRAINT historia_moscow_valido CHECK (
        moscow IN ('', 'M', 'S', 'C', 'W')
    ),
    CONSTRAINT historia_impact_valido CHECK (
        impact IS NULL OR impact IN (3.0, 2.0, 1.0, 0.5, 0.25)
    ),
    CONSTRAINT historia_confidence_valido CHECK (
        confidence IS NULL OR confidence IN (100, 80, 50)
    ),
    CONSTRAINT historia_effort_fibonacci CHECK (
        effort IS NULL OR effort IN (0, 1, 2, 3, 5, 8, 13, 21, 34, 55)
    )
);

-- Critério de aceitação: uma história pode possuir vários critérios.
CREATE TABLE core_criterioaceitacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dado TEXT NOT NULL,
    quando VARCHAR(255) NOT NULL,
    entao TEXT NOT NULL,
    historia_usuario_id INTEGER NOT NULL,
    FOREIGN KEY (historia_usuario_id)
        REFERENCES core_historiausuario (id)
        ON DELETE CASCADE
);

-- Tabela intermediária do relacionamento N:N entre projetos e usuários.
CREATE TABLE core_projeto_membros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (projeto_id) REFERENCES core_projeto (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE CASCADE,
    CONSTRAINT projeto_membro_unico UNIQUE (projeto_id, user_id)
);

-- Índices para as chaves estrangeiras e consultas frequentes.
CREATE INDEX core_projeto_dono_id_idx
    ON core_projeto (dono_id);
CREATE INDEX core_sprintbacklog_projeto_id_idx
    ON core_sprintbacklog (projeto_id);
CREATE INDEX core_epico_projeto_id_idx
    ON core_epico (projeto_id);
CREATE INDEX core_historiausuario_epico_id_idx
    ON core_historiausuario (epico_id);
CREATE INDEX core_historiausuario_product_backlog_id_idx
    ON core_historiausuario (product_backlog_id);
CREATE INDEX core_historiausuario_sprint_backlog_id_idx
    ON core_historiausuario (sprint_backlog_id);
CREATE INDEX core_criterioaceitacao_historia_id_idx
    ON core_criterioaceitacao (historia_usuario_id);
CREATE INDEX core_projeto_membros_projeto_id_idx
    ON core_projeto_membros (projeto_id);
CREATE INDEX core_projeto_membros_user_id_idx
    ON core_projeto_membros (user_id);

-- Uma história nova deve possuir um backlog. Histórias legadas sem backlog
-- podem ser mantidas, mas não podem ser desvinculadas do último backlog.
CREATE TRIGGER historia_vinculos_insert
BEFORE INSERT ON core_historiausuario
FOR EACH ROW
WHEN
    (NEW.product_backlog_id IS NULL AND NEW.sprint_backlog_id IS NULL)
    OR (
        NEW.epico_id IS NOT NULL AND (
            (
                NEW.product_backlog_id IS NOT NULL
                AND (SELECT projeto_id FROM core_epico WHERE id = NEW.epico_id)
                    != (SELECT projeto_id FROM core_productbacklog WHERE id = NEW.product_backlog_id)
            )
            OR (
                NEW.sprint_backlog_id IS NOT NULL
                AND (SELECT projeto_id FROM core_epico WHERE id = NEW.epico_id)
                    != (SELECT projeto_id FROM core_sprintbacklog WHERE id = NEW.sprint_backlog_id)
            )
        )
    )
BEGIN
    SELECT RAISE(ABORT, 'Historia sem backlog ou com vinculos entre projetos diferentes');
END;

CREATE TRIGGER historia_vinculos_update
BEFORE UPDATE ON core_historiausuario
FOR EACH ROW
WHEN
    (
        NEW.product_backlog_id IS NULL
        AND NEW.sprint_backlog_id IS NULL
        AND (OLD.product_backlog_id IS NOT NULL OR OLD.sprint_backlog_id IS NOT NULL)
    )
    OR (
        NEW.epico_id IS NOT NULL AND (
            (
                NEW.product_backlog_id IS NOT NULL
                AND (SELECT projeto_id FROM core_epico WHERE id = NEW.epico_id)
                    != (SELECT projeto_id FROM core_productbacklog WHERE id = NEW.product_backlog_id)
            )
            OR (
                NEW.sprint_backlog_id IS NOT NULL
                AND (SELECT projeto_id FROM core_epico WHERE id = NEW.epico_id)
                    != (SELECT projeto_id FROM core_sprintbacklog WHERE id = NEW.sprint_backlog_id)
            )
        )
    )
BEGIN
    SELECT RAISE(ABORT, 'Historia sem backlog ou com vinculos entre projetos diferentes');
END;

CREATE TRIGGER productbacklog_projeto_consistente
BEFORE UPDATE OF projeto_id ON core_productbacklog
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM core_historiausuario h
    JOIN core_epico e ON e.id = h.epico_id
    WHERE h.product_backlog_id = OLD.id
      AND e.projeto_id != NEW.projeto_id
)
BEGIN
    SELECT RAISE(ABORT, 'Backlog e epico devem pertencer ao mesmo projeto');
END;

CREATE TRIGGER sprintbacklog_projeto_consistente
BEFORE UPDATE OF projeto_id ON core_sprintbacklog
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM core_historiausuario h
    JOIN core_epico e ON e.id = h.epico_id
    WHERE h.sprint_backlog_id = OLD.id
      AND e.projeto_id != NEW.projeto_id
)
BEGIN
    SELECT RAISE(ABORT, 'Backlog e epico devem pertencer ao mesmo projeto');
END;

CREATE TRIGGER epico_projeto_consistente
BEFORE UPDATE OF projeto_id ON core_epico
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM core_historiausuario h
    LEFT JOIN core_productbacklog p ON p.id = h.product_backlog_id
    LEFT JOIN core_sprintbacklog s ON s.id = h.sprint_backlog_id
    WHERE h.epico_id = OLD.id
      AND (p.projeto_id != NEW.projeto_id OR s.projeto_id != NEW.projeto_id)
)
BEGIN
    SELECT RAISE(ABORT, 'Epico e backlog devem pertencer ao mesmo projeto');
END;

COMMIT;
