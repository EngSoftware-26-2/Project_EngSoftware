# Situação e responsável da história (quadro Kanban do Sprint).
# Muda a tabela core_historiausuario:
#  - situacao: texto, "a_fazer" (padrão), "em_desenvolvimento" ou "concluida";
#  - responsavel_id: chave para auth_user, opcional (SET NULL se o usuário for apagado).
# As histórias que já existem ficam "A fazer" e sem responsável.
import importlib

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


_m0005 = importlib.import_module("core.migrations.0005_integridade_vinculos_historias")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_criterioaceitacao_periodo_sprint"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # O SQLite reconstrói a tabela ao adicionar campos e restrições. Os gatilhos da 0005
        # são removidos antes e recriados no final, como na 0006 e na 0007.
        migrations.RunPython(_m0005.remover, _m0005.instalar),
        migrations.AddField(
            model_name="historiausuario",
            name="responsavel",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="historias_responsavel",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Responsável",
            ),
        ),
        migrations.AddField(
            model_name="historiausuario",
            name="situacao",
            field=models.CharField(
                choices=[
                    ("a_fazer", "A fazer"),
                    ("em_desenvolvimento", "Em desenvolvimento"),
                    ("concluida", "Concluída"),
                ],
                default="a_fazer",
                max_length=20,
                verbose_name="Situação",
            ),
        ),
        migrations.AddConstraint(
            model_name="historiausuario",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("situacao__in", ["a_fazer", "em_desenvolvimento", "concluida"])
                ),
                name="historia_situacao_valida",
            ),
        ),
        migrations.RunPython(_m0005.instalar, _m0005.remover),
    ]
