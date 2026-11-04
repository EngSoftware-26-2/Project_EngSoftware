"""Proteção SQLite para bulk_create/update e alterações do projeto dos vínculos.

CHECK não pode consultar outras tabelas. Os gatilhos complementam clean/save.
Não reatribui nem exclui histórias legadas sem backlog.
"""
from django.db import migrations


def instalar(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        raise RuntimeError("Esta proteção de vínculos requer SQLite, o banco configurado no projeto.")
    for evento in ("INSERT", "UPDATE"):
        # Permite manter um registro legado sem backlog; proíbe criar novos ou
        # desvincular o último backlog de uma história anteriormente vinculada.
        sem_backlog = "NEW.product_backlog_id IS NULL AND NEW.sprint_backlog_id IS NULL"
        if evento == "UPDATE":
            sem_backlog += " AND (OLD.product_backlog_id IS NOT NULL OR OLD.sprint_backlog_id IS NOT NULL)"
        schema_editor.execute(f"""
            CREATE TRIGGER historia_vinculos_{evento.lower()}
            BEFORE {evento} ON core_historiausuario
            FOR EACH ROW WHEN
                ({sem_backlog}) OR
                (NEW.epico_id IS NOT NULL AND (
                    (NEW.product_backlog_id IS NOT NULL AND
                        (SELECT projeto_id FROM core_epico WHERE id=NEW.epico_id) !=
                        (SELECT projeto_id FROM core_productbacklog WHERE id=NEW.product_backlog_id)) OR
                    (NEW.sprint_backlog_id IS NOT NULL AND
                        (SELECT projeto_id FROM core_epico WHERE id=NEW.epico_id) !=
                        (SELECT projeto_id FROM core_sprintbacklog WHERE id=NEW.sprint_backlog_id))
                ))
            BEGIN
                SELECT RAISE(ABORT, 'Historia sem backlog ou com vinculos entre projetos diferentes');
            END
        """)
    for tabela, campo, condicao in (
        ("productbacklog", "product_backlog_id", "e.projeto_id != NEW.projeto_id"),
        ("sprintbacklog", "sprint_backlog_id", "e.projeto_id != NEW.projeto_id"),
    ):
        schema_editor.execute(f"""
            CREATE TRIGGER {tabela}_projeto_consistente
            BEFORE UPDATE OF projeto_id ON core_{tabela}
            FOR EACH ROW WHEN EXISTS (
                SELECT 1 FROM core_historiausuario h
                JOIN core_epico e ON e.id=h.epico_id
                WHERE h.{campo}=OLD.id AND {condicao}
            )
            BEGIN
                SELECT RAISE(ABORT, 'Backlog e epico devem pertencer ao mesmo projeto');
            END
        """)
    schema_editor.execute("""
        CREATE TRIGGER epico_projeto_consistente
        BEFORE UPDATE OF projeto_id ON core_epico
        FOR EACH ROW WHEN EXISTS (
            SELECT 1 FROM core_historiausuario h
            LEFT JOIN core_productbacklog p ON p.id=h.product_backlog_id
            LEFT JOIN core_sprintbacklog s ON s.id=h.sprint_backlog_id
            WHERE h.epico_id=OLD.id AND (
                p.projeto_id != NEW.projeto_id OR s.projeto_id != NEW.projeto_id
            )
        )
        BEGIN
            SELECT RAISE(ABORT, 'Epico e backlog devem pertencer ao mesmo projeto');
        END
    """)


def remover(apps, schema_editor):
    for nome in (
        "historia_vinculos_insert", "historia_vinculos_update",
        "productbacklog_projeto_consistente", "sprintbacklog_projeto_consistente",
        "epico_projeto_consistente",
    ):
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {nome}")


class Migration(migrations.Migration):
    dependencies = [("core", "0004_historiausuario_historia_apenas_um_backlog")]
    operations = [migrations.RunPython(instalar, remover)]
