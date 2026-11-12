"""Protege exclusões pela aplicação e pelo admin, inclusive QuerySet.delete()."""
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.db.models.signals import m2m_changed, pre_delete
from django.dispatch import receiver

from .models import HistoriaUsuario, ProductBacklog, Projeto, SprintBacklog


def historias_do_projeto(projeto_id, using="default"):
    return HistoriaUsuario.objects.using(using).filter(
        Q(product_backlog__projeto_id=projeto_id) |
        Q(sprint_backlog__projeto_id=projeto_id) |
        Q(epico__projeto_id=projeto_id)
    )


# HU08 - O Product Backlog só pode ser excluído quando o projeto não tem nenhuma história,
# nem mesmo em Sprint Backlogs (evita apagar histórias sem querer). Ao excluir o projeto
# inteiro (HU07), a regra não se aplica.
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


# HU10 - Ao excluir um Sprint Backlog, suas histórias retornam ao Product Backlog.
# Ao excluir o projeto inteiro, a cascata do projeto continua sendo aplicada.
@receiver(pre_delete, sender=SprintBacklog)
def devolver_historias_ao_product_backlog(sender, instance, using, origin, **kwargs):
    if isinstance(origin, Projeto) or getattr(origin, "model", None) is Projeto:
        return
    backlog = ProductBacklog.objects.using(using).filter(
        projeto_id=instance.projeto_id,
    ).first()
    historias = HistoriaUsuario.objects.using(using).filter(sprint_backlog=instance)
    if historias.exists() and backlog is None:
        raise ProtectedError(
            "Não é possível excluir a Sprint porque o projeto não possui Product Backlog.",
            historias,
        )
    if backlog is not None:
        historias.update(product_backlog_id=backlog.pk, sprint_backlog_id=None,
                         situacao=HistoriaUsuario.SITUACAO_A_FAZER)


# HU07 - Ao excluir o projeto, apaga também as histórias que estão só em Sprint Backlogs
# ou épicos, que o CASCADE do Django não alcançaria.
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


# Responsável (passo da situação/responsável): quando alguém deixa de ser membro do projeto
# (removido pelo dono ou saiu sozinho), as histórias daquele projeto que estavam com essa
# pessoa ficam "Sem responsável". As histórias em si não mudam.
@receiver(m2m_changed, sender=Projeto.membros.through)
def limpar_responsavel_ao_sair(sender, instance, action, reverse, pk_set, using, **kwargs):
    if action != "post_remove" or reverse or not pk_set:
        return
    historias_do_projeto(instance.pk, using).filter(
        responsavel_id__in=pk_set,
    ).exclude(responsavel_id=instance.dono_id).update(responsavel=None)
