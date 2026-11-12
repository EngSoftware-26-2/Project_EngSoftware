from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from datetime import date, timedelta

from .models import Projeto, ProductBacklog, HistoriaUsuario, Epico, SprintBacklog, CriterioAceitacao


def dia(n):
    """Data de hoje + n dias, no formato do formulário (AAAA-MM-DD)."""
    return (date.today() + timedelta(days=n)).isoformat()


# Período de Sprint em andamento, relativo a hoje. Com datas fixas, o Sprint dos testes
# passaria a ser encerrado sozinho quando a data de fim ficasse no passado.
_HOJE = date.today()
SPRINT_PERIODO = {
    "data_inicio": _HOJE - timedelta(days=2),
    "data_fim": _HOJE + timedelta(days=7),
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


# HU01 - Regras dos campos do cadastro (nome, e-mail e senha), dicas e erros embaixo do campo
class CadastroRegrasTests(TestCase):
    SENHA = "SenhaForte!482"

    def cadastrar(self, **dados):
        base = {"nome": "Ana Souza", "email": "ana@example.com",
                "senha": self.SENHA, "confirmar_senha": self.SENHA}
        base.update(dados)
        if "senha" in dados and "confirmar_senha" not in dados:
            base["confirmar_senha"] = dados["senha"]
        return self.client.post(reverse("cadastro"), base)

    def erros(self, response, campo):
        return response.context["form"].errors.get(campo, [])

    def test_nome_limites_de_tamanho(self):
        for nome, aceito in [("Al", False), ("Ana", True), ("A" + "a" * 49, True), ("A" + "a" * 50, False)]:
            with self.subTest(tamanho=len(nome)):
                User.objects.all().delete()
                response = self.cadastrar(nome=nome)
                if aceito:
                    self.assertRedirects(response, reverse("inicio"))
                    self.client.logout()
                else:
                    self.assertTrue(self.erros(response, "nome"))
                    self.assertFalse(User.objects.exists())

    def test_nome_recusa_numero_minuscula_simbolo_e_espaco_duplo(self):
        casos = {
            "Ana 2": "O nome não pode conter números.",
            "ana Souza": "O nome deve começar com letra maiúscula.",
            "Ana@Souza": "O nome só pode ter letras, espaços, hífen (-) e apóstrofo (').",
            "Ana  Souza": "O nome não pode ter espaços duplos.",
        }
        for nome, mensagem in casos.items():
            with self.subTest(nome=nome):
                response = self.cadastrar(nome=nome)
                self.assertIn(mensagem, self.erros(response, "nome"))
                self.assertFalse(User.objects.exists())

    def test_nome_aceita_acento_hifen_e_apostrofo(self):
        response = self.cadastrar(nome="João D'Ávila-Conceição")
        self.assertRedirects(response, reverse("inicio"))
        self.assertEqual(User.objects.get().first_name, "João D'Ávila-Conceição")

    def test_senha_recusa_cada_regra_faltando(self):
        casos = {
            "Sen!a12": "A senha deve ter entre 8 e 64 caracteres.",
            "senhaforte!482": "A senha precisa de pelo menos uma letra maiúscula.",
            "SENHAFORTE!482": "A senha precisa de pelo menos uma letra minúscula.",
            "SenhaForte!abc": "A senha precisa de pelo menos um número.",
            "SenhaForte482": "A senha precisa de pelo menos um símbolo (ex.: ! @ # $).",
            "Aa1!" + "x" * 61: "A senha deve ter entre 8 e 64 caracteres.",
        }
        for senha, mensagem in casos.items():
            with self.subTest(senha=senha):
                response = self.cadastrar(senha=senha)
                self.assertIn(mensagem, self.erros(response, "senha"))
                self.assertFalse(User.objects.exists())

    def test_senha_nos_limites_de_8_e_64_e_aceita(self):
        for senha in ["Sen!a123", "Aa1!" + "x" * 60]:
            with self.subTest(tamanho=len(senha)):
                User.objects.all().delete()
                self.assertRedirects(self.cadastrar(senha=senha), reverse("inicio"))
                self.client.logout()

    def test_senha_parecida_com_o_email_e_recusada(self):
        response = self.cadastrar(email="robertacarvalho@example.com", senha="Robertacarvalho!1")
        self.assertTrue(self.erros(response, "senha"))
        self.assertFalse(User.objects.exists())

    def test_email_invalido_e_longo_demais(self):
        for email in ["ana.example.com", "a" * 90 + "@example.com"]:
            with self.subTest(email=email):
                response = self.cadastrar(email=email)
                self.assertTrue(self.erros(response, "email"))
                self.assertFalse(User.objects.exists())

    def test_tela_mostra_dicas_e_erro_embaixo_do_campo(self):
        response = self.client.get(reverse("cadastro"))
        self.assertContains(response, "3 a 50 letras, iniciar com maiúscula")
        self.assertContains(response, "com maiúscula, minúscula, número e símbolo")
        self.assertContains(response, "novalidate")

        html = self.cadastrar(nome="Ana 2").content.decode()
        campo_nome = html.index('id="id_nome"')
        erro = html.index("O nome não pode conter números.")
        campo_email = html.index('id="id_email"')
        self.assertLess(campo_nome, erro)
        self.assertLess(erro, campo_email)
        self.assertIn("campo-com-erro", html)

    def test_login_mostra_erro_geral_e_dica(self):
        response = self.client.post(reverse("login"), {"email": "ninguem@example.com", "senha": "x"})
        self.assertContains(response, "E-mail ou senha inválidos.")
        self.assertContains(response, "O e-mail usado no cadastro.")

    def test_conta_antiga_fora_das_regras_continua_entrando(self):
        User.objects.create_user("velho", email="velho@example.com", password="senhaantiga", first_name="x")
        response = self.client.post(reverse("login"), {"email": "velho@example.com", "senha": "senhaantiga"})
        self.assertRedirects(response, reverse("inicio"))


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
            # Incluído effort=5. O RICE agora divide pelo campo Effort (requisitos 17
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
            # Incluído "effort": 5, pelo mesmo motivo do teste acima. O score
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
            # A tela agora mostra "320" (rice_display) em vez de "320.00", e a
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


# ======================================================================
# Testes dos ajustes nas telas de membros e de detalhe do projeto (HU22, HU24).
# ======================================================================
class AjustesMembrosTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("lia", email="lia@exemplo.com", password="Senha-forte-123")
        self.membro = User.objects.create_user("mel", email="mel@exemplo.com", password="Senha-forte-123")
        self.projeto = Projeto.objects.create(nome="Projeto J", dono=self.dono)
        self.projeto.membros.add(self.membro)

    def test_hu22_mensagem_quando_nao_existe_conta(self):
        self.client.force_login(self.dono)
        resp = self.client.post(reverse("membros_projeto", args=[self.projeto.pk]), {"email": "ninguem@exemplo.com"})
        self.assertContains(resp, "Nenhuma conta com este e-mail.")
        self.assertEqual(self.projeto.membros.count(), 1)

    def test_hu24_sair_pelo_detalhe_pede_confirmacao(self):
        self.client.force_login(self.membro)
        resp = self.client.get(reverse("detalhe_projeto", args=[self.projeto.pk]))
        self.assertContains(resp, "return confirm('Deseja sair deste projeto?')")


# Migrações 0004/0005: dados antigos (história sem backlog, vínculos entre projetos) são
# tratados sem perder registros
class MigracaoIntegridadeTests(TransactionTestCase):
    antiga = ("core", "0003_alter_projeto_dono")
    # Os testes usam o model atual (que tem Effort, critérios de aceitação, período de
    # Sprint, situação, responsável e encerramento do Sprint) depois de migrar, então o banco precisa chegar na
    # última migration.
    atual = ("core", "0009_sprint_encerramento")

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
# Testes de Story Points, MoSCoW e RICE (HU18-HU21; requisitos 14-19) e do CRUD
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


# ======================================================================
# Testes do CRUD de critérios de aceitação (requisitos 12 e 13; HU12 critério 3
# e HU13).
# ======================================================================
class CriterioAceitacaoTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("dani", email="dani@exemplo.com", password="Senha-forte-123")
        self.membro = User.objects.create_user("edu", email="edu@exemplo.com", password="Senha-forte-123")
        self.estranho = User.objects.create_user("fabi", email="fabi@exemplo.com", password="Senha-forte-123")
        self.projeto = Projeto.objects.create(nome="Projeto C", dono=self.dono)
        self.projeto.membros.add(self.membro)
        backlog = ProductBacklog.objects.create(projeto=self.projeto)
        self.historia = HistoriaUsuario.objects.create(
            titulo="Login", product_backlog=backlog, papel="usuário", acao="entrar", beneficio="ver projetos")
        self.client.force_login(self.dono)

    def url(self, nome, *args):
        return reverse(nome, args=[self.projeto.pk, self.historia.pk, *args])

    def criterio(self, **extra):
        d = {"dado": "tenho conta", "quando": "digito e-mail e senha certos", "entao": "entro no sistema"}
        d.update(extra)
        return d

    def test_criar_varios_criterios_e_listar_na_historia(self):
        self.assertRedirects(self.client.post(self.url("criterio_criar"), self.criterio()), self.url("historia_detalhe"))
        self.client.post(self.url("criterio_criar"), self.criterio(dado="errei a senha", quando="tento entrar", entao="vejo um aviso"))
        self.assertEqual(self.historia.criterios_aceitacao.count(), 2)
        resp = self.client.get(self.url("historia_detalhe"))
        self.assertContains(resp, "digito e-mail e senha certos")
        self.assertContains(resp, "errei a senha")

    def test_requisito13_formato_completo_obrigatorio(self):
        resp = self.client.post(self.url("criterio_criar"), self.criterio(quando=""))
        self.assertContains(resp, "Preencha o Quando")
        self.assertFalse(CriterioAceitacao.objects.exists())

    def test_hu13_editar_e_excluir_criterio(self):
        c = CriterioAceitacao.objects.create(historia_usuario=self.historia, **self.criterio())
        self.client.post(self.url("criterio_editar", c.pk), self.criterio(entao="vejo meus projetos"))
        c.refresh_from_db()
        self.assertEqual(c.entao, "vejo meus projetos")
        self.client.get(self.url("criterio_excluir", c.pk))  # tela de confirmação não apaga
        self.assertTrue(CriterioAceitacao.objects.filter(pk=c.pk).exists())
        self.assertRedirects(self.client.post(self.url("criterio_excluir", c.pk)), self.url("historia_detalhe"))
        self.assertFalse(CriterioAceitacao.objects.filter(pk=c.pk).exists())

    def test_hu12_primeiro_criterio_na_criacao_da_historia(self):
        dados = {"titulo": "Sair", "papel": "usuário", "acao": "sair", "beneficio": "proteger a conta",
                 "criterio_dado": "estou logado", "criterio_quando": "clico em Sair",
                 "criterio_entao": "volto para o login"}
        self.client.post(reverse("historia_criar", args=[self.projeto.pk]), dados)
        nova = HistoriaUsuario.objects.get(titulo="Sair")
        self.assertEqual(nova.criterios_aceitacao.get().quando, "clico em Sair")

    def test_hu12_primeiro_criterio_incompleto_nao_cria_historia(self):
        dados = {"titulo": "Sair", "papel": "usuário", "acao": "sair", "beneficio": "proteger a conta",
                 "criterio_dado": "estou logado"}
        resp = self.client.post(reverse("historia_criar", args=[self.projeto.pk]), dados)
        self.assertContains(resp, "preencha Dado, Quando e Então")
        self.assertFalse(HistoriaUsuario.objects.filter(titulo="Sair").exists())

    def test_excluir_historia_apaga_os_criterios(self):
        CriterioAceitacao.objects.create(historia_usuario=self.historia, **self.criterio())
        self.client.post(reverse("historia_excluir", args=[self.projeto.pk, self.historia.pk]))
        self.assertFalse(CriterioAceitacao.objects.exists())

    def test_membro_gerencia_criterios(self):
        self.client.force_login(self.membro)
        self.assertRedirects(self.client.post(self.url("criterio_criar"), self.criterio()), self.url("historia_detalhe"))

    def test_estranho_nao_acessa_criterios(self):
        c = CriterioAceitacao.objects.create(historia_usuario=self.historia, **self.criterio())
        self.client.force_login(self.estranho)
        self.assertEqual(self.client.get(self.url("criterio_criar")).status_code, 404)
        self.assertEqual(self.client.post(self.url("criterio_excluir", c.pk)).status_code, 404)
        self.assertTrue(CriterioAceitacao.objects.filter(pk=c.pk).exists())

    def test_criterio_de_outra_historia_nao_e_acessado_por_esta(self):
        outra = HistoriaUsuario.objects.create(
            titulo="Outra", product_backlog=self.historia.product_backlog, papel="a", acao="b", beneficio="c")
        c = CriterioAceitacao.objects.create(historia_usuario=outra, **self.criterio())
        self.assertEqual(self.client.get(self.url("criterio_editar", c.pk)).status_code, 404)


# ======================================================================
# Testes do CRUD de Sprint Backlogs (requisito 6; HU09 e HU10).
# ======================================================================
class SprintBacklogViewsTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("gil", email="gil@exemplo.com", password="Senha-forte-123")
        self.membro = User.objects.create_user("hel", email="hel@exemplo.com", password="Senha-forte-123")
        self.estranho = User.objects.create_user("ivo", email="ivo@exemplo.com", password="Senha-forte-123")
        self.projeto = Projeto.objects.create(nome="Projeto S", dono=self.dono)
        self.projeto.membros.add(self.membro)
        self.backlog = ProductBacklog.objects.create(projeto=self.projeto)
        self.client.force_login(self.dono)

    def url(self, nome, *args):
        return reverse(nome, args=[self.projeto.pk, *args])

    def dados(self, **extra):
        # Datas relativas a hoje: a data de início não pode ser no passado.
        d = {"nome": "Sprint 1", "data_inicio": dia(0), "data_fim": dia(11)}
        d.update(extra)
        return d

    def test_hu09_criar_sprint_vazio(self):
        resp = self.client.post(self.url("sprint_criar"), self.dados())
        sprint = SprintBacklog.objects.get()
        self.assertRedirects(resp, self.url("sprint_detalhe", sprint.pk))
        self.assertEqual(sprint.projeto, self.projeto)
        self.assertEqual(sprint.historias.count(), 0)
        self.assertContains(self.client.get(self.url("sprint_lista")), "Sprint 1")

    def test_hu09_data_fim_antes_do_inicio(self):
        resp = self.client.post(self.url("sprint_criar"), self.dados(data_fim=dia(-1)))
        self.assertContains(resp, "A data de fim não pode ser anterior à data de início.")
        self.assertFalse(SprintBacklog.objects.exists())

    def test_hu09_campos_obrigatorios(self):
        resp = self.client.post(self.url("sprint_criar"), {"nome": "", "data_inicio": "", "data_fim": ""})
        self.assertContains(resp, "O nome do Sprint Backlog é obrigatório.")
        self.assertContains(resp, "Informe a data de início.")
        self.assertFalse(SprintBacklog.objects.exists())

    def test_hu09_varios_sprints_no_mesmo_projeto(self):
        self.client.post(self.url("sprint_criar"), self.dados())
        self.client.post(self.url("sprint_criar"), self.dados(nome="Sprint 2", data_inicio=dia(14), data_fim=dia(25)))
        self.assertEqual(self.projeto.sprint_backlogs.count(), 2)

    def test_hu10_editar_sprint(self):
        sprint = SprintBacklog.objects.create(projeto=self.projeto, **SPRINT_PERIODO, nome="Sprint 1")
        # Sprint em andamento: a data de início antiga (no passado) continua valendo.
        inicio = SPRINT_PERIODO["data_inicio"].isoformat()
        self.client.post(self.url("sprint_editar", sprint.pk), self.dados(nome="Sprint Um", data_inicio=inicio, data_fim=dia(15)))
        sprint.refresh_from_db()
        self.assertEqual(sprint.nome, "Sprint Um")
        self.assertEqual(sprint.data_fim.isoformat(), dia(15))

    def test_hu10_excluir_sprint_devolve_historias_ao_product_backlog(self):
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint 1", **SPRINT_PERIODO)
        h = HistoriaUsuario.objects.create(titulo="No sprint", sprint_backlog=sprint, papel="a", acao="b", beneficio="c")
        self.client.get(self.url("sprint_excluir", sprint.pk))  # tela de confirmação não apaga
        self.assertTrue(SprintBacklog.objects.filter(pk=sprint.pk).exists())
        self.assertRedirects(self.client.post(self.url("sprint_excluir", sprint.pk)), self.url("sprint_lista"))
        h.refresh_from_db()
        self.assertFalse(SprintBacklog.objects.exists())
        self.assertEqual(h.product_backlog, self.backlog)
        self.assertIsNone(h.sprint_backlog)

    def test_detalhe_mostra_historias_e_total_de_pontos(self):
        sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint 1", **SPRINT_PERIODO)
        HistoriaUsuario.objects.create(titulo="A", sprint_backlog=sprint, papel="a", acao="b", beneficio="c", story_points=5)
        HistoriaUsuario.objects.create(titulo="B", sprint_backlog=sprint, papel="a", acao="b", beneficio="c", story_points=8)
        resp = self.client.get(self.url("sprint_detalhe", sprint.pk))
        self.assertContains(resp, "13 Story Points")

    def test_membro_opera_e_estranho_nao_acessa(self):
        self.client.force_login(self.membro)
        self.client.post(self.url("sprint_criar"), self.dados())
        sprint = SprintBacklog.objects.get()
        self.client.force_login(self.estranho)
        self.assertEqual(self.client.get(self.url("sprint_lista")).status_code, 404)
        self.assertEqual(self.client.post(self.url("sprint_excluir", sprint.pk)).status_code, 404)
        self.assertTrue(SprintBacklog.objects.exists())


# ======================================================================
# Testes de mover história entre backlogs (requisito 8; HU11).
# ======================================================================
class MoverHistoriaTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("jade", email="jade@exemplo.com", password="Senha-forte-123")
        self.estranho = User.objects.create_user("kai", email="kai@exemplo.com", password="Senha-forte-123")
        self.projeto = Projeto.objects.create(nome="Projeto M", dono=self.dono)
        self.backlog = ProductBacklog.objects.create(projeto=self.projeto)
        self.sprint1 = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint 1", **SPRINT_PERIODO)
        self.sprint2 = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint 2", **SPRINT_PERIODO)
        self.historia = HistoriaUsuario.objects.create(
            titulo="Mover", product_backlog=self.backlog, papel="a", acao="b", beneficio="c")
        self.client.force_login(self.dono)

    def mover(self, destino, historia=None):
        h = historia or self.historia
        return self.client.post(reverse("historia_mover", args=[self.projeto.pk, h.pk]), {"destino": destino})

    def test_hu11_product_backlog_para_sprint(self):
        self.mover(f"sprint-{self.sprint1.pk}")
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.sprint_backlog, self.sprint1)
        self.assertIsNone(self.historia.product_backlog)
        self.assertNotContains(self.client.get(reverse("product_backlog", args=[self.projeto.pk])), ">Mover<")
        self.assertContains(self.client.get(reverse("sprint_detalhe", args=[self.projeto.pk, self.sprint1.pk])), "Mover")

    def test_hu11_sprint_de_volta_para_product_backlog(self):
        self.mover(f"sprint-{self.sprint1.pk}")
        self.mover("product-backlog")
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.product_backlog, self.backlog)
        self.assertIsNone(self.historia.sprint_backlog)

    def test_hu11_de_um_sprint_para_outro(self):
        self.mover(f"sprint-{self.sprint1.pk}")
        self.mover(f"sprint-{self.sprint2.pk}")
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.sprint_backlog, self.sprint2)
        self.assertFalse(self.sprint1.historias.exists())

    def test_destino_atual_nao_e_oferecido(self):
        resp = self.client.get(reverse("historia_detalhe", args=[self.projeto.pk, self.historia.pk]))
        self.assertNotContains(resp, 'value="product-backlog"')
        self.assertContains(resp, f'value="sprint-{self.sprint1.pk}"')

    def test_sprint_de_outro_projeto_e_recusado(self):
        outro = Projeto.objects.create(nome="Outro", dono=self.estranho)
        sprint_outro = SprintBacklog.objects.create(projeto=outro, nome="Sprint X", **SPRINT_PERIODO)
        self.mover(f"sprint-{sprint_outro.pk}")
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.product_backlog, self.backlog)
        self.assertIsNone(self.historia.sprint_backlog)

    def test_mover_exige_post(self):
        resp = self.client.get(reverse("historia_mover", args=[self.projeto.pk, self.historia.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_estranho_nao_move(self):
        self.client.force_login(self.estranho)
        self.assertEqual(self.mover(f"sprint-{self.sprint1.pk}").status_code, 404)
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.product_backlog, self.backlog)


# Situação da história no Sprint (quadro Kanban) e responsável
class SituacaoResponsavelTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("lia", email="lia@exemplo.com", first_name="Lia Melo")
        self.membro = User.objects.create_user("rui", email="rui@exemplo.com", first_name="Rui Dias")
        self.estranho = User.objects.create_user("eva", email="eva@exemplo.com", first_name="Eva Luz")
        self.projeto = Projeto.objects.create(nome="Projeto K", dono=self.dono)
        self.projeto.membros.add(self.membro)
        self.backlog = ProductBacklog.objects.create(projeto=self.projeto)
        self.sprint = SprintBacklog.objects.create(projeto=self.projeto, nome="Sprint 1", **SPRINT_PERIODO)
        self.historia = HistoriaUsuario.objects.create(
            titulo="Renovar empréstimo", sprint_backlog=self.sprint, papel="a", acao="b", beneficio="c")
        self.client.force_login(self.membro)

    def mudar(self, situacao, historia=None):
        h = historia or self.historia
        return self.client.post(reverse("historia_situacao", args=[self.projeto.pk, h.pk]), {"situacao": situacao})

    def dados_form(self, **extra):
        dados = {"titulo": "Renovar empréstimo", "papel": "a", "acao": "b", "beneficio": "c"}
        dados.update(extra)
        return dados

    def test_historia_nova_comeca_a_fazer_e_sem_responsavel(self):
        self.assertEqual(self.historia.situacao, HistoriaUsuario.SITUACAO_A_FAZER)
        self.assertIsNone(self.historia.responsavel)

    def test_botoes_movem_o_cartao_entre_as_colunas(self):
        for situacao in ["em_desenvolvimento", "concluida", "em_desenvolvimento", "a_fazer"]:
            with self.subTest(situacao=situacao):
                response = self.mudar(situacao)
                self.assertRedirects(response, reverse("sprint_detalhe", args=[self.projeto.pk, self.sprint.pk]))
                self.historia.refresh_from_db()
                self.assertEqual(self.historia.situacao, situacao)

    def test_situacao_invalida_e_recusada(self):
        self.mudar("pronta")
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.situacao, "a_fazer")

    def test_banco_recusa_situacao_fora_da_lista(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoriaUsuario.objects.filter(pk=self.historia.pk).update(situacao="pronta")

    def test_historia_no_product_backlog_nao_muda_de_situacao(self):
        historia = HistoriaUsuario.objects.create(
            titulo="No PB", product_backlog=self.backlog, papel="a", acao="b", beneficio="c")
        self.mudar("concluida", historia)
        historia.refresh_from_db()
        self.assertEqual(historia.situacao, "a_fazer")

    def test_quem_nao_participa_nao_move_o_cartao(self):
        self.client.force_login(self.estranho)
        self.assertEqual(self.mudar("concluida").status_code, 404)
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.situacao, "a_fazer")

    def test_voltar_para_o_product_backlog_reinicia_a_situacao(self):
        self.mudar("concluida")
        self.client.post(reverse("historia_mover", args=[self.projeto.pk, self.historia.pk]), {"destino": "product-backlog"})
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.product_backlog, self.backlog)
        self.assertEqual(self.historia.situacao, "a_fazer")

    def test_excluir_sprint_reinicia_a_situacao(self):
        self.mudar("em_desenvolvimento")
        self.sprint.delete()
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.product_backlog, self.backlog)
        self.assertEqual(self.historia.situacao, "a_fazer")

    def test_quadro_mostra_cada_historia_na_coluna_certa(self):
        outra = HistoriaUsuario.objects.create(
            titulo="Buscar livro", sprint_backlog=self.sprint, papel="a", acao="b", beneficio="c",
            story_points=5, responsavel=self.dono)
        self.mudar("concluida", outra)
        response = self.client.get(reverse("sprint_detalhe", args=[self.projeto.pk, self.sprint.pk]))
        colunas = {c["valor"]: [h.titulo for h in c["historias"]] for c in response.context["colunas"]}
        self.assertEqual(colunas["a_fazer"], ["Renovar empréstimo"])
        self.assertEqual(colunas["em_desenvolvimento"], [])
        self.assertEqual(colunas["concluida"], ["Buscar livro"])
        self.assertContains(response, "Lia Melo")
        self.assertContains(response, "Sem responsável")
        self.assertContains(response, "Iniciar →")
        self.assertContains(response, "← Reabrir")

    def test_responsavel_so_pode_ser_dono_ou_membro(self):
        url = reverse("historia_editar", args=[self.projeto.pk, self.historia.pk])
        response = self.client.post(url, self.dados_form(responsavel=self.estranho.pk, situacao="a_fazer"))
        self.assertTrue(response.context["form"].errors.get("responsavel"))
        self.client.post(url, self.dados_form(responsavel=self.dono.pk, situacao="em_desenvolvimento"))
        self.historia.refresh_from_db()
        self.assertEqual(self.historia.responsavel, self.dono)
        self.assertEqual(self.historia.situacao, "em_desenvolvimento")

    def test_model_recusa_responsavel_de_fora_do_projeto(self):
        self.historia.responsavel = self.estranho
        with self.assertRaises(ValidationError):
            self.historia.save()

    def test_situacao_so_aparece_no_formulario_com_a_historia_em_sprint(self):
        no_sprint = self.client.get(reverse("historia_editar", args=[self.projeto.pk, self.historia.pk]))
        self.assertIn("situacao", no_sprint.context["form"].fields)
        historia_pb = HistoriaUsuario.objects.create(
            titulo="No PB", product_backlog=self.backlog, papel="a", acao="b", beneficio="c")
        no_pb = self.client.get(reverse("historia_editar", args=[self.projeto.pk, historia_pb.pk]))
        self.assertNotIn("situacao", no_pb.context["form"].fields)
        self.assertIn("responsavel", no_pb.context["form"].fields)

    def test_membro_removido_ou_que_sai_deixa_historias_sem_responsavel(self):
        self.historia.responsavel = self.membro
        self.historia.save()
        self.client.post(reverse("sair_projeto", args=[self.projeto.pk]))
        self.historia.refresh_from_db()
        self.assertIsNone(self.historia.responsavel)

        self.projeto.membros.add(self.membro)
        self.historia.responsavel = self.membro
        self.historia.save()
        self.client.force_login(self.dono)
        self.client.post(reverse("remover_membro", args=[self.projeto.pk, self.membro.pk]))
        self.historia.refresh_from_db()
        self.assertIsNone(self.historia.responsavel)


