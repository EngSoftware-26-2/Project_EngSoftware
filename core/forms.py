
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .validadores import (
    EMAIL_DICA, EMAIL_MAX, NOME_DICA, NOME_MAX, SENHA_DICA, SENHA_MAX,
    validar_nome, validar_senha,
)
from .sprints import sprint_em_conflito
from .models import Projeto, ProductBacklog, Epico, HistoriaUsuario, CriterioAceitacao, SprintBacklog

# HU01 - Formulário de cadastro: o e-mail é usado como login (username) e não pode repetir.
# Nome e senha seguem as regras de core/validadores.py; a dica de cada campo aparece embaixo
# dele na tela.
class CadastroForm(forms.Form):
    nome = forms.CharField(
        label="Nome",
        max_length=NOME_MAX,
        help_text=NOME_DICA,
        validators=[validar_nome],
    )
    email = forms.EmailField(
        label="E-mail",
        max_length=EMAIL_MAX,
        help_text=EMAIL_DICA,
        error_messages={"invalid": "Informe um e-mail válido."},
    )
    senha = forms.CharField(
        label="Senha",
        max_length=SENHA_MAX,
        help_text=SENHA_DICA,
        strip=False,
        validators=[validar_senha],
        widget=forms.PasswordInput,
    )
    confirmar_senha = forms.CharField(
        label="Confirmar senha",
        max_length=SENHA_MAX,
        help_text="Repita a senha.",
        strip=False,
        widget=forms.PasswordInput,
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
                # A senha já passou pelas regras do sistema (validar_senha). O Django ainda
                # recusa senha comum demais ou parecida com o nome ou o e-mail.
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
    email = forms.EmailField(
        label="E-mail",
        help_text="O e-mail usado no cadastro.",
        error_messages={"invalid": "Informe um e-mail válido."},
    )
    senha = forms.CharField(
        label="Senha",
        strip=False,
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


# Formulários do CRUD de épicos (HU15, HU16; requisito 10) e de histórias de
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
            # Os campos contexto, evento e resultado saíram do formulário. Eles viraram campos
            # legados (Artefato 7, migration 0007); os critérios agora são gravados no model
            # CriterioAceitacao. Na criação da história o primeiro critério continua podendo
            # ser escrito (campos extras abaixo).
            'epico',
            'story_points', 'moscow',
            'reach', 'impact', 'confidence', 'effort',
            'responsavel', 'situacao',
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
        # Responsável: só o dono e os membros do projeto aparecem na lista.
        if projeto is not None:
            participantes = User.objects.filter(
                Q(pk=projeto.dono_id) | Q(projetos_como_membro=projeto)
            ).distinct().order_by('first_name', 'email')
        else:
            participantes = User.objects.none()
        self.fields['responsavel'].queryset = participantes
        self.fields['responsavel'].empty_label = 'Sem responsável'
        self.fields['responsavel'].label_from_instance = lambda u: u.first_name or u.email
        self.fields['responsavel'].help_text = 'Dono ou membro do projeto.'
        # A situação só faz sentido com a história em um Sprint. No Product Backlog o campo
        # não aparece (a história fica "A fazer").
        if self.instance.sprint_backlog_id is None or self.instance.sprint_backlog.fechado:
            del self.fields['situacao']
        else:
            self.fields['situacao'].help_text = 'Em que coluna do quadro do Sprint a história está.'
        # Na criação da história (HU12, critério 3), o usuário pode já escrever o
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


# (Requisitos 12 e 13) formulário para criar e editar um critério de aceitação,
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


# (Requisito 6; HU09 e HU10) formulário para criar e editar um Sprint Backlog,
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].help_text = 'Ex.: Sprint 3 ou Correção de bugs'
        self.fields['data_inicio'].help_text = 'A partir de hoje, até 1 ano à frente.'
        self.fields['data_fim'].help_text = f'No máximo {SprintBacklog.DURACAO_MAXIMA_DIAS} dias de Sprint, contando o dia de início.'

    def clean(self):
        # Regras de datas do Sprint:
        #  - duração máxima de 30 dias (Scrum Guide: "um mês ou menos"); não há mínimo, para
        #    permitir Sprints curtos, como um de correção de bugs;
        #  - a data de início não pode ser antes de hoje nem mais de 1 ano à frente. Ao editar
        #    um Sprint que já começou, a data de início antiga continua valendo;
        #  - um Sprint por vez no projeto: as datas não podem coincidir com as de outro.
        dados = super().clean()
        inicio, fim = dados.get('data_inicio'), dados.get('data_fim')
        hoje = timezone.localdate()
        if inicio:
            inicio_mudou = self.instance.pk is None or inicio != self.instance.data_inicio
            if inicio_mudou and inicio < hoje:
                self.add_error('data_inicio', f'A data de início não pode ser antes de hoje ({hoje:%d/%m/%Y}).')
            limite = hoje + timedelta(days=365)
            if inicio_mudou and inicio > limite:
                self.add_error('data_inicio', f'A data de início pode ser no máximo 1 ano à frente (até {limite:%d/%m/%Y}).')
        if inicio and fim:
            if fim < inicio:
                self.add_error('data_fim', 'A data de fim não pode ser anterior à data de início.')
            elif (fim - inicio).days + 1 > SprintBacklog.DURACAO_MAXIMA_DIAS:
                self.add_error('data_fim', f'O Sprint pode durar no máximo {SprintBacklog.DURACAO_MAXIMA_DIAS} dias.')
            if not self.errors:
                conflito = sprint_em_conflito(self.instance.projeto, inicio, fim, ignorar_pk=self.instance.pk)
                if conflito:
                    raise forms.ValidationError(
                        f'Já existe um Sprint nesse período: {conflito.nome} '
                        f'({conflito.data_inicio:%d/%m/%Y} a {conflito.fim_efetivo:%d/%m/%Y}). '
                        'O projeto tem um Sprint por vez; escolha datas fora desse período.'
                    )
        return dados

    def _post_clean(self):
        # Se alguma data faltou, o erro do próprio campo já avisa; evita repetir a mensagem
        # genérica do model ("deve informar as datas de início e fim").
        if self.errors.get('data_inicio') or self.errors.get('data_fim'):
            return
        super()._post_clean()


# (Requisito 8; HU11) formulário para mover uma história entre o Product
# Backlog e os Sprint Backlogs do mesmo projeto. Só aparecem os destinos possíveis: os
# backlogs do projeto, menos aquele em que a história já está.
class MoverHistoriaForm(forms.Form):
    DESTINO_PRODUCT_BACKLOG = 'product-backlog'

    destino = forms.ChoiceField(
        label='Mover para',
        error_messages={'required': 'Escolha para onde mover a história.',
                        'invalid_choice': 'Escolha um backlog deste projeto.'},
    )

    def __init__(self, *args, historia, projeto, **kwargs):
        super().__init__(*args, **kwargs)
        self.historia = historia
        opcoes = []
        backlog = ProductBacklog.objects.filter(projeto=projeto).first()
        # Uma história concluída num Sprint já encerrado ou cancelado faz parte do histórico
        # dele e não se move mais. E Sprints fechados não recebem histórias novas.
        self.no_sprint_fechado = bool(historia.sprint_backlog_id and historia.sprint_backlog.fechado)
        if not self.no_sprint_fechado:
            if backlog is not None and historia.product_backlog_id != backlog.pk:
                opcoes.append((self.DESTINO_PRODUCT_BACKLOG, 'Product Backlog'))
            for sprint in projeto.sprint_backlogs.order_by('data_inicio', 'pk'):
                if sprint.pk != historia.sprint_backlog_id and not sprint.fechado:
                    opcoes.append((f'sprint-{sprint.pk}', f'{sprint.nome} ({sprint.status_nome})'))
        self.fields['destino'].choices = opcoes
        self.backlog = backlog
        self.sprints = {f'sprint-{s.pk}': s for s in projeto.sprint_backlogs.all() if not s.fechado}

    def mover(self):
        # Uma história fica em um backlog por vez (Artefato 7): ao entrar em um, sai do outro.
        destino = self.cleaned_data['destino']
        if destino == self.DESTINO_PRODUCT_BACKLOG:
            self.historia.product_backlog = self.backlog
            self.historia.sprint_backlog = None
            nome = 'Product Backlog'
        else:
            sprint = self.sprints[destino]
            self.historia.sprint_backlog = sprint
            self.historia.product_backlog = None
            nome = sprint.nome
        self.historia.save()
        return nome


# Cancelar Sprint: o motivo é opcional e fica registrado na página do Sprint.
class CancelarSprintForm(forms.Form):
    motivo = forms.CharField(
        label='Motivo', required=False, max_length=500,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Se quiser, explique por que o Sprint foi cancelado. Fica registrado na página do Sprint.',
    )
