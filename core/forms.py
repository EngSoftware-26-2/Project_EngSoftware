
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Projeto, ProductBacklog

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


class ProductBacklogForm(forms.ModelForm):
    class Meta:
        model = ProductBacklog
        fields = ["descricao"]
        labels = {"descricao": "Descrição"}