# Regras de datas do Sprint, status, encerrar, cancelar e histórico
class SprintRegrasTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("ana", email="ana@exemplo.com", first_name="Ana Souza")
        self.membro = User.objects.create_user("rui", email="rui@exemplo.com", first_name="Rui Dias")
        self.projeto = Projeto.objects.create(nome="Projeto R", dono=self.dono)
        self.projeto.membros.add(self.membro)
        self.backlog = ProductBacklog.objects.create(projeto=self.projeto)
        self.client.force_login(self.dono)

    def url(self, nome, *args):
        return reverse(nome, args=[self.projeto.pk, *args])

    def criar(self, inicio, fim, nome="Sprint X"):
        return self.client.post(self.url("sprint_criar"), {"nome": nome, "data_inicio": inicio, "data_fim": fim})

    def sprint(self, ini, fim, nome="Sprint 1", **extra):
        hoje = date.today()
        return SprintBacklog.objects.create(projeto=self.projeto, nome=nome,
                                            data_inicio=hoje + timedelta(days=ini),
                                            data_fim=hoje + timedelta(days=fim), **extra)

    def historia(self, sprint, titulo, situacao="a_fazer", pontos=3):
        return HistoriaUsuario.objects.create(titulo=titulo, sprint_backlog=sprint, papel="a", acao="b",
                                              beneficio="c", story_points=pontos, situacao=situacao)

    def erros(self, response, campo):
        return response.context["form"].errors.get(campo, [])

    # --- datas ---
    def test_duracao_maxima_de_30_dias(self):
        self.assertEqual(self.criar(dia(0), dia(29)).status_code, 302)  # 30 dias
        SprintBacklog.objects.all().delete()
        response = self.criar(dia(0), dia(30))  # 31 dias
        self.assertIn("O Sprint pode durar no máximo 30 dias.", self.erros(response, "data_fim"))
        self.assertFalse(SprintBacklog.objects.exists())

    def test_sprint_de_um_dia_e_aceito(self):
        self.assertEqual(self.criar(dia(0), dia(0)).status_code, 302)

    def test_inicio_a_partir_de_hoje(self):
        response = self.criar(dia(-1), dia(5))
        self.assertTrue(any("não pode ser antes de hoje" in e for e in self.erros(response, "data_inicio")))
        self.assertFalse(SprintBacklog.objects.exists())
        self.assertEqual(self.criar(dia(0), dia(5)).status_code, 302)

    def test_inicio_no_maximo_um_ano_a_frente(self):
        response = self.criar(dia(366), dia(370))
        self.assertTrue(any("no máximo 1 ano à frente" in e for e in self.erros(response, "data_inicio")))
        self.assertEqual(self.criar(dia(365), dia(370)).status_code, 302)

    def test_um_sprint_por_vez(self):
        self.criar(dia(0), dia(11), "Sprint 1")
        response = self.criar(dia(11), dia(20), "Sprint 2")  # coincide no último dia
        self.assertTrue(any("Já existe um Sprint nesse período: Sprint 1" in e for e in response.context["form"].non_field_errors()))
        self.assertEqual(self.criar(dia(12), dia(20), "Sprint 2").status_code, 302)  # começa no dia seguinte
        self.assertEqual(self.projeto.sprint_backlogs.count(), 2)

    def test_sprint_cancelado_ou_encerrado_antes_libera_as_datas(self):
        cancelado = self.sprint(0, 10, cancelado=True, encerrado_em=date.today())
        self.assertEqual(self.criar(dia(0), dia(10), "Sprint novo").status_code, 302)
        SprintBacklog.objects.exclude(pk=cancelado.pk).delete()
        self.sprint(-5, 10, nome="Encerrado", encerrado_em=date.today() + timedelta(days=0))
        self.assertEqual(self.criar(dia(1), dia(5), "Seguinte").status_code, 302)

    # --- status ---
    def test_status_calculado_pelas_datas(self):
        hoje = date.today()
        s = SprintBacklog(projeto=self.projeto, nome="S", data_inicio=hoje, data_fim=hoje + timedelta(days=5))
        self.assertEqual(s.status_em(hoje - timedelta(days=1)), "planejado")
        self.assertEqual(s.status_em(hoje), "em_andamento")
        self.assertEqual(s.status_em(hoje + timedelta(days=5)), "em_andamento")
        self.assertEqual(s.status_em(hoje + timedelta(days=6)), "concluido")
        s.cancelado = True
        self.assertEqual(s.status_em(hoje), "cancelado")

    def test_lista_mostra_a_situacao_de_cada_sprint(self):
        self.sprint(-20, -15, nome="Antigo")
        self.sprint(-2, 5, nome="Atual")
        response = self.client.get(self.url("sprint_lista"))
        self.assertContains(response, "Em andamento")
        self.assertContains(response, "Concluído")

    # --- encerrar ---
    def test_dono_encerra_e_nao_concluidas_voltam_ao_product_backlog(self):
        sprint = self.sprint(-3, 7)
        feita = self.historia(sprint, "Feita", "concluida", 5)
        andando = self.historia(sprint, "Andando", "em_desenvolvimento", 3)
        parada = self.historia(sprint, "Parada", "a_fazer", 2)
        confirmacao = self.client.get(self.url("sprint_encerrar", sprint.pk))
        self.assertContains(confirmacao, "2 histórias não concluídas voltarão para o Product Backlog")
        sprint.refresh_from_db()
        self.assertIsNone(sprint.encerrado_em)  # a tela de confirmação não encerra

        self.client.post(self.url("sprint_encerrar", sprint.pk))
        sprint.refresh_from_db()
        self.assertEqual(sprint.encerrado_em, date.today())
        self.assertEqual(sprint.encerrado_por, self.dono)
        self.assertEqual(sprint.status, "concluido")
        for h in (feita, andando, parada):
            h.refresh_from_db()
        self.assertEqual(feita.sprint_backlog, sprint)
        self.assertEqual(andando.product_backlog, self.backlog)
        self.assertEqual(andando.situacao, "a_fazer")
        registros = {d.titulo: d for d in sprint.historias_devolvidas.all()}
        self.assertEqual(set(registros), {"Andando", "Parada"})
        self.assertEqual(registros["Andando"].situacao, "em_desenvolvimento")
        self.assertEqual(registros["Andando"].story_points, 3)

        historico = self.client.get(self.url("sprint_detalhe", sprint.pk))
        self.assertTemplateUsed(historico, "core/sprint_historico.html")
        self.assertContains(historico, "5 pts")
        self.assertContains(historico, "Voltaram para o Product Backlog")
        self.assertContains(historico, "antes do previsto")

    def test_membro_nao_encerra_nem_cancela(self):
        sprint = self.sprint(-3, 7)
        self.client.force_login(self.membro)
        self.assertNotContains(self.client.get(self.url("sprint_detalhe", sprint.pk)), "Encerrar Sprint")
        self.client.post(self.url("sprint_encerrar", sprint.pk))
        self.client.post(self.url("sprint_cancelar", sprint.pk), {"motivo": "x"})
        sprint.refresh_from_db()
        self.assertIsNone(sprint.encerrado_em)
        self.assertFalse(sprint.cancelado)

    def test_sprint_planejado_nao_e_encerrado_mas_pode_ser_cancelado(self):
        sprint = self.sprint(3, 10)
        self.client.post(self.url("sprint_encerrar", sprint.pk))
        sprint.refresh_from_db()
        self.assertIsNone(sprint.encerrado_em)
        self.client.post(self.url("sprint_cancelar", sprint.pk), {"motivo": ""})
        sprint.refresh_from_db()
        self.assertTrue(sprint.cancelado)

    # --- cancelar ---
    def test_cancelar_com_motivo_fica_registrado(self):
        sprint = self.sprint(-3, 7)
        self.historia(sprint, "Relatórios", "em_desenvolvimento")
        self.client.post(self.url("sprint_cancelar", sprint.pk), {"motivo": "O cliente suspendeu o módulo."})
        sprint.refresh_from_db()
        self.assertTrue(sprint.cancelado)
        self.assertEqual(sprint.status, "cancelado")
        self.assertEqual(sprint.motivo_cancelamento, "O cliente suspendeu o módulo.")
        self.assertEqual(HistoriaUsuario.objects.get(titulo="Relatórios").product_backlog, self.backlog)
        pagina = self.client.get(self.url("sprint_detalhe", sprint.pk))
        self.assertContains(pagina, "Sprint cancelado em")
        self.assertContains(pagina, "Motivo: O cliente suspendeu o módulo.")

    # --- encerramento automático ---
    def test_sprint_vencido_e_encerrado_sozinho(self):
        sprint = self.sprint(-10, -1)
        pendente = self.historia(sprint, "Pendente", "em_desenvolvimento")
        self.client.get(self.url("sprint_lista"))
        sprint.refresh_from_db()
        pendente.refresh_from_db()
        self.assertEqual(sprint.encerrado_em, sprint.data_fim)
        self.assertIsNone(sprint.encerrado_por)
        self.assertEqual(pendente.product_backlog, self.backlog)
        self.assertContains(self.client.get(self.url("sprint_detalhe", sprint.pk)), "encerrado automaticamente")

    # --- Sprint fechado não muda ---
    def test_sprint_fechado_nao_muda_mais(self):
        fechado = self.sprint(-10, -1, nome="Fechado")
        feita = self.historia(fechado, "Feita", "concluida")
        aberto = self.sprint(0, 5, nome="Aberto")
        no_pb = HistoriaUsuario.objects.create(titulo="No PB", product_backlog=self.backlog, papel="a", acao="b", beneficio="c")
        self.client.get(self.url("sprint_lista"))  # encerra o vencido

        self.client.post(self.url("historia_situacao", feita.pk), {"situacao": "a_fazer"})
        feita.refresh_from_db()
        self.assertEqual(feita.situacao, "concluida")

        detalhe = self.client.get(self.url("historia_detalhe", no_pb.pk))
        destinos = [v for v, _ in detalhe.context["form_mover"].fields["destino"].choices]
        self.assertIn(f"sprint-{aberto.pk}", destinos)
        self.assertNotIn(f"sprint-{fechado.pk}", destinos)
        self.assertEqual(self.client.get(self.url("historia_detalhe", feita.pk)).context["form_mover"].fields["destino"].choices, [])

        self.assertRedirects(self.client.get(self.url("sprint_editar", fechado.pk)), self.url("sprint_detalhe", fechado.pk))


