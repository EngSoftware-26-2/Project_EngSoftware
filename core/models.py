from django.db import models
from django.db.models import F, Q
from django.conf import settings
from django.core.exceptions import ValidationError

# (Requisito 4) CRUD de Projetos
class Projeto(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    # HU04 e HU22-HU24: quem cria o projeto é o dono. PROTECT impede apagar a conta de um
    # usuário que ainda é dono de algum projeto, para o projeto não ficar sem dono.
    dono = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.PROTECT,
    related_name="projetos_como_dono"
)

    # HU22-HU24: usuários de outras contas que participam do projeto
    membros = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="projetos_como_membro"
    )

    def __str__(self):
        return self.nome

# (Requisito 5) Product Backlog: pode existir só um por projeto
class ProductBacklog(models.Model):
    projeto = models.OneToOneField(
        Projeto,
        on_delete=models.CASCADE,
        related_name="product_backlog"
    )

    # HU08: descrição editável do Product Backlog (objetivo do produto)
    descricao = models.TextField(blank=True)

    def __str__(self):
        return f"Product Backlog - {self.projeto.nome}"


# (Requisito 6) Sprint Backlogs: podem existir vários por projeto
class SprintBacklog(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='sprint_backlogs')
    nome = models.CharField(max_length=100, help_text="Ex: Sprint 1")
    data_inicio = models.DateField("Data de início")
    data_fim = models.DateField("Data de fim")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(data_fim__gte=F("data_inicio")),
                name="sprint_periodo_valido",
            ),
        ]

    def clean(self):
        super().clean()
        if self.data_inicio is None or self.data_fim is None:
            raise ValidationError("A Sprint Backlog deve informar as datas de início e fim.")
        if self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "A data de fim não pode ser anterior à data de início."})

    def __str__(self):
        return f"{self.nome} ({self.projeto.nome})"

# (Requisito 10) CRUD de Épicos
class Epico(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='epicos')
    # O verbose_name "Nome" foi adicionado. O Artefato 4 (HU15/HU16) chama esse campo de
    # "nome" do épico; o nome da coluna (titulo) foi mantido para não quebrar o banco nem o
    # código de outros membros, só o rótulo exibido nas telas mudou.
    titulo = models.CharField("Nome", max_length=200)
    # Descrição opcional. A HU15 pede épicos "com nome e descrição".
    descricao = models.TextField("Descrição", blank=True)

    class Meta:
        ordering = ['titulo']

    def __str__(self):
        return self.titulo

