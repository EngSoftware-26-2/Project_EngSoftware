from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from datetime import date

from .models import Projeto, ProductBacklog, HistoriaUsuario, Epico, SprintBacklog


SPRINT_PERIODO = {
    "data_inicio": date(2026, 11, 1),
    "data_fim": date(2026, 11, 7),
}


# HU01-HU03: cadastro, login por e-mail e logout
class AutenticacaoTests(TestCase):
    def test_cadastro_autentica_e_armazena_hash(self):
        response = self.client.post(reverse("cadastro"), {
            "nome": "Ana", "email": "ANA@example.com", "senha": "SenhaForte!482",
            "confirmar_senha": "SenhaForte!482",
        })
        self.assertRedirects(response, reverse("inicio"))
        user = User.objects.get(email="ana@example.com")
        self.assertTrue(user.check_password("SenhaForte!482"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_cadastro_rejeita_email_duplicado_e_senhas_invalidas(self):
        User.objects.create_user("antigo", email="ana@example.com")
        for email, senha, confirmar in [
            ("ANA@example.com", "SenhaForte!482", "SenhaForte!482"),
            ("nova@example.com", "123", "123"),
            ("nova@example.com", "SenhaForte!482", "OutraSenha!482"),
            ("invalido", "SenhaForte!482", "SenhaForte!482"),
        ]:
            with self.subTest(email=email, senha=senha):
                response = self.client.post(reverse("cadastro"), {
                    "nome": "Ana", "email": email, "senha": senha,
                    "confirmar_senha": confirmar,
                })
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(User.objects.count(), 1)

    def test_login_por_email_de_conta_com_username_diferente(self):
        user = User.objects.create_user("legado", email="Ana@example.com", password="SenhaForte!482")
        response = self.client.post(reverse("login"), {"email": "ANA@example.com", "senha": "SenhaForte!482"})
        self.assertRedirects(response, reverse("inicio"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_login_rejeita_senha_errada_inativo_e_email_ambiguo(self):
        user = User.objects.create_user("ana", email="ana@example.com", password="SenhaForte!482")
        for password in ["errada", "SenhaForte!482"]:
            if password != "errada":
                user.is_active = False
                user.save()
            response = self.client.post(reverse("login"), {"email": user.email, "senha": password})
            self.assertTrue(response.context["form"].non_field_errors())
            self.assertNotIn("_auth_user_id", self.client.session)
        user.is_active = True
        user.save()
        User.objects.create_user("outra", email="ANA@example.com", password="SenhaForte!482")
        self.client.post(reverse("login"), {"email": user.email, "senha": "SenhaForte!482"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_exige_post(self):
        self.client.force_login(User.objects.create_user("ana"))
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)


# HU04-HU08 e HU22-HU24: projetos, Product Backlog, dono e membros, além das regras de
# integridade dos vínculos das histórias (requisitos 4, 5, 7, 8 e 11)
class ProjetoTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("dono", email="dono@example.com")
        self.membro = User.objects.create_user("membro", email="membro@example.com")
        self.outro = User.objects.create_user("outro", email="outro@example.com")
        self.projeto = Projeto.objects.create(nome="Projeto", dono=self.dono)
        self.projeto.membros.add(self.membro)
        self.backlog = ProductBacklog.objects.create(projeto=self.projeto, descricao="Original")
        self.client.force_login(self.dono)

    def url(self, name, **kwargs):
        return reverse(name, kwargs={"pk": self.projeto.pk, **kwargs})

    def test_criar_projeto_com_backlog_e_dono_autenticado(self):
        response = self.client.post(reverse("criar_projeto"), {
            "nome": "Novo", "descricao": "Descrição", "dono": self.outro.pk,
        })
        self.assertRedirects(response, reverse("inicio"))
        projeto = Projeto.objects.get(nome="Novo")
        self.assertEqual(projeto.dono, self.dono)
        self.assertEqual(projeto.product_backlog.descricao, "")
        self.assertEqual(ProductBacklog.objects.filter(projeto=projeto).count(), 1)

    def test_projeto_invalido_nao_cria_backlog(self):
        response = self.client.post(reverse("criar_projeto"), {"nome": ""})
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Projeto.objects.count(), 1)
        self.assertEqual(ProductBacklog.objects.count(), 1)

    def test_listagem_e_consulta_restritas_a_participantes(self):
        privado = Projeto.objects.create(nome="Privado", dono=self.outro)
        for user in [self.dono, self.membro]:
            self.client.force_login(user)
            response = self.client.get(reverse("inicio"))
            self.assertContains(response, self.projeto.nome)
            self.assertNotContains(response, privado.nome)
            for name in ["detalhe_projeto", "membros_projeto", "product_backlog"]:
                self.assertEqual(self.client.get(self.url(name)).status_code, 200)
        self.client.force_login(self.outro)
        self.assertRedirects(self.client.get(self.url("detalhe_projeto")), reverse("inicio"))
        for name in ["membros_projeto", "product_backlog"]:
            self.assertEqual(self.client.get(self.url(name)).status_code, 404)

    def test_editar_projeto_nao_transfere_dono(self):
        self.assertEqual(self.client.get(self.url("editar_projeto")).status_code, 200)
        response = self.client.post(self.url("editar_projeto"), {
            "nome": "Alterado", "descricao": "Nova", "dono": self.outro.pk,
        })
        self.assertRedirects(response, self.url("detalhe_projeto"))
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.nome, "Alterado")
        self.assertEqual(self.projeto.dono, self.dono)
        self.assertEqual(self.client.post(self.url("editar_projeto"), {"nome": ""}).status_code, 200)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.nome, "Alterado")

    def test_excluir_projeto_so_por_post(self):
        self.assertEqual(self.client.get(self.url("excluir_projeto")).status_code, 200)
        self.assertTrue(Projeto.objects.filter(pk=self.projeto.pk).exists())
        self.assertRedirects(self.client.post(self.url("excluir_projeto")), reverse("inicio"))
        self.assertFalse(Projeto.objects.filter(pk=self.projeto.pk).exists())
        self.assertFalse(ProductBacklog.objects.filter(pk=self.backlog.pk).exists())
        self.assertEqual(User.objects.count(), 3)

    def test_mutacoes_exclusivas_do_dono(self):
        for user in [self.membro, self.outro]:
            self.client.force_login(user)
            for name in ["editar_projeto", "excluir_projeto"]:
                for method in [self.client.get, self.client.post]:
                    with self.subTest(user=user.username, name=name, method=method.__name__):
                        self.assertEqual(method(self.url(name), {"nome": "Invadido", "descricao": "Invadido"}).status_code, 404)
            response = self.client.post(self.url("membros_projeto"), {"email": self.outro.email})
            self.assertIn(response.status_code, [403, 404])
            self.assertEqual(self.client.post(self.url("remover_membro", usuario_id=self.membro.pk)).status_code, 404)
        self.projeto.refresh_from_db()
        self.backlog.refresh_from_db()
        self.assertEqual(self.projeto.nome, "Projeto")
        self.assertEqual(self.backlog.descricao, "Original")
        self.assertTrue(self.projeto.membros.filter(pk=self.membro.pk).exists())

    def test_adicionar_membro_existente_por_email(self):
        self.assertRedirects(self.client.post(self.url("membros_projeto"), {"email": "OUTRO@example.com"}), self.url("membros_projeto"))
        self.assertTrue(self.projeto.membros.filter(pk=self.outro.pk).exists())
        self.assertEqual(User.objects.count(), 3)

    def test_rejeitar_membro_inexistente_duplicado_dono_e_email_ambiguo(self):
        User.objects.create_user("duplicado", email=self.outro.email)
        for email in ["inexistente@example.com", self.membro.email, self.dono.email, self.outro.email, "invalido"]:
            response = self.client.post(self.url("membros_projeto"), {"email": email})
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(self.projeto.membros.count(), 1)

    def test_remover_membro_e_sair_exigem_post(self):
        url = self.url("remover_membro", usuario_id=self.membro.pk)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), self.url("membros_projeto"))
        self.assertTrue(User.objects.filter(pk=self.membro.pk).exists())
        self.projeto.membros.add(self.membro)
        self.client.force_login(self.membro)
        self.assertEqual(self.client.get(self.url("sair_projeto")).status_code, 405)
        self.assertRedirects(self.client.post(self.url("sair_projeto")), reverse("inicio"))
        self.assertRedirects(self.client.get(self.url("detalhe_projeto")), reverse("inicio"))
        self.assertTrue(Projeto.objects.filter(pk=self.projeto.pk).exists())

    def test_dono_e_estranho_nao_podem_sair(self):
        for user in [self.dono, self.outro]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url("sair_projeto")).status_code, 404)

    def test_crud_backlog_preserva_historias_epicos_sprints_e_rice(self):
        epico = Epico.objects.create(projeto=self.projeto, titulo="Épico")
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint 1", **SPRINT_PERIODO)
        historia = HistoriaUsuario.objects.create(
            titulo="História", product_backlog=self.backlog,
            epico=epico, papel="Pessoa", acao="Agir", beneficio="Benefício",
            contexto="Contexto", evento="Evento", resultado="Resultado",
            # ALTERADO: incluído effort=5. O RICE agora divide pelo campo Effort (requisitos 17
            # e 18), e não mais pelos Story Points; sem Effort o RICE fica "incompleto".
            story_points=5, reach=10, impact=2, confidence=80, effort=5,
        )
        score = historia.rice_score
        self.assertEqual(self.client.get(self.url("editar_product_backlog")).status_code, 200)
        self.assertRedirects(self.client.post(self.url("editar_product_backlog"), {"descricao": "Atualizada"}), self.url("product_backlog"))
        self.assertContains(self.client.get(self.url("product_backlog")), "Atualizada")
        self.assertEqual(self.client.get(self.url("excluir_product_backlog")).status_code, 200)
        self.assertTrue(ProductBacklog.objects.filter(pk=self.backlog.pk).exists())
        response = self.client.post(self.url("excluir_product_backlog"))
        self.assertContains(response, "Não é possível excluir", status_code=409)
        historia.refresh_from_db()
        self.assertEqual(historia.product_backlog_id, self.backlog.pk)
        self.assertEqual(historia.epico_id, epico.pk)
        self.assertIsNone(historia.sprint_backlog_id)
        self.assertEqual(historia.rice_score, score)
        # Movimentar a história para um Sprint não libera a exclusão do PB.
        historia.product_backlog = None
        historia.sprint_backlog = sprint
        historia.save()
        self.assertEqual(self.client.post(self.url("excluir_product_backlog")).status_code, 409)
        historia.refresh_from_db()
        self.assertEqual(historia.sprint_backlog_id, sprint.pk)
        self.assertEqual(historia.rice_score, score)
        historia.delete()
        self.assertRedirects(self.client.post(self.url("excluir_product_backlog")), self.url("detalhe_projeto"))
        self.assertEqual(self.client.get(self.url("product_backlog")).status_code, 404)
        self.assertEqual(self.client.get(self.url("criar_product_backlog")).status_code, 200)
        self.assertFalse(ProductBacklog.objects.filter(projeto=self.projeto).exists())
        self.assertRedirects(self.client.post(self.url("criar_product_backlog"), {"descricao": "Recriado"}), self.url("product_backlog"))
        self.assertEqual(ProductBacklog.objects.get(projeto=self.projeto).descricao, "Recriado")

    def test_backlog_unico_na_view_e_no_banco(self):
        self.assertRedirects(self.client.post(self.url("criar_product_backlog"), {"descricao": "Duplicado"}), self.url("product_backlog"))
        self.assertEqual(ProductBacklog.objects.filter(projeto=self.projeto).count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductBacklog.objects.create(projeto=self.projeto)

    def test_anonimo_redirecionado_em_todas_as_rotas_protegidas(self):
        self.client.logout()
        names = ["detalhe_projeto", "editar_projeto", "excluir_projeto", "membros_projeto",
                 "sair_projeto", "product_backlog", "criar_product_backlog",
                 "editar_product_backlog", "excluir_product_backlog"]
        urls = [self.url(name) for name in names]
        urls += [self.url("remover_membro", usuario_id=self.membro.pk), reverse("inicio"), reverse("criar_projeto"), reverse("logout")]
        for url in urls:
            for method in [self.client.get, self.client.post]:
                self.assertEqual(method(url).status_code, 302)
                self.assertTrue(method(url).url.startswith(reverse("login")))

    def test_csrf_obrigatorio_em_mutacoes(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.dono)
        for name in ["editar_projeto", "excluir_projeto", "membros_projeto", "excluir_product_backlog"]:
            self.assertEqual(client.post(self.url(name), {}).status_code, 403)


    def historia(self, **kwargs):
        dados = {
            "titulo": "História", "product_backlog": self.backlog,
            "papel": "Pessoa", "acao": "Agir", "beneficio": "Benefício",
            "contexto": "Contexto", "evento": "Evento", "resultado": "Resultado",
            # ALTERADO: incluído "effort": 5, pelo mesmo motivo do teste acima. O score
            # esperado continua 320 = (10 x 2 x 80) / 5.
            "story_points": 5, "reach": 10, "impact": 2, "confidence": 80, "effort": 5,
        }
        dados.update(kwargs)
        return HistoriaUsuario.objects.create(**dados)

    def test_membro_gerencia_crud_backlog_vazio(self):
        self.client.force_login(self.membro)
        response = self.client.get(self.url("product_backlog"))
        self.assertContains(response, "Editar Product Backlog")
        self.assertContains(response, "Excluir Product Backlog")
        self.assertEqual(self.client.get(self.url("editar_product_backlog")).status_code, 200)
        self.assertRedirects(self.client.post(self.url("editar_product_backlog"), {"descricao": "Pelo membro"}), self.url("product_backlog"))
        self.assertContains(self.client.get(self.url("product_backlog")), "Pelo membro")
        self.assertEqual(self.client.get(self.url("excluir_product_backlog")).status_code, 200)
        self.assertTrue(ProductBacklog.objects.filter(pk=self.backlog.pk).exists())
        self.assertRedirects(self.client.post(self.url("excluir_product_backlog")), self.url("detalhe_projeto"))
        self.assertFalse(ProductBacklog.objects.filter(projeto=self.projeto).exists())
        self.assertContains(self.client.get(self.url("detalhe_projeto")), "Criar Product Backlog")
        self.assertFalse(ProductBacklog.objects.filter(projeto=self.projeto).exists())
        self.assertEqual(self.client.get(self.url("criar_product_backlog")).status_code, 200)
        self.assertRedirects(self.client.post(self.url("criar_product_backlog"), {"descricao": "Novo"}), self.url("product_backlog"))
        self.assertEqual(ProductBacklog.objects.get(projeto=self.projeto).descricao, "Novo")

    def test_externo_nao_manipula_backlog_por_get_ou_post(self):
        self.client.force_login(self.outro)
        for name in ["product_backlog", "criar_product_backlog", "editar_product_backlog", "excluir_product_backlog"]:
            for method in [self.client.get, self.client.post]:
                self.assertEqual(method(self.url(name), {"descricao": "Invadido"}).status_code, 404)
        self.backlog.refresh_from_db()
        self.assertEqual(self.backlog.descricao, "Original")

    def test_membro_nao_exclui_backlog_com_historia(self):
        historia = self.historia()
        self.client.force_login(self.membro)
        self.assertContains(self.client.post(self.url("excluir_product_backlog")), "Não é possível excluir", status_code=409)
        historia.refresh_from_db()
        self.assertEqual(historia.product_backlog_id, self.backlog.pk)

    def test_protecao_backlog_tambem_em_delete_e_queryset(self):
        historia = self.historia()
        for excluir in [self.backlog.delete, lambda: ProductBacklog.objects.filter(pk=self.backlog.pk).delete()]:
            with self.assertRaises(ProtectedError), transaction.atomic():
                excluir()
        historia.refresh_from_db()
        self.assertEqual(historia.product_backlog_id, self.backlog.pk)

    def test_exclusao_backlog_nao_afeta_outro_projeto(self):
        outro_projeto = Projeto.objects.create(nome="Outro", dono=self.outro)
        outro_pb = ProductBacklog.objects.create(projeto=outro_projeto)
        historia = self.historia(product_backlog=outro_pb)
        self.assertRedirects(self.client.post(self.url("excluir_product_backlog")), self.url("detalhe_projeto"))
        historia.refresh_from_db()
        self.assertEqual(historia.product_backlog_id, outro_pb.pk)
        self.assertEqual(historia.rice_score, 320)

    def test_projeto_exclui_historias_de_product_e_sprint_sem_afetar_outros(self):
        epico = Epico.objects.create(projeto=self.projeto, titulo="Épico")
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        historias = [self.historia(epico=epico), self.historia(product_backlog=None, sprint_backlog=sprint),
                     self.historia(product_backlog=None, sprint_backlog=sprint, epico=epico)]
        outro_projeto = Projeto.objects.create(nome="Outro", dono=self.outro)
        outro_pb = ProductBacklog.objects.create(projeto=outro_projeto)
        outra = self.historia(product_backlog=outro_pb)
        self.assertRedirects(self.client.post(self.url("excluir_projeto")), reverse("inicio"))
        self.assertFalse(HistoriaUsuario.objects.filter(pk__in=[h.pk for h in historias]).exists())
        self.assertFalse(Epico.objects.filter(pk=epico.pk).exists())
        self.assertFalse(SprintBacklog.objects.filter(pk=sprint.pk).exists())
        outra.refresh_from_db()
        self.assertEqual(outra.product_backlog_id, outro_pb.pk)
        self.assertEqual(outra.rice_score, 320)
        self.assertEqual(User.objects.count(), 3)

    def test_exclusao_projeto_queryset_remove_historias_sprint(self):
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        historia = self.historia(product_backlog=None, sprint_backlog=sprint)
        Projeto.objects.filter(pk=self.projeto.pk).delete()
        self.assertFalse(HistoriaUsuario.objects.filter(pk=historia.pk).exists())

    def test_exclusao_projeto_e_atomica(self):
        from unittest.mock import patch
        historia = self.historia()
        original = Projeto.delete

        def falhar(projeto):
            original(projeto)
            raise RuntimeError("Falha simulada após exclusão")

        with patch.object(Projeto, "delete", falhar), self.assertRaises(RuntimeError):
            self.client.post(self.url("excluir_projeto"))
        historia.refresh_from_db()
        self.assertEqual(historia.product_backlog_id, self.backlog.pk)
        self.assertTrue(Projeto.objects.filter(pk=self.projeto.pk).exists())

    def test_hu08_backlog_vazio(self):
        self.assertContains(self.client.get(self.url("product_backlog")), "O Product Backlog está vazio.")

    def test_hu08_dados_das_historias_e_isolamento(self):
        epico = Epico.objects.create(projeto=self.projeto, titulo="Épico visível")
        historia = self.historia(titulo="História visível", epico=epico, moscow="S")
        self.historia(titulo="Sem épico visível", story_points=0)
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        self.historia(titulo="Somente no Sprint", product_backlog=None, sprint_backlog=sprint)
        outro = Projeto.objects.create(nome="Privado", dono=self.outro)
        outro_pb = ProductBacklog.objects.create(projeto=outro)
        self.historia(titulo="História privada", product_backlog=outro_pb)
        for user in [self.dono, self.membro]:
            self.client.force_login(user)
            response = self.client.get(self.url("product_backlog"))
            # ALTERADO: a tela agora mostra "320" (rice_display) em vez de "320.00", e a
            # história com 0 Story Points aparece como "0 pts". Antes, Story Points 0 dava RICE
            # 0.00, porque o Effort era o próprio Story Points.
            for valor in ["História visível", "Story Points", "Should Have", "RICE", "Épico visível", "Sem épico", "320", "0 pts"]:
                self.assertContains(response, valor)
            self.assertNotContains(response, "Somente no Sprint")
            self.assertNotContains(response, "História privada")
            self.assertNotContains(response, "O Product Backlog está vazio.")
            self.assertIn(historia, response.context["historias"])

    def test_remover_membro_preserva_historias_e_conta(self):
        historia = self.historia()
        self.assertRedirects(self.client.post(self.url("remover_membro", usuario_id=self.membro.pk)), self.url("membros_projeto"))
        historia.refresh_from_db()
        self.assertEqual(historia.product_backlog_id, self.backlog.pk)
        self.assertTrue(User.objects.filter(pk=self.membro.pk).exists())
        self.client.force_login(self.membro)
        self.assertEqual(self.client.post(self.url("editar_product_backlog"), {"descricao": "Negada"}).status_code, 404)

    def test_modelo_rejeita_dois_backlogs_e_sem_backlog(self):
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        with self.assertRaises(ValidationError):
            self.historia(sprint_backlog=sprint)
        with self.assertRaises(ValidationError):
            self.historia(product_backlog=None)

    def test_banco_rejeita_dois_backlogs_em_update_e_bulk_create(self):
        historia = self.historia()
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoriaUsuario.objects.filter(pk=historia.pk).update(sprint_backlog=sprint)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoriaUsuario.objects.bulk_create([HistoriaUsuario(product_backlog=self.backlog, sprint_backlog=sprint)])

    def test_banco_rejeita_novas_historias_orfas_e_desvinculacao(self):
        historia = self.historia()
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoriaUsuario.objects.bulk_create([HistoriaUsuario(titulo="Órfã")])
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoriaUsuario.objects.filter(pk=historia.pk).update(product_backlog=None)

    def test_movimentacao_entre_backlogs_preserva_rice_e_epico(self):
        epico = Epico.objects.create(projeto=self.projeto, titulo="Épico")
        historia = self.historia(epico=epico)
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        historia.product_backlog = None
        historia.sprint_backlog = sprint
        historia.save(update_fields=["product_backlog", "sprint_backlog"])
        historia.refresh_from_db()
        self.assertEqual(historia.sprint_backlog_id, sprint.pk)
        self.assertEqual(historia.epico_id, epico.pk)
        self.assertEqual(historia.rice_score, 320)
        HistoriaUsuario.objects.filter(pk=historia.pk).update(sprint_backlog=None, product_backlog=self.backlog)
        historia.refresh_from_db()
        self.assertEqual(historia.product_backlog_id, self.backlog.pk)
        self.assertIsNone(historia.sprint_backlog_id)

    def test_epico_e_backlog_de_projetos_diferentes_rejeitados(self):
        outro = Projeto.objects.create(nome="Outro", dono=self.outro)
        epico = Epico.objects.create(projeto=outro, titulo="Outro épico")
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        for dados in [{"epico": epico}, {"epico": epico, "product_backlog": None, "sprint_backlog": sprint}]:
            with self.assertRaises(ValidationError):
                self.historia(**dados)
        historia = self.historia()
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoriaUsuario.objects.filter(pk=historia.pk).update(epico=epico)
        historia.epico = epico
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoriaUsuario.objects.bulk_update([historia], ["epico"])

    def test_banco_rejeita_trocar_projeto_de_backlog_ou_epico_incompativel(self):
        outro = Projeto.objects.create(nome="Outro", dono=self.outro)
        epico = Epico.objects.create(projeto=self.projeto, titulo="Épico")
        self.historia(epico=epico)
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        self.historia(product_backlog=None, sprint_backlog=sprint, epico=epico)
        for objeto in [self.backlog, sprint, epico]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                type(objeto).objects.filter(pk=objeto.pk).update(projeto=outro)

    def test_save_parcial_valida_estado_persistido(self):
        historia = self.historia()
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        historia.product_backlog = None
        historia.sprint_backlog = sprint
        with self.assertRaises(ValidationError):
            historia.save(update_fields=["sprint_backlog"])

    def test_exclusoes_com_csrf_valido_e_confirmacao_sem_mutacao(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.dono)
        for name in ["excluir_product_backlog", "excluir_projeto"]:
            response = client.get(self.url(name))
            self.assertContains(response, "Confirmar exclusão")
            self.assertTrue(Projeto.objects.filter(pk=self.projeto.pk).exists())
            self.assertEqual(client.post(self.url(name)).status_code, 403)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(self.url("excluir_product_backlog"), {"csrfmiddlewaretoken": token}).status_code, 302)
        self.assertEqual(client.post(self.url("excluir_projeto"), {"csrfmiddlewaretoken": token}).status_code, 302)


    def test_sprint_com_historias_volta_ao_product_backlog_na_exclusao(self):
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint", **SPRINT_PERIODO)
        historia = self.historia(product_backlog=None, sprint_backlog=sprint)
        sprint.delete()
        historia.refresh_from_db()
        self.assertEqual(historia.product_backlog_id, self.backlog.pk)
        self.assertIsNone(historia.sprint_backlog_id)