# Product Backlog em ordem de prioridade, com totais e "Mover para Sprint" na lista
class ProductBacklogPrioridadeTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("ana", email="ana@exemplo.com", first_name="Ana Souza")
        self.projeto = Projeto.objects.create(nome="Projeto P", dono=self.dono)
        self.backlog = ProductBacklog.objects.create(projeto=self.projeto)
        self.client.force_login(self.dono)

    def h(self, titulo, moscow="", rice=None, pontos=None):
        # rice=(reach, impact, confidence, effort)
        campos = dict(zip(["reach", "impact", "confidence", "effort"], rice)) if rice else {}
        return HistoriaUsuario.objects.create(titulo=titulo, product_backlog=self.backlog, papel="a", acao="b",
                                              beneficio="c", moscow=moscow, story_points=pontos, **campos)

    def url(self, nome, *args):
        return reverse(nome, args=[self.projeto.pk, *args])

    def titulos(self):
        return [h.titulo for h in self.client.get(self.url("product_backlog")).context["historias"]]

    def test_ordem_moscow_e_depois_rice(self):
        self.h("Sem etiqueta", "", (100, 1, 100, 1))
        self.h("Won't", "W", (100, 1, 100, 1))
        self.h("Could", "C")
        self.h("Must RICE baixo", "M", (10, 1, 50, 5))       # 100
        self.h("Must RICE alto", "M", (500, 2, 80, 5))       # 16000
        self.h("Must incompleto", "M")
        self.h("Should", "S", (1, 1, 50, 1))
        self.assertEqual(self.titulos(), [
            "Must RICE alto", "Must RICE baixo", "Must incompleto", "Should", "Could", "Won't", "Sem etiqueta",
        ])

    def test_rice_nao_calculavel_fica_depois_dos_calculados(self):
        self.h("Effort zero", "M", (100, 1, 100, 0))
        self.h("Calculado", "M", (1, 0.25, 50, 55))
        self.assertEqual(self.titulos(), ["Calculado", "Effort zero"])

    def test_totais_e_contagem_por_moscow(self):
        self.h("A", "M", pontos=5)
        self.h("B", "M", pontos=3)
        self.h("C", "S")
        response = self.client.get(self.url("product_backlog"))
        self.assertEqual(response.context["total_pontos"], 8)
        self.assertEqual(response.context["sem_estimativa"], 1)
        self.assertIn(("M", "Must", 2), response.context["contagem_moscow"])
        self.assertContains(response, "1 sem estimativa")

    def test_mover_para_sprint_pela_lista_volta_para_a_lista(self):
        historia = self.h("Mover daqui", "M")
        aberto = SprintBacklog.objects.create(projeto=self.projeto, nome="Aberto", **SPRINT_PERIODO)
        response = self.client.post(self.url("historia_mover", historia.pk),
                                    {"destino": f"sprint-{aberto.pk}", "voltar": "product_backlog"})
        self.assertRedirects(response, self.url("product_backlog"))
        historia.refresh_from_db()
        self.assertEqual(historia.sprint_backlog, aberto)
        self.assertNotIn("Mover daqui", self.titulos())

    def test_so_sprints_abertos_aparecem_para_mover(self):
        self.h("Qualquer", "M")
        hoje = date.today()
        aberto = SprintBacklog.objects.create(projeto=self.projeto, nome="Aberto", **SPRINT_PERIODO)
        cancelado = SprintBacklog.objects.create(projeto=self.projeto, nome="Cancelado", data_inicio=hoje,
                                                 data_fim=hoje, cancelado=True, encerrado_em=hoje)
        response = self.client.get(self.url("product_backlog"))
        self.assertEqual(response.context["sprints_abertos"], [aberto])
        self.assertNotContains(response, f'value="sprint-{cancelado.pk}"')

    def test_sem_sprint_aberto_mostra_aviso(self):
        self.h("Qualquer", "M")
        self.assertContains(self.client.get(self.url("product_backlog")), "Nenhum Sprint aberto")
