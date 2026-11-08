from django.db import migrations, models
import django.db.models.deletion
import importlib


_m0005 = importlib.import_module("core.migrations.0005_integridade_vinculos_historias")


def migrar_criterios_legados(apps, schema_editor):
    HistoriaUsuario = apps.get_model("core", "HistoriaUsuario")
    CriterioAceitacao = apps.get_model("core", "CriterioAceitacao")

    for historia in HistoriaUsuario.objects.using(schema_editor.connection.alias).all():
        valores = (historia.contexto, historia.evento, historia.resultado)
        preenchidos = tuple(valor not in (None, "") for valor in valores)

        if not any(preenchidos):
            continue

        if not all(preenchidos):
            raise RuntimeError(
                "Existe uma história com critério de aceitação legado incompleto. "
                "Preencha Dado, Quando e Então antes de aplicar esta migração."
            )

        CriterioAceitacao.objects.using(schema_editor.connection.alias).create(
            historia_usuario_id=historia.pk,
            dado=historia.contexto,
            quando=historia.evento,
            entao=historia.resultado,
        )


def validar_periodos_legados(apps, schema_editor):
    SprintBacklog = apps.get_model("core", "SprintBacklog")
    sem_periodo = SprintBacklog.objects.using(schema_editor.connection.alias).filter(
        models.Q(data_inicio__isnull=True) | models.Q(data_fim__isnull=True)
    )
    if sem_periodo.exists():
        raise RuntimeError(
            "Existem Sprint Backlogs sem período. "
            "Preencha data_inicio e data_fim antes de aplicar esta migração."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_historia_rice_epico"),
    ]

    operations = [
        # O SQLite reconstrói a tabela ao tornar as datas obrigatórias. Os
        # gatilhos da 0005 precisam ser removidos durante essa reconstrução.
        migrations.RunPython(_m0005.remover, _m0005.instalar),
        migrations.CreateModel(
            name="CriterioAceitacao",
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
                ("dado", models.TextField(verbose_name="Dado")),
                ("quando", models.CharField(max_length=255, verbose_name="Quando")),
                ("entao", models.TextField(verbose_name="Então")),
                (
                    "historia_usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="criterios_aceitacao",
                        to="core.historiausuario",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddField(
            model_name="sprintbacklog",
            name="data_inicio",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Data de início",
            ),
        ),
        migrations.AddField(
            model_name="sprintbacklog",
            name="data_fim",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Data de fim",
            ),
        ),
        migrations.RunPython(validar_periodos_legados, migrations.RunPython.noop),
        migrations.RunPython(migrar_criterios_legados, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sprintbacklog",
            name="data_inicio",
            field=models.DateField(verbose_name="Data de início"),
        ),
        migrations.AlterField(
            model_name="sprintbacklog",
            name="data_fim",
            field=models.DateField(verbose_name="Data de fim"),
        ),
        migrations.AddConstraint(
            model_name="sprintbacklog",
            constraint=models.CheckConstraint(
                condition=models.Q(data_fim__gte=models.F("data_inicio")),
                name="sprint_periodo_valido",
            ),
        ),
        migrations.RunPython(_m0005.instalar, _m0005.remover),
    ]
