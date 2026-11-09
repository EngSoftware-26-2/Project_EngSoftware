
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Projeto, ProductBacklog, Epico, HistoriaUsuario, CriterioAceitacao, SprintBacklog

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
            # ALTERADO: contexto, evento e resultado saíram do formulário. Eles viraram campos
            # legados (Artefato 7, migration 0007); os critérios agora são gravados no model
            # CriterioAceitacao. Na criação da história o primeiro critério continua podendo
            # ser escrito (campos extras abaixo).
            'epico',
            'story_points', 'moscow',
            'reach', 'impact', 'confidence', 'effort',
        ]
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
        # ADICIONADO: na criação da história (HU12, critério 3), o usuário pode já escrever o
        # primeiro critério de aceitação. Os outros são adicionados depois, no detalhe da
        # história. Na edição esses campos não aparecem: os critérios têm CRUD próprio.
        if self.instance.pk is None:
            self.fields['criterio_dado'] = forms.CharField(label='Dado', required=False, widget=forms.Textarea(attrs={'rows': 2}))
            self.fields['criterio_quando'] = forms.CharField(label='Quando', required=False, max_length=255)
            self.fields['criterio_entao'] = forms.CharField(label='Então', required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean(self):
        dados = super().clean()
        # O primeiro critério é opcional, mas se for escrito precisa estar completo (requisito 13).
        partes = [dados.get(c, '').strip() for c in ('criterio_dado', 'criterio_quando', 'criterio_entao')]
        if any(partes) and not all(partes):
            raise forms.ValidationError('Para adicionar o critério, preencha Dado, Quando e Então.')
        return dados

    def save(self, commit=True):
        historia = super().save(commit=commit)
        if commit and 'criterio_dado' in self.fields:
            dado = self.cleaned_data.get('criterio_dado', '').strip()
            if dado:
                CriterioAceitacao.objects.create(
                    historia_usuario=historia,
                    dado=dado,
                    quando=self.cleaned_data['criterio_quando'].strip(),
                    entao=self.cleaned_data['criterio_entao'].strip(),
                )
        return historia


# ADICIONADO: (Requisitos 12 e 13) formulário para criar e editar um critério de aceitação,
# usando o model CriterioAceitacao definido no Artefato 7 (campos dado, quando, entao).
class CriterioAceitacaoForm(forms.ModelForm):
    class Meta:
        model = CriterioAceitacao
        fields = ['dado', 'quando', 'entao']
        widgets = {
            'dado': forms.Textarea(attrs={'rows': 2}),
            'entao': forms.Textarea(attrs={'rows': 2}),
        }
        error_messages = {
            'dado': {'required': 'Preencha o Dado (contexto inicial).'},
            'quando': {'required': 'Preencha o Quando (ação ou evento).'},
            'entao': {'required': 'Preencha o Então (resultado esperado).'},
        }


# ADICIONADO: (Requisito 6; HU09 e HU10) formulário para criar e editar um Sprint Backlog,
# com nome e período. A regra "data de fim não pode ser antes da de início" já está no
# model (clean e restrição no banco, Artefato 7) e aparece como erro no formulário.
class SprintBacklogForm(forms.ModelForm):
    class Meta:
        model = SprintBacklog
        fields = ['nome', 'data_inicio', 'data_fim']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_fim': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }
        error_messages = {
            'nome': {'required': 'O nome do Sprint Backlog é obrigatório.'},
            'data_inicio': {'required': 'Informe a data de início.', 'invalid': 'Informe uma data válida.'},
            'data_fim': {'required': 'Informe a data de fim.', 'invalid': 'Informe uma data válida.'},
        }

    def _post_clean(self):
        # Se alguma data faltou, o erro do próprio campo já avisa; evita repetir a mensagem
        # genérica do model ("deve informar as datas de início e fim").
        if self.errors.get('data_inicio') or self.errors.get('data_fim'):
            return
        super()._post_clean()