# Migrações 0004/0005: dados antigos (história sem backlog, vínculos entre projetos) são
# tratados sem perder registros
class MigracaoIntegridadeTests(TransactionTestCase):
    antiga = ("core", "0003_alter_projeto_dono")
    # ALTERADO: de 0005 para 0007. Os testes usam o model atual (que tem Effort,
    # critérios de aceitação e período de Sprint)
    # depois de migrar, então o banco precisa chegar na última migration.
    atual = ("core", "0007_criterioaceitacao_periodo_sprint")

    def setUp(self):
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        executor.migrate([self.antiga])
        self.apps_antigas = executor.loader.project_state([self.antiga]).apps
        self.dono = User.objects.create_user("dono_legado")
        self.ProjetoAntigo = self.apps_antigas.get_model("core", "Projeto")
        self.HistoriaAntiga = self.apps_antigas.get_model("core", "HistoriaUsuario")
        self.projeto = self.ProjetoAntigo.objects.create(nome="Legado", dono_id=self.dono.pk)
        self.pb = self.apps_antigas.get_model("core", "ProductBacklog").objects.create(projeto=self.projeto)

    def migrar(self):
        from django.db.migrations.executor import MigrationExecutor
        MigrationExecutor(connection).migrate([self.atual])

    def tearDown(self):
        self.migrar()
        super().tearDown()

    def test_legados_sem_identificacao_preservados_e_exclusao_por_epico(self):
        EpicoAntigo = self.apps_antigas.get_model("core", "Epico")
        epico = EpicoAntigo.objects.create(projeto=self.projeto, titulo="Legado")
        historia_epico = self.HistoriaAntiga.objects.create(titulo="Só épico", epico=epico)
        sem_identificacao = self.HistoriaAntiga.objects.create(titulo="Sem identificação")
        self.migrar()
        historia = HistoriaUsuario.objects.get(pk=sem_identificacao.pk)
        self.assertIsNone(historia.product_backlog_id)
        self.assertIsNone(historia.sprint_backlog_id)
        self.assertIsNone(historia.epico_id)
        self.client.force_login(self.dono)
        url = reverse("excluir_projeto", args=[self.projeto.pk])
        self.assertRedirects(self.client.post(url), reverse("inicio"))
        self.assertFalse(HistoriaUsuario.objects.filter(pk=historia_epico.pk).exists())
        self.assertTrue(HistoriaUsuario.objects.filter(pk=sem_identificacao.pk).exists())

    def test_migracao_recusa_dois_backlogs_sem_escolher_destino(self):
        SprintAntigo = self.apps_antigas.get_model("core", "SprintBacklog")
        sprint = SprintAntigo.objects.create(projeto=self.projeto, nome="Sprint")
        historia = self.HistoriaAntiga.objects.create(product_backlog=self.pb, sprint_backlog=sprint)
        try:
            with self.assertRaisesMessage(RuntimeError, "Histórias com vínculos inconsistentes"):
                self.migrar()
            historia.refresh_from_db()
            self.assertEqual(historia.product_backlog_id, self.pb.pk)
            self.assertEqual(historia.sprint_backlog_id, sprint.pk)
        finally:
            historia.delete()
            sprint.delete()

    def test_migracao_recusa_vinculos_entre_projetos(self):
        outro = self.ProjetoAntigo.objects.create(nome="Outro", dono_id=self.dono.pk)
        EpicoAntigo = self.apps_antigas.get_model("core", "Epico")
        epico = EpicoAntigo.objects.create(projeto=outro, titulo="Outro épico")
        historia = self.HistoriaAntiga.objects.create(product_backlog=self.pb, epico=epico)
        try:
            with self.assertRaisesMessage(RuntimeError, "Histórias com vínculos inconsistentes"):
                self.migrar()
            historia.refresh_from_db()
            self.assertEqual(historia.epico_id, epico.pk)
        finally:
            historia.delete()

