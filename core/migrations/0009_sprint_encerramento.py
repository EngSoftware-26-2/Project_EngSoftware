# Encerramento e cancelamento do Sprint.
# Muda a tabela core_sprintbacklog:
#  - encerrado_em: data em que o Sprint foi encerrado ou cancelado (opcional);
#  - encerrado_por_id: quem encerrou ou cancelou, ligada a auth_user (opcional; vazia quando
#    o sistema encerra sozinho ao passar a data de fim);
#  - cancelado: verdadeiro/falso, padrão falso;
#  - motivo_cancelamento: texto opcional.
# Cria a tabela core_historiadevolvida: as histórias que voltaram para o Product Backlog
# quando o Sprint foi fechado (título, Story Points e situação no dia).
import importlib

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


_m0005 = importlib.import_module("core.migrations.0005_integridade_vinculos_historias")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_historia_situacao_responsavel"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Gatilhos da 0005 removidos e recriados em volta das alterações, como na 0006 a 0008.
        migrations.RunPython(_m0005.remover, _m0005.instalar),
        migrations.CreateModel(
            name="HistoriaDevolvida",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("titulo", models.CharField(max_length=200, verbose_name="Título")),
                (
                    "story_points",
                    models.IntegerField(
                        blank=True, null=True, verbose_name="Story Points"
                    ),
                ),
                (
                    "situacao",
                    models.CharField(
                        choices=[
                            ("a_fazer", "A fazer"),
                            ("em_desenvolvimento", "Em desenvolvimento"),
                            ("concluida", "Concluída"),
                        ],
                        max_length=20,
                        verbose_name="Situação no encerramento",
                    ),
                ),
            ],
            options={
                "ordering": ["titulo"],
            },
        ),
        migrations.AddField(
            model_name="sprintbacklog",
            name="cancelado",
            field=models.BooleanField(default=False, verbose_name="Cancelado"),
        ),
        migrations.AddField(
            model_name="sprintbacklog",
            name="encerrado_em",
            field=models.DateField(blank=True, null=True, verbose_name="Encerrado em"),
        ),
        migrations.AddField(
            model_name="sprintbacklog",
            name="encerrado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sprints_encerrados",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Encerrado por",
            ),
        ),
        migrations.AddField(
            model_name="sprintbacklog",
            name="motivo_cancelamento",
            field=models.TextField(blank=True, verbose_name="Motivo"),
        ),
        migrations.AddConstraint(
            model_name="sprintbacklog",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("cancelado", False),
                    ("encerrado_em__isnull", False),
                    _connector="OR",
                ),
                name="sprint_cancelado_com_data",
            ),
        ),
        migrations.AddField(
            model_name="historiadevolvida",
            name="historia",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="devolucoes",
                to="core.historiausuario",
            ),
        ),
        migrations.AddField(
            model_name="historiadevolvida",
            name="sprint",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="historias_devolvidas",
                to="core.sprintbacklog",
            ),
        ),
        migrations.RunPython(_m0005.instalar, _m0005.remover),
    ]
