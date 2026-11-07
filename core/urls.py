from django.urls import path
from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("cadastro/", views.cadastro, name="cadastro"),
    path("login/", views.entrar, name="login"),
    path("logout/", views.sair, name="logout"),
    path("projetos/novo/", views.criar_projeto, name="criar_projeto"),
    path("projetos/<int:pk>/", views.detalhe_projeto, name="detalhe_projeto"),
    path("projetos/<int:pk>/editar/", views.editar_projeto, name="editar_projeto"),
    path("projetos/<int:pk>/excluir/", views.excluir_projeto, name="excluir_projeto"),
    path("projetos/<int:pk>/membros/", views.membros_projeto, name="membros_projeto"),
    path("projetos/<int:pk>/membros/<int:usuario_id>/remover/", views.remover_membro, name="remover_membro"),
    path("projetos/<int:pk>/sair/", views.sair_projeto, name="sair_projeto"),
    path("projetos/<int:pk>/backlog/", views.product_backlog, name="product_backlog"),
    path("projetos/<int:pk>/backlog/criar/", views.criar_product_backlog, name="criar_product_backlog"),
    path("projetos/<int:pk>/backlog/editar/", views.editar_product_backlog, name="editar_product_backlog"),
    path("projetos/<int:pk>/backlog/excluir/", views.excluir_product_backlog, name="excluir_product_backlog"),
]
