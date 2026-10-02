from django.db import models
from django.contrib.auth.models import User

# (Requisito 4) CRUD de Projetos
class Projeto(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

# (Requisito 5) Product Backlog: pode existir só um por projeto
class ProductBacklog(models.Model):
    projeto = models.OneToOneField(Projeto, on_delete=models.CASCADE, related_name='product_backlog')
    
    def __str__(self):
        return f"Product Backlog - {self.projeto.nome}"

# (Requisito 6) Sprint Backlogs: podem existir vários por projeto
class SprintBacklog(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='sprint_backlogs')
    nome = models.CharField(max_length=100, help_text="Ex: Sprint 1")

    def __str__(self):
        return f"{self.nome} ({self.projeto.nome})"

# (Requisito 10) CRUD de Épicos
class Epico(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='epicos')
    titulo = models.CharField(max_length=200)

    def __str__(self):
        return self.titulo

# (Requisitos 7 a 19) História de Utilizador e Priorização
class HistoriaUsuario(models.Model):
    titulo = models.CharField(max_length=200)
    
    # Vinculações (Requisito 7, 8 e 11)
    product_backlog = models.ForeignKey(ProductBacklog, on_delete=models.CASCADE, related_name='historias', null=True, blank=True)
    sprint_backlog = models.ForeignKey(SprintBacklog, on_delete=models.SET_NULL, null=True, blank=True, related_name='historias')
    epico = models.ForeignKey(Epico, on_delete=models.SET_NULL, null=True, blank=True, related_name='historias')
    
    # Formato padrão da História (Requisito 9)
    papel = models.CharField(max_length=100, help_text="Como um [papel]...")
    acao = models.CharField(max_length=255, help_text="Eu quero [ação]...")
    beneficio = models.CharField(max_length=255, help_text="Para [benefício]...")

    # Formato padrão de Critérios de Aceitação (Requisito 13)
    contexto = models.TextField(help_text="Dado [contexto inicial]...")
    evento = models.CharField(max_length=255, help_text="Quando [evento]...")
    resultado = models.TextField(help_text="Então [resultado]...")

    # Story Points (Requisito 14 e 15)
    STORY_POINTS_CHOICES = [(0, '0'), (1, '1'), (2, '2'), (3, '3'), (5, '5'), (8, '8'), (13, '13'), (21, '21'), (34, '34'), (55, '55')]
    story_points = models.IntegerField(choices=STORY_POINTS_CHOICES, default=0)

    # MoSCoW (Requisito 16)
    MOSCOW_CHOICES = [('M', 'Must Have'), ('S', 'Should Have'), ('C', 'Could Have'), ('W', "Won't Have")]
    moscow = models.CharField(max_length=1, choices=MOSCOW_CHOICES, default='M')

    # Critérios RICE (Requisito 17 e 18)
    reach = models.IntegerField(default=0, help_text="Alcance (Número de usuários)")
    IMPACT_CHOICES = [(3.0, 'Massivo'), (2.0, 'Alto'), (1.0, 'Médio'), (0.5, 'Baixo'), (0.25, 'Mínimo')]
    impact = models.FloatField(choices=IMPACT_CHOICES, default=1.0)
    CONFIDENCE_CHOICES = [(100, 'Alta (100%)'), (80, 'Média (80%)'), (50, 'Baixa (50%)')]
    confidence = models.IntegerField(choices=CONFIDENCE_CHOICES, default=80)
    # Esforço (Effort) é o próprio valor dos story_points

    @property
    def rice_score(self):
        # Cálculo RICE: (R x I x C) / E (Requisito 19)
        if self.story_points == 0:
            return 0 
        return (self.reach * self.impact * self.confidence) / self.story_points

    def __str__(self):
        return f"{self.titulo} (RICE: {self.rice_score})"