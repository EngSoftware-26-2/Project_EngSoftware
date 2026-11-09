
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
from django.db.models import Q
from django.db.models.deletion import ProtectedError

from .models import Projeto, ProductBacklog, Epico, HistoriaUsuario, CriterioAceitacao, SprintBacklog

from .forms import (
    CadastroForm, LoginForm, ProjetoForm, AdicionarMembroForm, ProductBacklogForm,
    EpicoForm, HistoriaUsuarioForm, CriterioAceitacaoForm, SprintBacklogForm,
)

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
            form.add_error(
                "email",
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
    return get_object_or_404(
        Projeto.objects.filter(Q(dono=usuario) | Q(membros=usuario)).distinct(),
        pk=pk,
    )


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
    return render(request, "core/product_backlog.html", {
        "projeto": projeto, "backlog": backlog,
        "historias": backlog.historias.select_related("epico").filter(
            sprint_backlog__isnull=True,
        ).filter(Q(epico__isnull=True) | Q(epico__projeto=projeto)).order_by("pk"),
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
# ADICIONADO: CRUD de histórias de usuário (HU12, HU13, HU14; requisitos 7 e 9), CRUD de
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


# HU12 a HU14 - Lista de todas as histórias do projeto (em qualquer backlog)
@login_required(login_url="login")
def historia_lista(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    return render(request, "core/historia_lista.html", {
        "projeto": projeto,
        "historias": historias_visiveis(projeto).order_by("titulo"),
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
    form = HistoriaUsuarioForm(request.POST or None, instance=historia, projeto=projeto)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "História criada no Product Backlog.")
        return redirect("historia_lista", pk=projeto.pk)
    return render(request, "core/historia_form.html", {"projeto": projeto, "form": form, "acao": "Nova história"})


# HU12/HU13 - Detalhe da história, com Story Points, MoSCoW e RICE
@login_required(login_url="login")
def historia_detalhe(request, pk, historia_id):
    projeto = projeto_acessivel(request.user, pk)
    historia = obter_historia(projeto, historia_id)
    # ALTERADO: a página também lista os critérios de aceitação da história (requisito 12).
    return render(request, "core/historia_detalhe.html", {
        "projeto": projeto, "historia": historia, "criterios": historia.criterios_aceitacao.all(),
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
    return render(request, "core/epico_detalhe.html", {
        "projeto": projeto, "epico": epico, "historias": epico.historias.order_by("titulo"),
    })


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
# ADICIONADO: CRUD de critérios de aceitação (requisitos 12 e 13; HU12 critério 3 e HU13),
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
    form = CriterioAceitacaoForm(request.POST or None, instance=criterio)
    if request.method == "POST" and form.is_valid():
        form.save()
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
# ADICIONADO: CRUD de Sprint Backlogs (requisito 6; HU09 e HU10). Um projeto pode ter
# vários Sprint Backlogs, cada um com nome e período. Dono e membros do projeto podem
# operar; quem não participa recebe 404.
# ======================================================================
def obter_sprint(projeto, sprint_id):
    return get_object_or_404(SprintBacklog, pk=sprint_id, projeto=projeto)


# HU09/HU10 - Lista dos Sprint Backlogs do projeto
@login_required(login_url="login")
def sprint_lista(request, pk):
    projeto = projeto_acessivel(request.user, pk)
    return render(request, "core/sprint_lista.html", {
        "projeto": projeto,
        "sprints": projeto.sprint_backlogs.prefetch_related("historias").order_by("data_inicio", "pk"),
    })


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
    historias = sprint.historias.select_related("epico").order_by("titulo")
    total_pontos = sum(h.story_points or 0 for h in historias)
    return render(request, "core/sprint_detalhe.html", {
        "projeto": projeto, "sprint": sprint, "historias": historias, "total_pontos": total_pontos,
    })


# HU10 - Editar nome e datas do Sprint Backlog
@login_required(login_url="login")
def sprint_editar(request, pk, sprint_id):
    projeto = projeto_acessivel(request.user, pk)
    sprint = obter_sprint(projeto, sprint_id)
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
