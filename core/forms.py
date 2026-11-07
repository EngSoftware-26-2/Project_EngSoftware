
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Projeto, ProductBacklog, Epico, HistoriaUsuario

# HU01 - Formulário de cadastro: o e-mail é usado como login (username) e não pode repetir;
# a senha passa pelos validadores de senha do Django.
class CadastroForm(forms.Form):
    nome = forms.CharField(
        label="Nome",
        max_length=150
    )
    email = forms.EmailField(
        label="E-mail",
        max_length=150
    )
    senha = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput
    )
    confirmar_senha = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        existe = User.objects.filter(
            Q(email__iexact=email) |
            Q(username__iexact=email)
        ).exists()

        if existe:
            raise forms.ValidationError(
                "Este e-mail já está em uso."
            )

        return email

    def clean(self):
        dados = super().clean()

        senha = dados.get("senha")
        confirmar = dados.get("confirmar_senha")

        if senha and confirmar:
            if senha != confirmar:
                self.add_error(
                    "confirmar_senha",
                    "As senhas não coincidem."
                )
            else:
                usuario = User(
                    username=dados.get("email", ""),
                    email=dados.get("email", ""),
                    first_name=dados.get("nome", "")
                )

                try:
                    validate_password(senha, user=usuario)
                except ValidationError as erro:
                    self.add_error("senha", erro)

        return dados

    def salvar(self):
        dados = self.cleaned_data

        return User.objects.create_user(
            username=dados["email"],
            email=dados["email"],
            first_name=dados["nome"],
            password=dados["senha"]
        )


# HU02 - Formulário de login por e-mail e senha
class LoginForm(forms.Form):
    email = forms.EmailField(label="E-mail")
    senha = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput
    )

# HU04 - Formulário de criação de projetos

class ProjetoForm(forms.ModelForm):

    class Meta:
        model = Projeto

        fields = ["nome", "descricao"]

        labels = {
            "nome": "Nome do projeto",
            "descricao": "Descrição"
        }

        widgets = {
            "nome": forms.TextInput(
                attrs={"placeholder": "Nome do projeto"}
            ),
            "descricao": forms.Textarea(
                attrs={
                    "placeholder": "Descrição do projeto",
                    "rows": 4
                }
            )
        }

# HU22 - Adicionar membros ao projeto

class AdicionarMembroForm(forms.Form):
    email = forms.EmailField(
        label="E-mail do membro",
        max_length=150,
        widget=forms.EmailInput(
            attrs={"placeholder": "usuario@exemplo.com"}
        )
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


# HU08 - Formulário para criar e editar a descrição do Product Backlog (requisito 5)
class ProductBacklogForm(forms.ModelForm):
    class Meta:
        model = ProductBacklog
        fields = ["descricao"]
        labels = {"descricao": "Descrição"}


# ADICIONADO: formulários do CRUD de épicos (HU15, HU16; requisito 10) e de histórias de
# usuário (HU12, HU13; requisitos 7, 9, 11, 14-19).
class EpicoForm(forms.ModelForm):
    class Meta:
        model = Epico
        fields = ['titulo', 'descricao']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}
        error_messages = {'titulo': {'required': 'O nome do épico é obrigatório.'}}


class HistoriaUsuarioForm(forms.ModelForm):
    class Meta:
        model = HistoriaUsuario
        fields = [
            'titulo', 'papel', 'acao', 'beneficio',
            'contexto', 'evento', 'resultado',
            'epico',
            'story_points', 'moscow',
            'reach', 'impact', 'confidence', 'effort',
        ]
        widgets = {
            'contexto': forms.Textarea(attrs={'rows': 2}),
            'resultado': forms.Textarea(attrs={'rows': 2}),
        }
        error_messages = {
            'titulo': {'required': 'O título é obrigatório.'},
            'papel': {'required': 'Informe o papel (Como um...).'},
            'acao': {'required': 'Informe a ação (Eu quero...).'},
            'beneficio': {'required': 'Informe o benefício (Para...).'},
            'story_points': {'invalid_choice': 'Story Points aceita apenas 0, 1, 2, 3, 5, 8, 13, 21, 34 ou 55.'},
            'moscow': {'invalid_choice': 'MoSCoW aceita apenas M, S, C ou W.'},
            'impact': {'invalid_choice': 'Impact aceita apenas 3, 2, 1, 0,5 ou 0,25.'},
            'confidence': {'invalid_choice': 'Confidence aceita apenas 100, 80 ou 50.'},
            'effort': {'invalid_choice': 'Effort aceita apenas 0, 1, 2, 3, 5, 8, 13, 21, 34 ou 55.'},
        }

    def __init__(self, *args, projeto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.projeto = projeto
        # Vinculação com épico (HU17): só os épicos do mesmo projeto aparecem na lista, e a
        # opção vazia vale como "Sem épico".
        self.fields['epico'].queryset = Epico.objects.filter(projeto=projeto)
        self.fields['epico'].empty_label = 'Sem épico'
        self.fields['story_points'].choices = [('', 'Sem estimativa')] + HistoriaUsuario.STORY_POINTS_CHOICES
        self.fields['moscow'].choices = [('', 'Sem etiqueta')] + HistoriaUsuario.MOSCOW_CHOICES
        self.fields['impact'].choices = [('', '---------')] + HistoriaUsuario.IMPACT_CHOICES
        self.fields['confidence'].choices = [('', '---------')] + HistoriaUsuario.CONFIDENCE_CHOICES
        self.fields['effort'].choices = [('', '---------')] + HistoriaUsuario.STORY_POINTS_CHOICES
