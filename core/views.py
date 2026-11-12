
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError

from .models import Projeto, ProductBacklog, Epico, HistoriaUsuario, CriterioAceitacao, SprintBacklog

from .forms import (
    CadastroForm, LoginForm, ProjetoForm, AdicionarMembroForm, ProductBacklogForm,
    EpicoForm, HistoriaUsuarioForm, CriterioAceitacaoForm, SprintBacklogForm,
    MoverHistoriaForm, CancelarSprintForm,
)
from django.utils import timezone
from .sprints import SemProductBacklog, encerrar_sprints_vencidos, fechar_sprint, historias_nao_concluidas

# HU01 - Cadastro
def cadastro(request):
    if request.user.is_authenticated:
        return redirect("inicio")

    form = CadastroForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        usuario = form.salvar()
        login(request, usuario)
        return redirect("inicio")

    return render(
        request,
        "core/cadastro.html",
        {"form": form}
    )


# HU02 - Login
def entrar(request):
    if request.user.is_authenticated:
        return redirect("inicio")

    form = LoginForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        senha = form.cleaned_data["senha"]

        contas = list(get_user_model().objects.filter(email__iexact=email)[:2])
        usuario = None
        if len(contas) == 1:
            usuario = authenticate(
                request, username=contas[0].get_username(), password=senha
            )

        if usuario is not None:
            login(request, usuario)
            return redirect("inicio")

        form.add_error(
            None,
            "E-mail ou senha inválidos."
        )

    return render(
        request,
        "core/login.html",
        {"form": form}
    )


# HU05 - Página inicial protegida: lista os projetos em que o usuário é dono ou membro

@login_required(login_url="login")
def inicio(request):

    projetos = Projeto.objects.filter(
        Q(dono=request.user) |
        Q(membros=request.user)
    ).distinct().order_by("-criado_em")

    return render(
        request,
        "core/inicio.html",
        {"projetos": projetos}
    )


# HU03 - Logout
@login_required(login_url="login")
@require_POST
def sair(request):
    logout(request)
    return redirect("login")


# HU04 - Criar projeto

@login_required(login_url="login")
def criar_projeto(request):

    form = ProjetoForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():

        with transaction.atomic():

            projeto = form.save(commit=False)

            # O usuário autenticado será o dono
            projeto.dono = request.user

            projeto.save()

            # Cria automaticamente o Product Backlog
            ProductBacklog.objects.create(
                projeto=projeto
            )

        return redirect("inicio")

    return render(
        request,
        "core/criar_projeto.html",
        {"form": form}
    )


# HU22 e HU23 - Gerenciar membros

@login_required(login_url="login")
def membros_projeto(request, pk):

    projeto = projeto_acessivel(request.user, pk)
    if request.method == "POST" and projeto.dono_id != request.user.pk:
        raise PermissionDenied

    form = AdicionarMembroForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():

        email = form.cleaned_data["email"]

        User = get_user_model()

        contas = list(User.objects.filter(
            email__iexact=email
        )[:2])
        usuario = contas[0] if len(contas) == 1 else None

        if usuario is None:
            # Quando não existe conta com o e-mail, a mensagem agora é a do
            # Artefato 4 (HU22, critério 2). A mensagem antiga continua para o caso raro de
            # haver mais de uma conta com o mesmo e-mail.
            form.add_error(
                "email",
                "Nenhuma conta com este e-mail."
                if not contas else
                "Não foi possível identificar uma única conta com este e-mail."
            )

        elif usuario.pk == projeto.dono_id:
            form.add_error(
                "email",
                "Este usuário já é o dono do projeto."
            )

        elif projeto.membros.filter(pk=usuario.pk).exists():
            form.add_error(
                "email",
                "Este usuário já participa do projeto."
            )

        else:
            projeto.membros.add(usuario)

            return redirect(
                "membros_projeto",
                pk=projeto.pk
            )

    return render(
        request,
        "core/membros_projeto.html",
        {
            "projeto": projeto,
            "form": form,
            "membros": projeto.membros.all()
        }
    )


# HU23 - Remover membro

@login_required(login_url="login")
@require_POST
def remover_membro(request, pk, usuario_id):

    projeto = get_object_or_404(
        Projeto,
        pk=pk,
        dono=request.user
    )

    membro = get_object_or_404(
        projeto.membros,
        pk=usuario_id
    )

    # Remover a participação não exclui o usuário
    # nem as histórias existentes.
    projeto.membros.remove(membro)

    return redirect(
        "membros_projeto",
        pk=projeto.pk
    )