# (Requisitos 7 a 19) História de Utilizador e Priorização
class HistoriaUsuario(models.Model):
    titulo = models.CharField("Título", max_length=200)

    # Vinculações (Requisito 7, 8 e 11)
    product_backlog = models.ForeignKey(ProductBacklog, on_delete=models.CASCADE, related_name='historias', null=True, blank=True)
    sprint_backlog = models.ForeignKey(SprintBacklog, on_delete=models.SET_NULL, null=True, blank=True, related_name='historias')
    # Vinculação história -> épico (HU17). SET_NULL atende a HU16: excluir o épico não apaga
    # as histórias, elas só ficam "sem épico".
    epico = models.ForeignKey(Epico, on_delete=models.SET_NULL, null=True, blank=True, related_name='historias', verbose_name="Épico")

    # Formato padrão da História (Requisito 9)
    papel = models.CharField("Como um", max_length=100, help_text="Como um [papel]...")
    acao = models.CharField("Eu quero", max_length=255, help_text="Eu quero [ação]...")
    beneficio = models.CharField("Para", max_length=255, help_text="Para [benefício]...")

    # Compatibilidade com dados legados. Novos critérios devem ser gravados em
    # CriterioAceitacao, que permite vários critérios por história. Estes campos
    # permanecerão durante a transição para que registros antigos não sejam perdidos.
    contexto = models.TextField("Dado", blank=True, help_text="Dado [contexto inicial]...")
    evento = models.CharField("Quando", max_length=255, blank=True, help_text="Quando [evento]...")
    resultado = models.TextField("Então", blank=True, help_text="Então [resultado]...")

    # Story Points (Requisito 14 e 15)
    STORY_POINTS_CHOICES = [(0, '0'), (1, '1'), (2, '2'), (3, '3'), (5, '5'), (8, '8'), (13, '13'), (21, '21'), (34, '34'), (55, '55')]
    STORY_POINTS_VALIDOS = [valor for valor, _ in STORY_POINTS_CHOICES]
    # De default=0 para null=True/blank=True. Zero é uma estimativa válida da escala,
    # então usar 0 como padrão fazia toda história nova parecer "estimada em 0 pontos" sem
    # ninguém ter estimado. Agora "sem estimativa" (vazio) é diferente de "0 pts".
    story_points = models.IntegerField("Story Points", choices=STORY_POINTS_CHOICES, null=True, blank=True)

    # MoSCoW (Requisito 16)
    MOSCOW_CHOICES = [('M', 'Must Have'), ('S', 'Should Have'), ('C', 'Could Have'), ('W', "Won't Have")]
    # De default='M' para blank=True com padrão vazio. Com 'M' como padrão, toda
    # história nova nascia como "Must", o que distorce a priorização e contradiz a HU19, em que
    # a etiqueta é escolhida pelo Product Owner.
    moscow = models.CharField("MoSCoW", max_length=1, choices=MOSCOW_CHOICES, blank=True, default='')

    # Critérios RICE (Requisito 17 e 18)
    # Os quatro componentes do RICE passaram a ser opcionais (null=True/blank=True)
    # e sem valor padrão. Antes reach=0, impact=1 e confidence=80 eram preenchidos sozinhos,
    # então o RICE nunca ficava "incompleto" (HU20, critério 3) e o score podia aparecer
    # calculado com valores que o Product Owner nunca informou.
    # O campo reach passou de IntegerField para PositiveIntegerField, porque alcance negativo
    # (número de usuários) não faz sentido e era aceito.
    reach = models.PositiveIntegerField("Reach", null=True, blank=True, help_text="Alcance (Número de usuários)")
    IMPACT_CHOICES = [(3.0, 'Massivo'), (2.0, 'Alto'), (1.0, 'Médio'), (0.5, 'Baixo'), (0.25, 'Mínimo')]
    impact = models.FloatField("Impact", choices=IMPACT_CHOICES, null=True, blank=True)
    # Confidence entra na fórmula pelo valor literal (100, 80 ou 50), como define a Visão e Escopo.
    CONFIDENCE_CHOICES = [(100, 'Alta (100%)'), (80, 'Média (80%)'), (50, 'Baixa (50%)')]
    confidence = models.IntegerField("Confidence", choices=CONFIDENCE_CHOICES, null=True, blank=True)
    # Campo Effort próprio. Antes o código usava story_points como Effort
    # ("Esforço (Effort) é o próprio valor dos story_points"). O enunciado lista Effort entre
    # os critérios que o usuário atribui (requisito 17) e o Artefato 4 (HU20/HU21) trata Effort
    # como campo separado: mudar os Story Points não muda o Effort.
    # Pelo requisito 18 do enunciado, Effort "deve ser valor de pontos de história", por isso
    # ele usa a mesma escala dos Story Points (0, 1, 2, 3, 5, 8, 13, 21, 34 ou 55).
    effort = models.IntegerField("Effort", choices=STORY_POINTS_CHOICES, null=True, blank=True, help_text="Esforço na escala de pontos de história")

    # Situação da história dentro do Sprint (quadro Kanban: A fazer, Em desenvolvimento,
    # Concluída). Toda história começa "A fazer". No Product Backlog a situação não aparece e
    # volta a ser "A fazer" (ver save()), porque a história ainda não está em trabalho.
    SITUACAO_A_FAZER = 'a_fazer'
    SITUACAO_EM_DESENVOLVIMENTO = 'em_desenvolvimento'
    SITUACAO_CONCLUIDA = 'concluida'
    SITUACAO_CHOICES = [
        (SITUACAO_A_FAZER, 'A fazer'),
        (SITUACAO_EM_DESENVOLVIMENTO, 'Em desenvolvimento'),
        (SITUACAO_CONCLUIDA, 'Concluída'),
    ]
    situacao = models.CharField("Situação", max_length=20, choices=SITUACAO_CHOICES, default=SITUACAO_A_FAZER)

    # Responsável pela história: o dono ou um membro do projeto. É opcional ("Sem
    # responsável"). Se a pessoa sair do projeto, a história fica sem responsável (signals.py).
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='historias_responsavel', verbose_name="Responsável",
    )

    class Meta:
        # Restrições no banco. Os "choices" só limitam o formulário; um valor fora
        # da escala salvo por outro caminho (shell, script, outra view) entrava no banco.
        # A HU18 e a HU19 exigem que valores fora da escala sejam recusados e a história não
        # seja salva.
        constraints = [
            # Requisito 8: a história fica em um backlog por vez (Product ou Sprint).
            models.CheckConstraint(
                condition=(models.Q(product_backlog__isnull=True) |
                           models.Q(sprint_backlog__isnull=True)),
                name="historia_apenas_um_backlog",
            ),
            models.CheckConstraint(
                condition=Q(story_points__isnull=True) | Q(story_points__in=[0, 1, 2, 3, 5, 8, 13, 21, 34, 55]),
                name='historia_story_points_fibonacci',
            ),
            models.CheckConstraint(
                condition=Q(moscow__in=['', 'M', 'S', 'C', 'W']),
                name='historia_moscow_valido',
            ),
            models.CheckConstraint(
                condition=Q(impact__isnull=True) | Q(impact__in=[3.0, 2.0, 1.0, 0.5, 0.25]),
                name='historia_impact_valido',
            ),
            models.CheckConstraint(
                condition=Q(confidence__isnull=True) | Q(confidence__in=[100, 80, 50]),
                name='historia_confidence_valido',
            ),
            models.CheckConstraint(
                condition=Q(effort__isnull=True) | Q(effort__in=[0, 1, 2, 3, 5, 8, 13, 21, 34, 55]),
                name='historia_effort_fibonacci',
            ),
            models.CheckConstraint(
                condition=Q(situacao__in=['a_fazer', 'em_desenvolvimento', 'concluida']),
                name='historia_situacao_valida',
            ),
        ]

    # ------------------------------------------------------------------
    # Projeto ao qual a história pertence (pelo Product ou pelo Sprint Backlog)
    # ------------------------------------------------------------------
    @property
    def projeto(self):
        if self.product_backlog_id:
            return self.product_backlog.projeto
        if self.sprint_backlog_id:
            return self.sprint_backlog.projeto
        return None

    def clean(self):
        # Requisitos 7, 8 e 11: a história está sempre em exatamente um backlog, e o épico
        # ligado a ela precisa ser do mesmo projeto desse backlog (HU17).
        super().clean()
        if self.product_backlog_id and self.sprint_backlog_id:
            raise ValidationError("A história deve estar em apenas um backlog por vez.")
        if not self.product_backlog_id and not self.sprint_backlog_id:
            raise ValidationError("A história deve estar associada a um backlog.")
        backlog = self.product_backlog if self.product_backlog_id else self.sprint_backlog
        if self.epico_id and self.epico.projeto_id != backlog.projeto_id:
            raise ValidationError({"epico": "O épico e o backlog devem pertencer ao mesmo projeto."})
        # O responsável precisa participar do projeto (dono ou membro).
        if self.responsavel_id:
            projeto = backlog.projeto
            if self.responsavel_id != projeto.dono_id and not projeto.membros.filter(pk=self.responsavel_id).exists():
                raise ValidationError({"responsavel": "O responsável precisa ser o dono ou um membro do projeto."})

    def save(self, *args, **kwargs):
        # ModelForms já validam; esta chamada também protege criações pelo ORM.
        # Valida o estado efetivamente persistido quando save é parcial.
        # No Product Backlog a história ainda não está em trabalho: a situação volta a ser
        # "A fazer". Assim, se ela for para um Sprint de novo, entra na primeira coluna.
        if self.sprint_backlog_id is None and self.situacao != self.SITUACAO_A_FAZER:
            self.situacao = self.SITUACAO_A_FAZER
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"situacao"}
        update_fields = kwargs.get("update_fields")
        if update_fields and self.pk:
            persisted = type(self).objects.get(pk=self.pk)
            for field in update_fields:
                model_field = self._meta.get_field(field)
                setattr(persisted, model_field.attname, getattr(self, model_field.attname))
            persisted.clean()
        else:
            self.clean()
        return super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Cálculo RICE (Requisito 19)
    # ------------------------------------------------------------------
    RICE_INCOMPLETO = 'RICE incompleto'
    RICE_NAO_CALCULAVEL = 'não calculável'

    @property
    def rice_completo(self):
        return None not in (self.reach, self.impact, self.confidence, self.effort)

    @property
    def rice_score(self):
        # Cálculo RICE: (R x I x C) / E (Requisito 19)
        #  1. O divisor passou de story_points para effort (ver comentário do campo effort).
        #  2. Com algum campo vazio, devolve None ("RICE incompleto", HU20) em vez de calcular
        #     com valores padrão.
        #  3. Com Effort = 0, devolve None ("não calculável", HU21) em vez de 0. Devolver 0
        #     jogava a história para o fim da fila como se tivesse prioridade mínima.
        # Exemplo da HU21: R=500, I=2, C=80, E=5 -> (500 x 2 x 80) / 5 = 16000.
        if not self.rice_completo or self.effort == 0:
            return None
        return (self.reach * self.impact * self.confidence) / self.effort

    @property
    def rice_display(self):
        # Texto exibido nas telas e no admin para os três casos possíveis.
        if not self.rice_completo:
            return self.RICE_INCOMPLETO
        if self.effort == 0:
            return self.RICE_NAO_CALCULAVEL
        score = self.rice_score
        return f"{score:g}" if score == int(score) else f"{score:.2f}"

    @property
    def story_points_display(self):
        return "sem estimativa" if self.story_points is None else f"{self.story_points} pts"

    def __str__(self):
        return f"{self.titulo} (RICE: {self.rice_display})"


class CriterioAceitacao(models.Model):
    """Critério Dado/Quando/Então pertencente a uma história de usuário."""

    historia_usuario = models.ForeignKey(
        HistoriaUsuario,
        on_delete=models.CASCADE,
        related_name="criterios_aceitacao",
    )
    dado = models.TextField("Dado")
    quando = models.CharField("Quando", max_length=255)
    entao = models.TextField("Então")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Critério de aceitação da história {self.historia_usuario_id}"
