from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from .models import Projeto, ProductBacklog, HistoriaUsuario, Epico, SprintBacklog


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
        for name in ["detalhe_projeto", "membros_projeto", "product_backlog"]:
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
            for name in ["editar_projeto", "excluir_projeto", "criar_product_backlog",
                         "editar_product_backlog", "excluir_product_backlog"]:
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
        self.assertEqual(self.client.get(self.url("detalhe_projeto")).status_code, 404)
        self.assertTrue(Projeto.objects.filter(pk=self.projeto.pk).exists())

    def test_dono_e_estranho_nao_podem_sair(self):
        for user in [self.dono, self.outro]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url("sair_projeto")).status_code, 404)

    def test_crud_backlog_preserva_historias_epicos_sprints_e_rice(self):
        epico = Epico.objects.create(projeto=self.projeto, titulo="Épico")
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint 1")
        historia = HistoriaUsuario.objects.create(
            titulo="História", product_backlog=self.backlog, sprint_backlog=sprint,
            epico=epico, papel="Pessoa", acao="Agir", beneficio="Benefício",
            contexto="Contexto", evento="Evento", resultado="Resultado",
            story_points=5, reach=10, impact=2, confidence=80,
        )
        score = historia.rice_score
        self.assertEqual(self.client.get(self.url("editar_product_backlog")).status_code, 200)
        self.assertRedirects(self.client.post(self.url("editar_product_backlog"), {"descricao": "Atualizada"}), self.url("product_backlog"))
        self.assertContains(self.client.get(self.url("product_backlog")), "Atualizada")
        self.assertEqual(self.client.get(self.url("excluir_product_backlog")).status_code, 200)
        self.assertTrue(ProductBacklog.objects.filter(pk=self.backlog.pk).exists())
        self.assertRedirects(self.client.post(self.url("excluir_product_backlog")), self.url("detalhe_projeto"))
        historia.refresh_from_db()
        self.assertIsNone(historia.product_backlog_id)
        self.assertEqual(historia.epico_id, epico.pk)
        self.assertEqual(historia.sprint_backlog_id, sprint.pk)
        self.assertEqual(historia.rice_score, score)
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