# HU24 - Sair de um projeto

@login_required(login_url="login")
@require_POST
def sair_projeto(request, pk):

    # O dono não pode sair do próprio projeto
    projeto = get_object_or_404(
        Projeto.objects.exclude(dono=request.user),
        pk=pk,
        membros=request.user
    )

    projeto.membros.remove(request.user)

    return redirect("inicio")


# Projeto que o usuário pode acessar (dono ou membro). Para os outros usuários, o projeto
# "não existe" (404), assim ninguém descobre projetos alheios pelo endereço (HU05).
def projeto_acessivel(usuario, pk):
    projeto = get_object_or_404(
        Projeto.objects.filter(Q(dono=usuario) | Q(membros=usuario)).distinct(),
        pk=pk,
    )
    # Sprints cuja data de fim já passou são encerrados aqui, na primeira vez que alguém
    # abre o projeto depois do prazo (as histórias não concluídas voltam ao Product Backlog).
    encerrar_sprints_vencidos(projeto)
    return projeto


# HU05 - Detalhe do projeto (quem não participa volta para a lista de projetos)
@login_required(login_url="login")
def detalhe_projeto(request, pk):
    try:
        projeto = projeto_acessivel(request.user, pk)
    except Http404:
        return redirect("inicio")
    return render(request, "core/detalhe_projeto.html", {"projeto": projeto})


# HU06 - Editar projeto: só o dono (o filtro dono=request.user dá 404 para membros)
@login_required(login_url="login")
def editar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk, dono=request.user)
    form = ProjetoForm(request.POST if request.method == "POST" else None, instance=projeto)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("detalhe_projeto", pk=pk)
    return render(request, "core/formulario.html", {
        "form": form, "titulo": "Editar projeto", "projeto": projeto,
    })


# HU07 - Excluir projeto: só o dono, com confirmação; apaga backlogs, épicos e histórias
@login_required(login_url="login")
def excluir_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk, dono=request.user)
    erro = None
    if request.method == "POST":
        try:
            with transaction.atomic():
                projeto.delete()
        except ProtectedError:
            erro = "Não é possível excluir: há histórias com vínculos inconsistentes entre projetos."
        else:
            return redirect("inicio")
    return render(request, "core/confirmar_exclusao.html", {
        "projeto": projeto, "titulo": "Excluir projeto",
        "aviso": "O projeto e seus backlogs, épicos e histórias serão excluídos.",
        "erro": erro,
    }, status=409 if erro else 200)


