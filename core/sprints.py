# Regras do Sprint: encerrar, cancelar e encerrar sozinho quando passa a data de fim.
#
# Em todos os casos, as histórias que não foram concluídas voltam para o Product Backlog
# (como no Scrum: o Product Owner prioriza de novo e elas podem entrar no próximo Sprint).
# Antes de devolver, o sistema guarda como cada uma estava (HistoriaDevolvida), para o
# histórico do Sprint mostrar o que ficou para depois. As concluídas ficam no Sprint.
from django.db import transaction
from django.utils import timezone

from .models import HistoriaDevolvida, HistoriaUsuario, ProductBacklog, SprintBacklog


class SemProductBacklog(Exception):
    """O projeto não tem Product Backlog para receber as histórias não concluídas."""


def historias_nao_concluidas(sprint):
    return sprint.historias.exclude(situacao=HistoriaUsuario.SITUACAO_CONCLUIDA).order_by("titulo")


@transaction.atomic
def fechar_sprint(sprint, usuario=None, data=None, cancelar=False, motivo=""):
    data = data or timezone.localdate()
    pendentes = list(historias_nao_concluidas(sprint))
    backlog = ProductBacklog.objects.filter(projeto_id=sprint.projeto_id).first()
    if pendentes and backlog is None:
        raise SemProductBacklog(
            "O projeto não tem Product Backlog para receber as histórias não concluídas. "
            "Crie o Product Backlog antes de encerrar ou cancelar o Sprint."
        )
    for historia in pendentes:
        HistoriaDevolvida.objects.create(
            sprint=sprint, historia=historia, titulo=historia.titulo,
            story_points=historia.story_points, situacao=historia.situacao,
        )
        historia.sprint_backlog = None
        historia.product_backlog = backlog
        historia.save()  # o save() da história já volta a situação para "A fazer"
    sprint.encerrado_em = data
    sprint.encerrado_por = usuario
    sprint.cancelado = cancelar
    sprint.motivo_cancelamento = motivo.strip() if cancelar else ""
    sprint.save()
    return pendentes


def encerrar_sprints_vencidos(projeto):
    # Sprint cuja data de fim já passou e que ninguém encerrou: o sistema encerra na data de
    # fim prevista. Roda quando alguém abre as telas do projeto (não precisa de agendador).
    hoje = timezone.localdate()
    vencidos = SprintBacklog.objects.filter(
        projeto=projeto, cancelado=False, encerrado_em__isnull=True, data_fim__lt=hoje,
    )
    for sprint in vencidos:
        try:
            fechar_sprint(sprint, usuario=None, data=sprint.data_fim)
        except SemProductBacklog:
            # Sem Product Backlog as histórias não têm para onde voltar; o Sprint aparece como
            # concluído pela data e as histórias ficam nele até o backlog ser criado.
            continue


def sprint_em_conflito(projeto, inicio, fim, ignorar_pk=None):
    # Um Sprint por vez no projeto. Sprints cancelados não contam, e um Sprint encerrado
    # antes do previsto só ocupa os dias até o encerramento.
    candidatos = SprintBacklog.objects.filter(projeto=projeto, cancelado=False, data_inicio__lte=fim)
    if ignorar_pk:
        candidatos = candidatos.exclude(pk=ignorar_pk)
    for sprint in candidatos.order_by("data_inicio"):
        if sprint.fim_efetivo >= inicio:
            return sprint
    return None
