
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError

from .models import Projeto, ProductBacklog

from .forms import (
    CadastroForm, LoginForm, ProjetoForm, AdicionarMembroForm, ProductBacklogForm,
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


# Página inicial protegida

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


def projeto_acessivel(usuario, pk):
    return get_object_or_404(
        Projeto.objects.filter(Q(dono=usuario) | Q(membros=usuario)).distinct(),
        pk=pk,
    )


@login_required(login_url="login")
def detalhe_projeto(request, pk):
    try:
        projeto = projeto_acessivel(request.user, pk)
    except Http404:
        return redirect("inicio")
    return render(request, "core/detalhe_projeto.html", {"projeto": projeto})


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