# ======================================================================
# ADICIONADO: testes de Story Points, MoSCoW e RICE (HU18-HU21; requisitos 14-19) e do CRUD
# de histórias (HU12-HU14), de épicos (HU15-HU16) e do vínculo entre eles (HU17).
# ======================================================================
class PriorizacaoTests(TestCase):
    def setUp(self):
        dono = User.objects.create_user("dono_rice", email="dono_rice@exemplo.com", password="Senha-forte-123")
        projeto = Projeto.objects.create(nome="Projeto A", dono=dono)
        self.backlog = ProductBacklog.objects.create(projeto=projeto)

    def nova(self, **campos):
        dados = dict(titulo="Filtrar por épico", papel="analista", acao="filtrar histórias", beneficio="achar rápido")
        dados.update(campos)
        return HistoriaUsuario.objects.create(product_backlog=self.backlog, **dados)

    def test_hu21_exemplo(self):
        h = self.nova(reach=500, impact=2.0, confidence=80, effort=5)
        self.assertEqual(h.rice_score, 16000)
        self.assertEqual(h.rice_display, "16000")

    def test_hu20_effort_independente_dos_story_points(self):
        h = self.nova(reach=500, impact=2.0, confidence=80, effort=5, story_points=13)
        h.story_points = 8
        h.save()
        self.assertEqual(h.rice_score, 16000)

    def test_hu20_rice_incompleto(self):
        h = self.nova(reach=500, impact=2.0, confidence=80)
        self.assertIsNone(h.rice_score)
        self.assertEqual(h.rice_display, "RICE incompleto")

    def test_hu21_effort_zero_nao_calculavel(self):
        h = self.nova(reach=500, impact=2.0, confidence=80, effort=0)
        self.assertIsNone(h.rice_score)
        self.assertEqual(h.rice_display, "não calculável")

    def test_hu21_recalcula_ao_mudar_campo(self):
        h = self.nova(reach=500, impact=2.0, confidence=80, effort=5)
        h.confidence = 50
        h.save()
        self.assertEqual(HistoriaUsuario.objects.get(pk=h.pk).rice_score, 10000)

    def test_historia_nova_sem_estimativa_nem_etiqueta(self):
        h = self.nova()
        self.assertIsNone(h.story_points)
        self.assertEqual(h.moscow, "")
        self.assertEqual(h.story_points_display, "sem estimativa")

    def test_hu18_hu19_hu20_valores_fora_da_escala_recusados_no_banco(self):
        for campos in ({"story_points": 4}, {"story_points": 60}, {"moscow": "X"},
                       {"confidence": 70}, {"impact": 4.0}, {"effort": 4}):
            with self.subTest(campos=campos), self.assertRaises(IntegrityError), transaction.atomic():
                self.nova(**campos)
        self.assertEqual(HistoriaUsuario.objects.count(), 0)


class HistoriaEpicoViewsTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("ana", email="ana@exemplo.com", password="Senha-forte-123")
        self.membro = User.objects.create_user("bia", email="bia@exemplo.com", password="Senha-forte-123")
        self.estranho = User.objects.create_user("caio", email="caio@exemplo.com", password="Senha-forte-123")
        self.projeto = Projeto.objects.create(nome="Projeto A", dono=self.dono)
        self.projeto.membros.add(self.membro)
        ProductBacklog.objects.create(projeto=self.projeto)
        self.outro = Projeto.objects.create(nome="Projeto B", dono=self.estranho)
        self.client.force_login(self.dono)

    def url(self, nome, *args):
        return reverse(nome, args=[self.projeto.pk, *args])

    def dados(self, **extra):
        d = {"titulo": "Exportar PDF", "papel": "PO", "acao": "exportar o backlog", "beneficio": "compartilhar",
             "story_points": "13", "moscow": "S", "reach": "500", "impact": "2.0", "confidence": "80", "effort": "5"}
        d.update(extra)
        return d

    def test_exige_login(self):
        self.client.logout()
        resp = self.client.get(self.url("historia_lista"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp["Location"])

    def test_hu12_criar_historia_nasce_no_product_backlog(self):
        resp = self.client.post(self.url("historia_criar"), self.dados())
        self.assertRedirects(resp, self.url("historia_lista"))
        h = HistoriaUsuario.objects.get()
        self.assertEqual(h.product_backlog.projeto, self.projeto)
        self.assertEqual(h.rice_score, 16000)
        self.assertContains(self.client.get(self.url("product_backlog")), "Exportar PDF")

    def test_hu12_sem_product_backlog_pede_para_criar(self):
        ProductBacklog.objects.filter(projeto=self.projeto).delete()
        resp = self.client.get(self.url("historia_criar"))
        self.assertRedirects(resp, reverse("criar_product_backlog", args=[self.projeto.pk]))

    def test_hu12_campos_obrigatorios(self):
        resp = self.client.post(self.url("historia_criar"), self.dados(titulo="", papel=""))
        self.assertContains(resp, "O título é obrigatório.")
        self.assertEqual(HistoriaUsuario.objects.count(), 0)

    def test_hu18_hu20_fora_da_escala_no_formulario(self):
        for campo, valor, msg in (("story_points", "4", "Story Points aceita apenas"), ("effort", "4", "Effort aceita apenas")):
            resp = self.client.post(self.url("historia_criar"), self.dados(**{campo: valor}))
            self.assertContains(resp, msg)
        self.assertEqual(HistoriaUsuario.objects.count(), 0)

    def test_hu13_hu14_editar_e_excluir_historia(self):
        self.client.post(self.url("historia_criar"), self.dados())
        h = HistoriaUsuario.objects.get()
        self.client.post(self.url("historia_editar", h.pk), self.dados(titulo="Exportar backlog", effort="0"))
        h.refresh_from_db()
        self.assertEqual(h.titulo, "Exportar backlog")
        self.assertEqual(h.rice_display, "não calculável")
        self.client.get(self.url("historia_excluir", h.pk))  # tela de confirmação não apaga
        self.assertTrue(HistoriaUsuario.objects.exists())
        self.client.post(self.url("historia_excluir", h.pk))
        self.assertFalse(HistoriaUsuario.objects.exists())

    def test_hu15_hu16_hu17_crud_epico_e_vinculo(self):
        self.client.post(self.url("epico_criar"), {"titulo": "Priorização", "descricao": "RICE e MoSCoW"})
        epico = Epico.objects.get()
        self.client.post(self.url("historia_criar"), self.dados(epico=str(epico.pk)))
        h = HistoriaUsuario.objects.get()
        self.assertEqual(h.epico, epico)
        self.assertContains(self.client.get(self.url("epico_detalhe", epico.pk)), "Exportar PDF")
        self.client.post(self.url("epico_editar", epico.pk), {"titulo": "Priorização RICE", "descricao": ""})
        self.assertContains(self.client.get(self.url("historia_detalhe", h.pk)), "Priorização RICE")
        self.client.post(self.url("historia_editar", h.pk), self.dados(epico=""))
        h.refresh_from_db()
        self.assertIsNone(h.epico)
        self.client.post(self.url("historia_editar", h.pk), self.dados(epico=str(epico.pk)))
        self.client.post(self.url("epico_excluir", epico.pk))
        h.refresh_from_db()
        self.assertIsNone(h.epico)
        self.assertFalse(Epico.objects.exists())

    def test_hu15_epico_sem_nome(self):
        resp = self.client.post(self.url("epico_criar"), {"titulo": "", "descricao": ""})
        self.assertContains(resp, "O nome do épico é obrigatório.")
        self.assertFalse(Epico.objects.exists())

    def test_hu17_nao_liga_epico_de_outro_projeto(self):
        epico_outro = Epico.objects.create(projeto=self.outro, titulo="Outro")
        resp = self.client.post(self.url("historia_criar"), self.dados(epico=str(epico_outro.pk)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(HistoriaUsuario.objects.count(), 0)

    def test_membro_opera_historias_e_epicos(self):
        self.client.force_login(self.membro)
        self.assertRedirects(self.client.post(self.url("historia_criar"), self.dados()), self.url("historia_lista"))
        self.assertRedirects(self.client.post(self.url("epico_criar"), {"titulo": "Do membro"}), self.url("epico_lista"))

    def test_estranho_nao_acessa_historias_nem_epicos(self):
        self.client.post(self.url("historia_criar"), self.dados())
        h = HistoriaUsuario.objects.get()
        self.client.force_login(self.estranho)
        for nome, args in (("historia_lista", ()), ("historia_detalhe", (h.pk,)), ("epico_lista", ())):
            self.assertEqual(self.client.get(self.url(nome, *args)).status_code, 404)
        self.assertEqual(self.client.post(self.url("historia_excluir", h.pk)).status_code, 404)
        self.assertTrue(HistoriaUsuario.objects.exists())
