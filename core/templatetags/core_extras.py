from django import template

register = template.Library()


# Iniciais do nome para o círculo do responsável no quadro do Sprint.
# Ex.: "Ana Souza" -> "AS"; "Bruno" -> "B"; sem nome usa a primeira letra do e-mail.
@register.filter
def iniciais(usuario):
    nome = (usuario.first_name or "").split()
    if nome:
        return "".join(parte[0] for parte in (nome[:1] + nome[1:][-1:])).upper()
    return (usuario.email or usuario.get_username() or "?")[0].upper()
