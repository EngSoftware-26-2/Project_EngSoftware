from django.contrib import admin
from .models import CriterioAceitacao, Projeto, ProductBacklog, SprintBacklog, Epico, HistoriaUsuario

# Regista os modelos simples
admin.site.register(Projeto)
admin.site.register(ProductBacklog)
admin.site.register(SprintBacklog)
admin.site.register(Epico)
admin.site.register(CriterioAceitacao)

# Configura a vista da História de Utilizador para mostrar a pontuação RICE na lista
@admin.register(HistoriaUsuario)
class HistoriaUsuarioAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'projeto_vinculado', 'epico', 'story_points', 'moscow', 'rice_score_display')
    
    def projeto_vinculado(self, obj):
        # Usa a propriedade projeto do model, que também encontra histórias que
        # estejam só num Sprint Backlog.
        return obj.projeto.nome if obj.projeto else "-"
    
    def rice_score_display(self, obj):
        # O rice_score agora pode ser None (RICE incompleto ou Effort = 0), e
        # round(None) quebrava a listagem. rice_display já devolve o texto certo para cada caso.
        return obj.rice_display
    rice_score_display.short_description = 'Pontuação RICE'
