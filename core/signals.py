"""Protege exclusões pela aplicação e pelo admin, inclusive QuerySet.delete()."""
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import HistoriaUsuario, ProductBacklog, Projeto, SprintBacklog


def historias_do_projeto(projeto_id, using="default"):
    return HistoriaUsuario.objects.using(using).filter(
        Q(product_backlog__projeto_id=projeto_id) |
        Q(sprint_backlog__projeto_id=projeto_id) |
        Q(epico__projeto_id=projeto_id)
    )


@receiver(pre_delete, sender=ProductBacklog)
def proteger_product_backlog(sender, instance, using, origin, **kwargs):
    # A exclusão completa do projeto deve continuar removendo seus dependentes.
    if isinstance(origin, Projeto) or getattr(origin, "model", None) is Projeto:
        return
    historias = historias_do_projeto(instance.projeto_id, using)
    if historias.exists():
        raise ProtectedError(
            "Não é possível excluir o Product Backlog enquanto houver histórias "
            "no projeto, inclusive em Sprint Backlogs.",
            historias,
        )


@receiver(pre_delete, sender=SprintBacklog)
def proteger_historias_do_sprint(sender, instance, using, origin, **kwargs):
    if isinstance(origin, Projeto) or getattr(origin, "model", None) is Projeto:
        return
    historias = instance.historias.using(using).all()
    if historias.exists():
        raise ProtectedError(
            "Mova as histórias para outro backlog antes de excluir este Sprint Backlog.",
            historias,
        )


@receiver(pre_delete, sender=Projeto)
def excluir_historias_do_projeto(sender, instance, using, **kwargs):
    historias = historias_do_projeto(instance.pk, using)
    # Não remova dados compartilhados por vínculos legados inconsistentes.
    conflitos = historias.filter(
        (Q(product_backlog__isnull=False) & ~Q(product_backlog__projeto_id=instance.pk)) |
        (Q(sprint_backlog__isnull=False) & ~Q(sprint_backlog__projeto_id=instance.pk)) |
        (Q(epico__isnull=False) & ~Q(epico__projeto_id=instance.pk))
    )
    if conflitos.exists():
        raise ProtectedError("Há histórias com vínculos entre projetos diferentes.", conflitos)
    # Histórias do Product Backlog já fazem parte da cascata do coletor Django.
    # As demais sobreviveriam por causa de SET_NULL nos Sprints e épicos.
    historias.filter(product_backlog__isnull=True).delete()
