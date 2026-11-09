# Rotas do sistema: autenticação (HU01-HU03), projetos e membros (HU04-HU07, HU22-HU24),
# Product Backlog (HU08), Sprint Backlogs (HU09-HU10), histórias (HU11-HU14), critérios de aceitação (requisito 12)
# e épicos (HU15-HU17).
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
    # ADICIONADO: histórias de usuário (HU12, HU13, HU14)
    path("projetos/<int:pk>/historias/", views.historia_lista, name="historia_lista"),
    path("projetos/<int:pk>/historias/nova/", views.historia_criar, name="historia_criar"),
    path("projetos/<int:pk>/historias/<int:historia_id>/", views.historia_detalhe, name="historia_detalhe"),
    path("projetos/<int:pk>/historias/<int:historia_id>/editar/", views.historia_editar, name="historia_editar"),
    path("projetos/<int:pk>/historias/<int:historia_id>/excluir/", views.historia_excluir, name="historia_excluir"),
    # ADICIONADO: mover história entre backlogs (requisito 8; HU11)
    path("projetos/<int:pk>/historias/<int:historia_id>/mover/", views.historia_mover, name="historia_mover"),
    # ADICIONADO: critérios de aceitação de uma história (requisitos 12 e 13)
    path("projetos/<int:pk>/historias/<int:historia_id>/criterios/novo/", views.criterio_criar, name="criterio_criar"),
    path("projetos/<int:pk>/historias/<int:historia_id>/criterios/<int:criterio_id>/editar/", views.criterio_editar, name="criterio_editar"),
    path("projetos/<int:pk>/historias/<int:historia_id>/criterios/<int:criterio_id>/excluir/", views.criterio_excluir, name="criterio_excluir"),
    # ADICIONADO: Sprint Backlogs (requisito 6; HU09, HU10)
    path("projetos/<int:pk>/sprints/", views.sprint_lista, name="sprint_lista"),
    path("projetos/<int:pk>/sprints/novo/", views.sprint_criar, name="sprint_criar"),
    path("projetos/<int:pk>/sprints/<int:sprint_id>/", views.sprint_detalhe, name="sprint_detalhe"),
    path("projetos/<int:pk>/sprints/<int:sprint_id>/editar/", views.sprint_editar, name="sprint_editar"),
    path("projetos/<int:pk>/sprints/<int:sprint_id>/excluir/", views.sprint_excluir, name="sprint_excluir"),
    # ADICIONADO: épicos (HU15, HU16) e histórias ligadas a cada um (HU17)
    path("projetos/<int:pk>/epicos/", views.epico_lista, name="epico_lista"),
    path("projetos/<int:pk>/epicos/novo/", views.epico_criar, name="epico_criar"),
    path("projetos/<int:pk>/epicos/<int:epico_id>/", views.epico_detalhe, name="epico_detalhe"),
    path("projetos/<int:pk>/epicos/<int:epico_id>/editar/", views.epico_editar, name="epico_editar"),
    path("projetos/<int:pk>/epicos/<int:epico_id>/excluir/", views.epico_excluir, name="epico_excluir"),
]
