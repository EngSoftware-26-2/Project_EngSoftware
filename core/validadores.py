# HU01 - Regras dos campos da conta (nome e senha).
# Cada regra tem a sua mensagem, para o usuário saber exatamente o que corrigir.
# Todas as regras que falharem aparecem juntas, embaixo do campo.
from django.core.exceptions import ValidationError

NOME_MIN = 3
NOME_MAX = 50
SENHA_MIN = 8
SENHA_MAX = 64
EMAIL_MAX = 100

NOME_DICA = f"{NOME_MIN} a {NOME_MAX} letras, iniciar com maiúscula. Ex.: Ana Souza"
EMAIL_DICA = "Ex.: voce@exemplo.com"
SENHA_DICA = f"{SENHA_MIN} a {SENHA_MAX} caracteres, com maiúscula, minúscula, número e símbolo (ex.: ! @ #)"


def validar_nome(valor):
    nome = valor.strip()
    erros = []

    if not NOME_MIN <= len(nome) <= NOME_MAX:
        erros.append(f"O nome deve ter entre {NOME_MIN} e {NOME_MAX} caracteres.")
    if any(c.isdigit() for c in nome):
        erros.append("O nome não pode conter números.")
    # isalpha() aceita letras com acento (João, Conceição).
    if any(not (c.isalpha() or c.isdigit() or c in " -'") for c in nome):
        erros.append("O nome só pode ter letras, espaços, hífen (-) e apóstrofo (').")
    if nome and not nome[0].isupper():
        erros.append("O nome deve começar com letra maiúscula.")
    if "  " in nome:
        erros.append("O nome não pode ter espaços duplos.")

    if erros:
        raise ValidationError(erros)
    return nome


def validar_senha(senha):
    erros = []

    if not SENHA_MIN <= len(senha) <= SENHA_MAX:
        erros.append(f"A senha deve ter entre {SENHA_MIN} e {SENHA_MAX} caracteres.")
    if not any(c.isupper() for c in senha):
        erros.append("A senha precisa de pelo menos uma letra maiúscula.")
    if not any(c.islower() for c in senha):
        erros.append("A senha precisa de pelo menos uma letra minúscula.")
    if not any(c.isdigit() for c in senha):
        erros.append("A senha precisa de pelo menos um número.")
    if not any(not c.isalnum() and not c.isspace() for c in senha):
        erros.append("A senha precisa de pelo menos um símbolo (ex.: ! @ # $).")

    if erros:
        raise ValidationError(erros)
    return senha
