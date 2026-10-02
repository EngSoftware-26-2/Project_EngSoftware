from django.contrib import admin
from .models import Projeto, ProductBacklog, SprintBacklog, Epico, HistoriaUsuario

# Regista os modelos simples
admin.site.register(Projeto)
admin.site.register(ProductBacklog)
admin.site.register(SprintBacklog)
admin.site.register(Epico)

# Configura a vista da História de Utilizador para mostrar a pontuação RICE na lista
@admin.register(HistoriaUsuario)
class HistoriaUsuarioAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'projeto_vinculado', 'story_points', 'rice_score_display')
    
    def projeto_vinculado(self, obj):
        if obj.product_backlog:
            return obj.product_backlog.projeto.nome
        return "-"
    
    def rice_score_display(self, obj):
        return round(obj.rice_score, 2)
    rice_score_display.short_description = 'Pontuação RICE'