# HU08 - Ver o Product Backlog: histórias que ainda não estão em nenhum Sprint Backlog
@login_required(login_url="login")
def product_backlog(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    backlog = get_object_or_404(ProductBacklog, projeto=projeto)
    historias = list(backlog.historias.select_related("epico", "responsavel").filter(
        sprint_backlog__isnull=True,
    ).filter(Q(epico__isnull=True) | Q(epico__projeto=projeto)).annotate(num_criterios=Count("criterios_aceitacao")))
    # Ordem de prioridade: primeiro o MoSCoW (Must, Should, Could, Won't, sem etiqueta) e,
    # dentro de cada etiqueta, o maior score RICE primeiro. RICE incompleto ou não calculável
    # fica depois dos calculados. Empate: ordem alfabética.
    ordem_moscow = {"M": 0, "S": 1, "C": 2, "W": 3, "": 4}
    historias.sort(key=lambda h: (
        ordem_moscow.get(h.moscow, 4),
        h.rice_score is None,
        -(h.rice_score or 0),
        h.titulo.lower(),
    ))
    # Sprints que ainda recebem histórias (planejados ou em andamento), para o "Mover para".
    sprints_abertos = [s for s in projeto.sprint_backlogs.order_by("data_inicio", "pk") if not s.fechado]
    por_moscow = {codigo: 0 for codigo in ordem_moscow}
    for h in historias:
        por_moscow[h.moscow] = por_moscow.get(h.moscow, 0) + 1
    return render(request, "core/product_backlog.html", {
        "projeto": projeto, "backlog": backlog, "historias": historias,
        "sprints_abertos": sprints_abertos,
        "total_pontos": sum(h.story_points or 0 for h in historias),
        "sem_estimativa": sum(1 for h in historias if h.story_points is None),
        "contagem_moscow": [
            ("M", "Must", por_moscow["M"]), ("S", "Should", por_moscow["S"]),
            ("C", "Could", por_moscow["C"]), ("W", "Won't", por_moscow["W"]),
        ],
    })


# HU08 - Criar o Product Backlog (requisito 5: só um por projeto)
@login_required(login_url="login")
def criar_product_backlog(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    if ProductBacklog.objects.filter(projeto=projeto).exists():
        return redirect("product_backlog", pk=pk)
    form = ProductBacklogForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Também impede duplicação quando há duas submissões.
            ProductBacklog.objects.get_or_create(
                projeto=projeto, defaults={"descricao": form.cleaned_data["descricao"]},
            )
        return redirect("product_backlog", pk=pk)
    return render(request, "core/formulario.html", {
        "form": form, "titulo": "Criar Product Backlog", "projeto": projeto,
    })


# HU08 - Editar a descrição do Product Backlog
@login_required(login_url="login")
def editar_product_backlog(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    backlog = get_object_or_404(ProductBacklog, projeto=projeto)
    form = ProductBacklogForm(
        request.POST if request.method == "POST" else None, instance=backlog,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("product_backlog", pk=pk)
    return render(request, "core/formulario.html", {
        "form": form, "titulo": "Editar Product Backlog", "projeto": projeto,
    })


# HU08 - Excluir o Product Backlog: bloqueado enquanto houver histórias no projeto
# (a regra fica em signals.py, para valer também no admin)
@login_required(login_url="login")
def excluir_product_backlog(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    backlog = get_object_or_404(ProductBacklog, projeto=projeto)
    erro = None
    if request.method == "POST":
        try:
            with transaction.atomic():
                backlog.delete()
        except ProtectedError:
            erro = "Não é possível excluir o Product Backlog enquanto houver histórias no projeto, inclusive em Sprint Backlogs."
        else:
            return redirect("detalhe_projeto", pk=pk)
    return render(request, "core/confirmar_exclusao.html", {
        "projeto": projeto, "titulo": "Excluir Product Backlog",
        "aviso": "A exclusão é permitida somente sem histórias no projeto, inclusive nos Sprints. O backlog não será recriado automaticamente; participantes poderão criá-lo novamente.",
        "erro": erro,
    }, status=409 if erro else 200)


# ======================================================================
# CRUD de histórias de usuário (HU12, HU13, HU14; requisitos 7 e 9), CRUD de
# épicos (HU15, HU16; requisito 10) e vinculação história-épico (HU17; requisito 11).
# O acesso usa projeto_acessivel(): dono e membros do projeto podem operar histórias e
# épicos; quem não participa recebe 404.
# ======================================================================
def historias_visiveis(projeto):
    # A história pertence ao projeto pelo Product Backlog ou por um Sprint Backlog.
    return (HistoriaUsuario.objects
            .filter(Q(product_backlog__projeto=projeto) | Q(sprint_backlog__projeto=projeto))
            .select_related("epico", "sprint_backlog")
            .distinct())


def obter_historia(projeto, historia_id):
    return get_object_or_404(historias_visiveis(projeto), pk=historia_id)


def avisar_historia(request, historia):
    # Avisos de boas práticas depois de salvar; a história é salva do mesmo jeito.
    if historia.grande_demais:
        messages.warning(request, f"Com {historia.story_points} pontos, a história pode ser grande demais "
                                  "para um Sprint. Considere dividi-la em histórias menores.")
    if historia.sem_criterios:
        messages.warning(request, "A história ainda não tem critério de aceitação. Adicione pelo menos um "
                                  "para o time saber quando ela está pronta.")


# HU12 a HU14 - Lista de todas as histórias do projeto (em qualquer backlog)
@login_required(login_url="login")
def historia_lista(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    return render(request, "core/historia_lista.html", {
        "projeto": projeto,
        "historias": historias_visiveis(projeto).annotate(num_criterios=Count("criterios_aceitacao")).order_by("titulo"),
    })


# HU12 - Criar história: ela nasce no Product Backlog do projeto (requisito 7)
@login_required(login_url="login")
def historia_criar(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    backlog = ProductBacklog.objects.filter(projeto=projeto).first()
    if backlog is None:
        # Sem Product Backlog não há onde a história nascer; o usuário cria o backlog antes
        # (HU08). O backlog não é recriado sozinho, para respeitar a exclusão feita pelo usuário.
        messages.error(request, "Crie o Product Backlog do projeto antes de criar histórias.")
        return redirect("criar_product_backlog", pk=projeto.pk)
    historia = HistoriaUsuario(product_backlog=backlog)
    # "Nova história neste épico": a página do épico manda ?epico=<id> e o campo já vem
    # escolhido (só vale para épicos do próprio projeto).
    inicial = {}
    epico_id = request.GET.get("epico")
    if epico_id and epico_id.isdigit() and Epico.objects.filter(pk=epico_id, projeto=projeto).exists():
        inicial["epico"] = int(epico_id)
    form = HistoriaUsuarioForm(request.POST or None, instance=historia, projeto=projeto, initial=inicial)
    if request.method == "POST" and form.is_valid():
        nova = form.save()
        messages.success(request, "História criada no Product Backlog.")
        avisar_historia(request, nova)
        return redirect("historia_lista", pk=projeto.pk)
    return render(request, "core/historia_form.html", {"projeto": projeto, "form": form, "acao": "Nova história"})


# HU12/HU13 - Detalhe da história, com Story Points, MoSCoW e RICE
@login_required(login_url="login")
def historia_detalhe(request, pk, historia_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    # A página também lista os critérios de aceitação da história (requisito 12)
    # e, desde a HU11, traz o formulário para mover a história de backlog (requisito 8).
    return render(request, "core/historia_detalhe.html", {
        "projeto": projeto, "historia": historia, "criterios": historia.criterios_aceitacao.all(),
        "form_mover": MoverHistoriaForm(historia=historia, projeto=projeto),
    })


# HU13 - Editar história (inclui Story Points, MoSCoW, RICE e épico)
@login_required(login_url="login")
def historia_editar(request, pk, historia_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    form = HistoriaUsuarioForm(request.POST or None, instance=historia, projeto=projeto)
    if request.method == "POST" and form.is_valid():
        # HU21 (critério 4): o score RICE é recalculado na hora, porque é uma propriedade
        # calculada a partir dos campos salvos.
        form.save()
        messages.success(request, "História atualizada.")
        # Na edição os avisos não viram mensagem: a página da história já os mostra.
        return redirect("historia_detalhe", pk=projeto.pk, historia_id=historia.pk)
    return render(request, "core/historia_form.html", {"projeto": projeto, "form": form, "acao": "Editar história", "historia": historia})


# HU14 - Excluir história: só apaga depois da confirmação (POST); cancelar não apaga nada
@login_required(login_url="login")
def historia_excluir(request, pk, historia_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    if request.method == "POST":
        historia.delete()
        messages.success(request, "História excluída.")
        return redirect("historia_lista", pk=projeto.pk)
    return render(request, "core/confirmar_exclusao_item.html", {
        "projeto": projeto, "objeto": historia, "tipo": "a história",
        "voltar_url": reverse("historia_detalhe", args=[projeto.pk, historia.pk]),
    })


# HU15/HU16 - Lista de épicos do projeto
@login_required(login_url="login")
def epico_lista(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    return render(request, "core/epico_lista.html", {
        "projeto": projeto,
        "epicos": projeto.epicos.prefetch_related("historias"),
    })


# HU15 - Criar épico
@login_required(login_url="login")
def epico_criar(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    form = EpicoForm(request.POST or None, instance=Epico(projeto=projeto))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Épico criado.")
        return redirect("epico_lista", pk=projeto.pk)
    return render(request, "core/epico_form.html", {"projeto": projeto, "form": form, "acao": "Novo épico"})


# HU17 - Detalhe do épico, com as histórias ligadas a ele
@login_required(login_url="login")
def epico_detalhe(request, pk, epico_id):
    projeto = projeto_acessivel(request.user, pk)
    epico = get_object_or_404(Epico, pk=epico_id, projeto=projeto)
    historias = list(epico.historias.select_related("sprint_backlog", "responsavel")
                     .annotate(num_criterios=Count("criterios_aceitacao")).order_by("titulo"))
    return render(request, "core/epico_detalhe.html", {
        "projeto": projeto, "epico": epico, "historias": historias,
        "total_pontos": sum(h.story_points or 0 for h in historias),
    })


# Atalho do épico (ponto 7): escolher várias histórias do projeto de uma vez e ligar ao
# épico. Aparecem as sem épico e as que estão em outro épico; marcar uma destas move a
# história de épico.
@login_required(login_url="login")
def epico_adicionar_historias(request, pk, epico_id):
    projeto = projeto_acessivel(request.user, pk)
    epico = get_object_or_404(Epico, pk=epico_id, projeto=projeto)
    candidatas = historias_visiveis(projeto).exclude(epico=epico).select_related("epico").order_by("titulo")
    if request.method == "POST":
        escolhidas = candidatas.filter(pk__in=request.POST.getlist("historias"))
        if not escolhidas:
            messages.error(request, "Marque pelo menos uma história.")
        else:
            de_outro_epico = 0
            for historia in escolhidas:
                if historia.epico_id:
                    de_outro_epico += 1
                historia.epico = epico
                historia.save(update_fields=["epico"])
            total = len(escolhidas)
            texto = "1 história ligada ao épico." if total == 1 else f"{total} histórias ligadas ao épico."
            if de_outro_epico == 1:
                texto += " Uma delas saiu de outro épico." if total > 1 else " Ela saiu de outro épico."
            elif de_outro_epico > 1:
                texto += f" {de_outro_epico} delas saíram de outro épico."
            messages.success(request, texto)
            return redirect("epico_detalhe", pk=projeto.pk, epico_id=epico.pk)
    return render(request, "core/epico_adicionar_historias.html", {
        "projeto": projeto, "epico": epico,
        "sem_epico": [h for h in candidatas if h.epico_id is None],
        "outro_epico": [h for h in candidatas if h.epico_id is not None],
    })


# Tira a história do épico: ela fica "sem épico" e não é apagada (como na HU16).
@login_required(login_url="login")
@require_POST
def epico_remover_historia(request, pk, epico_id, historia_id):
    projeto = projeto_acessivel(request.user, pk)
    epico = get_object_or_404(Epico, pk=epico_id, projeto=projeto)
    historia = get_object_or_404(historias_visiveis(projeto), pk=historia_id, epico=epico)
    historia.epico = None
    historia.save(update_fields=["epico"])
    messages.success(request, f"“{historia.titulo}” saiu do épico e ficou sem épico.")
    return redirect("epico_detalhe", pk=projeto.pk, epico_id=epico.pk)


# HU16 - Editar épico (o nome novo aparece em todas as histórias ligadas)
@login_required(login_url="login")
def epico_editar(request, pk, epico_id):
    projeto = projeto_acessivel(request.user, pk)
    epico = get_object_or_404(Epico, pk=epico_id, projeto=projeto)
    form = EpicoForm(request.POST or None, instance=epico)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Épico atualizado.")
        return redirect("epico_detalhe", pk=projeto.pk, epico_id=epico.pk)
    return render(request, "core/epico_form.html", {"projeto": projeto, "form": form, "acao": "Editar épico", "epico": epico})


# HU16 - Excluir épico: as histórias não são apagadas, o on_delete=SET_NULL as deixa sem épico
@login_required(login_url="login")
def epico_excluir(request, pk, epico_id):
    projeto = projeto_acessivel(request.user, pk)
    epico = get_object_or_404(Epico, pk=epico_id, projeto=projeto)
    if request.method == "POST":
        epico.delete()
        messages.success(request, "Épico excluído. As histórias dele ficaram sem épico.")
        return redirect("epico_lista", pk=projeto.pk)
    return render(request, "core/confirmar_exclusao_item.html", {
        "projeto": projeto, "objeto": epico, "tipo": "o épico",
        "aviso": "As histórias ligadas a ele não serão apagadas, só ficarão sem épico.",
        "voltar_url": reverse("epico_detalhe", args=[projeto.pk, epico.pk]),
    })


# ======================================================================
# CRUD de critérios de aceitação (requisitos 12 e 13; HU12 critério 3 e HU13),
# usando o model CriterioAceitacao do Artefato 7. Os critérios ficam dentro da história:
# a leitura é na página de detalhe dela, e criar, editar e excluir voltam para lá.
# Dono e membros do projeto podem operar; quem não participa recebe 404.
# ======================================================================
def obter_criterio(historia, criterio_id):
    return get_object_or_404(CriterioAceitacao, pk=criterio_id, historia_usuario=historia)


# Requisito 12 (criar) - Adicionar critério no formato Dado / Quando / Então
@login_required(login_url="login")
def criterio_criar(request, pk, historia_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    form = CriterioAceitacaoForm(request.POST or None, instance=CriterioAceitacao(historia_usuario=historia))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Critério de aceitação adicionado.")
        return redirect("historia_detalhe", pk=projeto.pk, historia_id=historia.pk)
    return render(request, "core/criterio_form.html", {
        "projeto": projeto, "historia": historia, "form": form, "acao": "Novo critério de aceitação",
    })


# Requisito 12 (atualizar) - HU13: editar um critério
@login_required(login_url="login")
def criterio_editar(request, pk, historia_id, criterio_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    criterio = obter_criterio(historia, criterio_id)
    # Na edição, o critério pode mudar de história (útil ao dividir uma história grande).
    form = CriterioAceitacaoForm(request.POST or None, instance=criterio,
                                 historias=historias_visiveis(projeto).order_by("titulo"))
    if request.method == "POST" and form.is_valid():
        salvo = form.save()
        if salvo.historia_usuario_id != historia.pk:
            messages.success(request, f"Critério movido para “{salvo.historia_usuario.titulo}”.")
        else:
            messages.success(request, "Critério de aceitação atualizado.")
        return redirect("historia_detalhe", pk=projeto.pk, historia_id=historia.pk)
    return render(request, "core/criterio_form.html", {
        "projeto": projeto, "historia": historia, "form": form, "acao": "Editar critério de aceitação",
    })


# Requisito 12 (excluir) - HU13 (critério 2): apagar um critério, com confirmação
@login_required(login_url="login")
def criterio_excluir(request, pk, historia_id, criterio_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    criterio = obter_criterio(historia, criterio_id)
    voltar_url = reverse("historia_detalhe", args=[projeto.pk, historia.pk])
    if request.method == "POST":
        criterio.delete()
        messages.success(request, "Critério de aceitação excluído.")
        return redirect(voltar_url)
    return render(request, "core/confirmar_exclusao_item.html", {
        "projeto": projeto, "objeto": f"Dado {criterio.dado} quando {criterio.quando} então {criterio.entao}",
        "tipo": "o critério de aceitação", "voltar_url": voltar_url,
    })


# ======================================================================
# CRUD de Sprint Backlogs (requisito 6; HU09 e HU10). Um projeto pode ter
# vários Sprint Backlogs, cada um com nome e período. Dono e membros do projeto podem
# operar; quem não participa recebe 404.
# ======================================================================
def obter_sprint(projeto, sprint_id):
    return get_object_or_404(SprintBacklog, pk=sprint_id, projeto=projeto)


# HU09/HU10 - Lista dos Sprint Backlogs do projeto
@login_required(login_url="login")
def sprint_lista(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    sprints = list(projeto.sprint_backlogs.prefetch_related("historias", "historias_devolvidas").order_by("-data_inicio", "-pk"))
    for sprint in sprints:
        sprint.resumo = resumo_sprint(sprint)
    return render(request, "core/sprint_lista.html", {"projeto": projeto, "sprints": sprints})


def resumo_sprint(sprint):
    # Números do Sprint para a lista e para o histórico. Num Sprint fechado, as histórias que
    # ficaram nele são as concluídas e as outras estão em HistoriaDevolvida.
    historias = list(sprint.historias.all())
    devolvidas = list(sprint.historias_devolvidas.all())
    concluidas = [h for h in historias if h.situacao == HistoriaUsuario.SITUACAO_CONCLUIDA]
    pontos = lambda itens: sum(h.story_points or 0 for h in itens)
    return {
        "total": len(historias) + len(devolvidas),
        "concluidas": len(concluidas),
        "devolvidas": len(devolvidas),
        "pontos_concluidos": pontos(concluidas),
        "pontos_total": pontos(historias) + pontos(devolvidas),
    }


# HU09 - Criar Sprint Backlog com nome e período (nasce vazio)
@login_required(login_url="login")
def sprint_criar(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    form = SprintBacklogForm(request.POST or None, instance=SprintBacklog(projeto=projeto))
    if request.method == "POST" and form.is_valid():
        sprint = form.save()
        messages.success(request, "Sprint Backlog criado.")
        return redirect("sprint_detalhe", pk=projeto.pk, sprint_id=sprint.pk)
    return render(request, "core/sprint_form.html", {"projeto": projeto, "form": form, "acao": "Novo Sprint Backlog"})


# HU09/HU10 - Detalhe do Sprint Backlog, com as histórias que estão nele
@login_required(login_url="login")
def sprint_detalhe(request, pk, sprint_id):
    projeto = projeto_acessivel(request.user, pk)
    sprint = obter_sprint(projeto, sprint_id)
    if sprint.fechado:
        # Concluído ou cancelado: a página vira histórico, só para consulta.
        return render(request, "core/sprint_historico.html", {
            "projeto": projeto, "sprint": sprint, "resumo": resumo_sprint(sprint),
            "concluidas": sprint.historias.select_related("responsavel").order_by("titulo"),
            "devolvidas": sprint.historias_devolvidas.select_related(
                "historia__sprint_backlog", "historia__product_backlog"),
            "antecipado": sprint.encerrado_em and sprint.encerrado_em < sprint.data_fim,
            "dias_antes": (sprint.data_fim - sprint.encerrado_em).days if sprint.encerrado_em else 0,
        })
    historias = list(sprint.historias.select_related("epico", "responsavel")
                     .annotate(num_criterios=Count("criterios_aceitacao")).order_by("titulo"))
    total_pontos = sum(h.story_points or 0 for h in historias)
    # Quadro Kanban: uma coluna por situação, com quantas histórias e pontos cada uma tem.
    colunas = []
    for valor, nome in HistoriaUsuario.SITUACAO_CHOICES:
        da_coluna = [h for h in historias if h.situacao == valor]
        colunas.append({
            "valor": valor, "nome": nome, "historias": da_coluna,
            "pontos": sum(h.story_points or 0 for h in da_coluna),
        })
    hoje = timezone.localdate()
    e_dono = projeto.dono_id == request.user.id
    return render(request, "core/sprint_detalhe.html", {
        "projeto": projeto, "sprint": sprint, "historias": historias, "total_pontos": total_pontos,
        "colunas": colunas,
        "dias_restantes": (sprint.data_fim - hoje).days,
        "dias_para_comecar": (sprint.data_inicio - hoje).days,
        # Encerrar e cancelar: só o dono do projeto (no Scrum, o Product Owner).
        "pode_encerrar": e_dono and sprint.status == SprintBacklog.STATUS_EM_ANDAMENTO,
        "pode_cancelar": e_dono,
    })


def sprint_aberto_do_dono(request, pk, sprint_id):
    # Encerrar e cancelar só valem para o dono do projeto e para Sprints ainda abertos.
    projeto = projeto_acessivel(request.user, pk)
    sprint = obter_sprint(projeto, sprint_id)
    if projeto.dono_id != request.user.id:
        messages.error(request, "Só o dono do projeto pode encerrar ou cancelar um Sprint.")
        return projeto, sprint, redirect("sprint_detalhe", pk=projeto.pk, sprint_id=sprint.pk)
    if sprint.fechado:
        messages.error(request, "Este Sprint já foi encerrado ou cancelado.")
        return projeto, sprint, redirect("sprint_detalhe", pk=projeto.pk, sprint_id=sprint.pk)
    return projeto, sprint, None


# Encerrar Sprint antes do previsto: as histórias não concluídas voltam ao Product Backlog.
@login_required(login_url="login")
def sprint_encerrar(request, pk, sprint_id):
    projeto, sprint, recusa = sprint_aberto_do_dono(request, pk, sprint_id)
    if recusa:
        return recusa
    if sprint.status != SprintBacklog.STATUS_EM_ANDAMENTO:
        messages.error(request, "Só um Sprint em andamento pode ser encerrado. Um Sprint planejado pode ser cancelado ou excluído.")
        return redirect("sprint_detalhe", pk=projeto.pk, sprint_id=sprint.pk)
    erro = None
    if request.method == "POST":
        try:
            devolvidas = fechar_sprint(sprint, usuario=request.user)
        except SemProductBacklog as e:
            erro = str(e)
        else:
            messages.success(request, f"{sprint.nome} encerrado. {len(devolvidas)} história(s) voltaram para o Product Backlog.")
            return redirect("sprint_detalhe", pk=projeto.pk, sprint_id=sprint.pk)
    return render(request, "core/sprint_fechar.html", {
        "projeto": projeto, "sprint": sprint, "acao": "encerrar", "erro": erro,
        "pendentes": historias_nao_concluidas(sprint),
        "concluidas": sprint.historias.filter(situacao=HistoriaUsuario.SITUACAO_CONCLUIDA).count(),
        "hoje": timezone.localdate(),
    })


# Cancelar Sprint: quando o trabalho deixou de fazer sentido. Motivo opcional.
@login_required(login_url="login")
def sprint_cancelar(request, pk, sprint_id):
    projeto, sprint, recusa = sprint_aberto_do_dono(request, pk, sprint_id)
    if recusa:
        return recusa
    form = CancelarSprintForm(request.POST or None)
    erro = None
    if request.method == "POST" and form.is_valid():
        try:
            devolvidas = fechar_sprint(sprint, usuario=request.user, cancelar=True, motivo=form.cleaned_data["motivo"])
        except SemProductBacklog as e:
            erro = str(e)
        else:
            messages.success(request, f"{sprint.nome} cancelado. {len(devolvidas)} história(s) voltaram para o Product Backlog.")
            return redirect("sprint_detalhe", pk=projeto.pk, sprint_id=sprint.pk)
    return render(request, "core/sprint_fechar.html", {
        "projeto": projeto, "sprint": sprint, "acao": "cancelar", "erro": erro, "form": form,
        "pendentes": historias_nao_concluidas(sprint),
        "concluidas": sprint.historias.filter(situacao=HistoriaUsuario.SITUACAO_CONCLUIDA).count(),
        "hoje": timezone.localdate(),
    })


# HU10 - Editar nome e datas do Sprint Backlog
@login_required(login_url="login")
def sprint_editar(request, pk, sprint_id):
    projeto = projeto_acessivel(request.user, pk)
    sprint = obter_sprint(projeto, sprint_id)
    if sprint.fechado:
        messages.error(request, "Um Sprint encerrado ou cancelado faz parte do histórico e não pode ser editado.")
        return redirect("sprint_detalhe", pk=projeto.pk, sprint_id=sprint.pk)
    form = SprintBacklogForm(request.POST or None, instance=sprint)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Sprint Backlog atualizado.")
        return redirect("sprint_detalhe", pk=projeto.pk, sprint_id=sprint.pk)
    return render(request, "core/sprint_form.html", {
        "projeto": projeto, "form": form, "acao": "Editar Sprint Backlog", "sprint": sprint,
    })


# HU10 - Excluir Sprint Backlog, com confirmação. As histórias não são apagadas: voltam para
# o Product Backlog (regra em signals.py, feita pelo Leandro).
@login_required(login_url="login")
def sprint_excluir(request, pk, sprint_id):
    projeto = projeto_acessivel(request.user, pk)
    sprint = obter_sprint(projeto, sprint_id)
    voltar_url = reverse("sprint_detalhe", args=[projeto.pk, sprint.pk])
    erro = None
    if request.method == "POST":
        try:
            with transaction.atomic():
                sprint.delete()
        except ProtectedError as e:
            # Acontece quando o Sprint tem histórias e o projeto está sem Product Backlog.
            erro = e.args[0]
        else:
            messages.success(request, "Sprint Backlog excluído. As histórias dele voltaram para o Product Backlog.")
            return redirect("sprint_lista", pk=projeto.pk)
    return render(request, "core/confirmar_exclusao_item.html", {
        "projeto": projeto, "objeto": sprint, "tipo": "o Sprint Backlog",
        "aviso": "As histórias deste Sprint não serão apagadas: elas voltam para o Product Backlog.",
        "erro": erro, "voltar_url": voltar_url,
    }, status=409 if erro else 200)


# ======================================================================
# Mover história entre backlogs (requisito 8; HU11). A história pode ir do
# Product Backlog para um Sprint, voltar de um Sprint para o Product Backlog ou passar de
# um Sprint para outro, sempre dentro do mesmo projeto.
# ======================================================================
@login_required(login_url="login")
@require_POST
def historia_mover(request, pk, historia_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    form = MoverHistoriaForm(request.POST, historia=historia, projeto=projeto)
    if form.is_valid():
        destino = form.mover()
        messages.success(request, f"História movida para {destino}.")
    else:
        for erro in form.errors.get("destino", []):
            messages.error(request, erro)
    # O "Mover para Sprint" da lista do Product Backlog volta para a própria lista.
    if request.POST.get("voltar") == "product_backlog":
        return redirect("product_backlog", pk=projeto.pk)
    return redirect("historia_detalhe", pk=projeto.pk, historia_id=historia.pk)


# Quadro Kanban do Sprint: muda a situação de uma história (A fazer, Em desenvolvimento ou
# Concluída) pelos botões do cartão. Dono e membros podem mover os cartões. Só vale para
# histórias que estão em um Sprint; no Product Backlog a situação não se aplica.
@login_required(login_url="login")
@require_POST
def historia_situacao(request, pk, historia_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    nova = request.POST.get("situacao")
    validas = dict(HistoriaUsuario.SITUACAO_CHOICES)
    if historia.sprint_backlog_id is None:
        messages.error(request, "A história precisa estar em um Sprint para mudar de situação.")
        return redirect("historia_detalhe", pk=projeto.pk, historia_id=historia.pk)
    if historia.sprint_backlog.fechado:
        messages.error(request, "Este Sprint já foi encerrado ou cancelado; o quadro não muda mais.")
    elif nova not in validas:
        messages.error(request, "Situação inválida.")
    elif nova != historia.situacao:
        historia.situacao = nova
        historia.save(update_fields=["situacao"])
        messages.success(request, f"“{historia.titulo}” foi para {validas[nova]}.")
    return redirect("sprint_detalhe", pk=projeto.pk, sprint_id=historia.sprint_backlog_id)
