# Sistema de Gestão de Requisitos Ágeis

Projeto desenvolvido para a disciplina de **Engenharia de Software**.

---

## Sumário

1. [O que é este sistema?](#1-o-que-é-este-sistema)
2. [Palavras que aparecem no sistema](#2-palavras-que-aparecem-no-sistema)
3. [O que o sistema faz](#3-o-que-o-sistema-faz)
4. [O que você precisa antes de instalar](#4-o-que-você-precisa-antes-de-instalar)
5. [Instalação passo a passo](#5-instalação-passo-a-passo)
6. [Como abrir o sistema no navegador](#6-como-abrir-o-sistema-no-navegador)
7. [Como usar: primeiro acesso](#7-como-usar-primeiro-acesso)
8. [Como usar: as telas principais](#8-como-usar-as-telas-principais)
9. [Como desligar e como abrir de novo depois](#9-como-desligar-e-como-abrir-de-novo-depois)
10. [Problemas comuns e como resolver](#10-problemas-comuns-e-como-resolver)
11. [Para quem é da equipe: testes automáticos](#11-para-quem-é-da-equipe-testes-automáticos)
12. [Onde estão os documentos do projeto](#12-onde-estão-os-documentos-do-projeto)
13. [Participantes](#13-participantes)

---

## 1. O que é este sistema?

É um site que ajuda uma equipe a **organizar o que precisa ser feito em um projeto** de software.

Pense em um quadro de avisos com post-its: cada post-it é uma tarefa que alguém precisa fazer. O sistema guarda esses "post-its", diz quais são mais importantes, separa o trabalho em períodos curtos e mostra quem está fazendo o quê.

Ele segue um jeito de trabalhar chamado **Scrum**, muito usado por equipes de tecnologia.

O site roda **no seu próprio computador**. Não precisa de internet depois de instalado, e os dados ficam guardados em um arquivo dentro da pasta do projeto.

---

## 2. Palavras que aparecem no sistema

| Palavra | O que significa, em linguagem simples |
|---|---|
| **Projeto** | O trabalho da equipe. Ex.: "Aplicativo da biblioteca". |
| **Dono do projeto** | Quem criou o projeto. Pode editar, excluir e convidar pessoas. |
| **Membro** | Pessoa convidada para participar do projeto. |
| **História de usuário** | Uma tarefa escrita do ponto de vista de quem vai usar. Ex.: "Como **aluno**, eu quero **reservar um livro** para **não perder a viagem até a biblioteca**". |
| **Critério de aceitação** | Como saber que a história ficou pronta. Escrito no formato "Dado... Quando... Então...". |
| **Product Backlog** | A "lista de espera" com todas as histórias do projeto, da mais importante para a menos importante. |
| **Sprint** | Um período curto (até 30 dias) em que a equipe se compromete a terminar algumas histórias. |
| **Sprint Backlog** | As histórias escolhidas para um Sprint. |
| **Quadro Kanban** | Um quadro com três colunas: **A fazer**, **Em desenvolvimento** e **Concluída**. Mostra em que pé está cada história do Sprint. |
| **Épico** | Um grupo de histórias sobre o mesmo assunto. Ex.: "Pagamentos". |
| **Story Points** | Uma nota de "tamanho" da história (0, 1, 2, 3, 5, 8, 13...). Quanto maior, mais trabalhosa. |
| **MoSCoW** | Um jeito de dizer a importância: **M**ust (obrigatória), **S**hould (deveria ter), **C**ould (seria bom ter), **W**on't (não agora). |
| **RICE** | Uma conta que dá uma nota de prioridade usando Alcance, Impacto, Confiança e Esforço. O sistema faz a conta sozinho. |

---

## 3. O que o sistema faz

### Conta de usuário
- Criar uma conta com nome, e-mail e senha.
- Entrar e sair do sistema.
- Se algo for digitado errado, a mensagem aparece **embaixo do próprio campo**, dizendo exatamente o que corrigir.

### Projetos
- Criar, editar e excluir projetos.
- Convidar pessoas pelo e-mail (a pessoa precisa já ter conta no sistema).
- Remover membros (só o dono) ou sair de um projeto (membros).

### Histórias de usuário
- Criar, ver, editar e excluir histórias.
- Adicionar critérios de aceitação a cada história.
- Dar Story Points, prioridade MoSCoW e preencher os campos do RICE.
- Escolher um **responsável** (o dono ou um membro do projeto).
- Mover a história entre o Product Backlog e um Sprint.

### Avisos de boa prática
O sistema mostra um aviso (sem impedir nada) quando:
- a história tem **13 Story Points ou mais**: ela talvez seja grande demais e possa ser dividida;
- a história **não tem critério de aceitação**: fica difícil saber quando está pronta.

### Product Backlog
- Ver todas as histórias que ainda não entraram em um Sprint.
- Ordenar a lista por prioridade (MoSCoW ou nota RICE).

### Sprints e quadro Kanban
- Criar um Sprint com data de início e de fim.
- Ver o quadro Kanban do Sprint e mudar a situação de cada história.
- **Encerrar** o Sprint antes da data ou **cancelar** (informando o motivo).
- Ver o **histórico** de Sprints anteriores e o que ficou para depois.

Regras do Sprint:
- dura **no máximo 30 dias**;
- a data de início pode ser **de hoje até 1 ano à frente**;
- só existe **um Sprint por vez** em cada projeto;
- só o **dono do projeto** pode encerrar ou cancelar;
- quando o Sprint termina (encerrado, cancelado ou porque a data de fim passou), as histórias **não concluídas voltam sozinhas para o Product Backlog**.

### Épicos
- Criar épicos, colocar e tirar histórias deles.

---

## 4. O que você precisa antes de instalar

Você vai precisar de **dois programas gratuitos** e **dos arquivos do projeto**.

### 4.1 Python (obrigatório)

O Python é o "motor" que faz o sistema funcionar.

1. Entre em **https://www.python.org/downloads/**.
2. Clique no botão amarelo **Download Python** (versão 3.12 ou mais nova).
3. Abra o arquivo baixado.
4. **Windows: muito importante.** Na primeira tela do instalador, marque a caixinha **"Add python.exe to PATH"** antes de clicar em **Install Now**. Sem isso, os próximos passos não funcionam.
5. Termine a instalação.

### 4.2 Os arquivos do projeto

Escolha **um** dos dois jeitos.

**Jeito A: baixar um arquivo ZIP (mais fácil)**
1. Entre na página do projeto: **https://github.com/EngSoftware-26-2/Project_EngSoftware**
2. Clique no botão verde **Code** e depois em **Download ZIP**.
3. Encontre o arquivo na pasta *Downloads* e extraia (clique com o botão direito e escolha **Extrair tudo**).
4. Guarde a pasta extraída em um lugar fácil, por exemplo a **Área de Trabalho**.

**Jeito B: usar o Git (para quem é da equipe)**
1. Instale o Git em **https://git-scm.com/downloads**.
2. No terminal (veja o próximo passo), digite:
   ```
   git clone https://github.com/EngSoftware-26-2/Project_EngSoftware.git
   ```

---

## 5. Instalação passo a passo

A instalação é feita no **terminal**: uma janela onde você digita comandos. Não tenha medo: basta copiar cada comando deste guia, colar e apertar **Enter**.

> **Dica:** espere cada comando terminar (a janela volta a mostrar o cursor piscando) antes de digitar o próximo.

### Passo 1: Abrir o terminal dentro da pasta do projeto

**Windows**
1. Abra a pasta do projeto (aquela que tem o arquivo `manage.py`).
2. Clique na barra de endereço lá em cima, apague o que estiver escrito, digite `cmd` e aperte **Enter**.
3. Uma janela preta vai abrir, já dentro da pasta certa.

**Mac**
1. Abra o aplicativo **Terminal** (procure por "Terminal" no Spotlight, com Command + Espaço).
2. Digite `cd ` (com um espaço no final), **arraste a pasta do projeto** para dentro da janela e aperte **Enter**.

**Linux**
1. Abra a pasta do projeto, clique com o botão direito em um espaço vazio e escolha **Abrir no terminal**.

### Passo 2: Criar um "ambiente separado" para o projeto

Isso cria uma caixinha onde ficam as peças que o sistema usa, sem bagunçar o resto do computador. Só precisa ser feito **uma vez**.

| Windows | Mac e Linux |
|---|---|
| `python -m venv .venv` | `python3 -m venv .venv` |

### Passo 3: Ligar o ambiente

| Windows | Mac e Linux |
|---|---|
| `.venv\Scripts\activate` | `source .venv/bin/activate` |

Se deu certo, aparece **(.venv)** no começo da linha do terminal.

> Esse passo precisa ser repetido **toda vez** que você abrir um terminal novo.

### Passo 4: Instalar as peças do sistema

Igual para todos:
```
pip install -r requirements.txt
```
Vai aparecer bastante texto. É normal. Espere terminar.

### Passo 5: Preparar o banco de dados

O banco de dados é onde o sistema guarda contas, projetos e histórias.

| Windows | Mac e Linux |
|---|---|
| `python manage.py migrate` | `python3 manage.py migrate` |

Aparece uma lista de linhas terminando em **OK**. Está tudo certo.

> Rode este comando de novo sempre que baixar uma versão mais nova do projeto. Ele atualiza o banco sem apagar seus dados.

### Passo 6: Ligar o sistema

| Windows | Mac e Linux |
|---|---|
| `python manage.py runserver` | `python3 manage.py runserver` |

Quando aparecer a frase **"Starting development server at http://127.0.0.1:8000/"**, o sistema está ligado.

> **Não feche essa janela** enquanto estiver usando o sistema. Ela é o que mantém o site funcionando.

---

## 6. Como abrir o sistema no navegador

1. Abra o seu navegador (Chrome, Edge, Firefox, Safari...).
2. Na barra de endereço, digite:
   ```
   http://127.0.0.1:8000
   ```
3. Aperte **Enter**. A página inicial do sistema vai aparecer.

> Esse endereço só funciona **no mesmo computador** onde o sistema está ligado (passo 6 acima).

---

## 7. Como usar: primeiro acesso

### 7.1 Criar sua conta
1. Na página inicial, clique em **Cadastre-se**.
2. Preencha:
   - **Nome**: de 3 a 50 letras, começando com letra maiúscula, sem números. Ex.: *Ana Souza*.
   - **E-mail**: ex.: *voce@exemplo.com*.
   - **Senha**: de 8 a 64 caracteres, com pelo menos **uma letra maiúscula, uma minúscula, um número e um símbolo** (ex.: `!`, `@`, `#`). Ex.: *Senha@2026*.
3. Clique em **Cadastrar**.

Se algo estiver errado, a mensagem aparece embaixo do campo dizendo o que ajustar.

### 7.2 Entrar
1. Clique em **Entrar**.
2. Digite o e-mail e a senha que você cadastrou e clique em **Entrar**.

### 7.3 Sair
Clique em **Sair da Conta**.

---

## 8. Como usar: as telas principais

### 8.1 Criar um projeto
1. Depois de entrar, clique em **Criar Novo Projeto**.
2. Dê um nome e, se quiser, uma descrição.
3. Salve. Você passa a ser o **dono** desse projeto.

### 8.2 Convidar pessoas
1. Abra o projeto e clique em **Gerenciar Membros**.
2. Digite o e-mail da pessoa (ela precisa já ter criado uma conta) e clique em **Adicionar membro**.

### 8.3 Criar o Product Backlog
1. Dentro do projeto, abra **Product Backlog**.
2. Se ainda não existir, clique para criar. Ele é a lista de espera das histórias.

### 8.4 Escrever uma história de usuário
1. Vá em **Histórias** e clique em **Nova história**.
2. Preencha as três partes da frase: **Como um** (quem), **Eu quero** (o quê), **Para** (por quê).
3. Se quiser, escolha:
   - **Story Points** (tamanho);
   - **MoSCoW** (importância);
   - os campos do **RICE** (o sistema calcula a nota sozinho);
   - o **Responsável**.
4. Salve.
5. Abra a história e adicione pelo menos um **critério de aceitação** (Dado... Quando... Então...).

### 8.5 Montar um Sprint
1. Vá em **Sprints** e clique em **Novo Sprint Backlog**.
2. Escolha a data de início e a de fim (no máximo 30 dias entre elas).
3. Salve.
4. Em cada história que vai entrar no Sprint, use **Mover para** e escolha o Sprint.

### 8.6 Acompanhar no quadro Kanban
1. Abra o Sprint.
2. Você verá as três colunas: **A fazer**, **Em desenvolvimento** e **Concluída**.
3. Mude a situação de cada história conforme o trabalho anda.

### 8.7 Encerrar ou cancelar um Sprint (só o dono)
- **Encerrar Sprint**: o trabalho acabou (ou acabou antes do previsto).
- **Cancelar Sprint**: o Sprint deixou de fazer sentido. É preciso escrever o motivo.

Nos dois casos, as histórias que não foram concluídas voltam para o Product Backlog, e o Sprint vai para o **histórico**.

Se ninguém encerrar, o sistema encerra sozinho quando a data de fim passa.

### 8.8 Organizar por épicos
1. Vá em **Épicos** e clique em **Novo épico** (ex.: "Pagamentos").
2. Dentro dele, use **Adicionar histórias** para agrupar as histórias daquele assunto.

---

## 9. Como desligar e como abrir de novo depois

**Para desligar:** na janela do terminal, aperte **Ctrl + C** (no Mac também é Ctrl + C). Depois pode fechar a janela.

**Para abrir de novo outro dia** (não precisa instalar tudo de novo):
1. Abra o terminal dentro da pasta do projeto (Passo 1).
2. Ligue o ambiente (Passo 3).
3. Ligue o sistema (Passo 6).
4. Abra **http://127.0.0.1:8000** no navegador.

Seus dados continuam lá: eles ficam no arquivo `db.sqlite3`, dentro da pasta do projeto.

---

## 10. Problemas comuns e como resolver

| O que aparece | O que fazer |
|---|---|
| `'python' não é reconhecido como um comando` (Windows) | O Python foi instalado sem marcar **"Add python.exe to PATH"**. Abra o instalador de novo, escolha **Modify** (ou reinstale) e marque essa opção. Feche e abra o terminal. |
| `command not found: python` (Mac/Linux) | Use `python3` no lugar de `python`. |
| No Windows, o comando de ligar o ambiente dá erro de "execução de scripts" | Você está no **PowerShell**. Use o `cmd` (Passo 1) ou digite antes: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e responda **S**. |
| `No module named django` | O ambiente não está ligado. Faça o Passo 3 (deve aparecer **(.venv)**) e depois o Passo 4. |
| `no such table` ou `no such column` | O banco não está atualizado. Rode o Passo 5 (`migrate`). |
| `That port is already in use` | O sistema já está ligado em outra janela. Use aquela, ou feche-a com **Ctrl + C**. |
| O navegador diz "não é possível acessar esse site" | A janela do terminal com o sistema foi fechada. Ligue de novo (Passo 6). |

---

## 11. Para quem é da equipe: testes automáticos

O projeto tem testes que conferem sozinhos se as regras continuam funcionando. Com o ambiente ligado (Passo 3):

| Windows | Mac e Linux |
|---|---|
| `python manage.py test core` | `python3 manage.py test core` |

No final deve aparecer **OK**. Se aparecer **FAILED**, alguma regra quebrou e a mensagem mostra qual.

---

## 12. Onde estão os documentos do projeto

Todos os artefatos (documentos da disciplina) ficam na pasta **`artefatos`**, em PDF.

Também na pasta principal:
- `database_schema.sql` e `database_schema.dbml`: o desenho das tabelas do banco de dados.
- `requirements.txt`: a lista das peças que o Passo 4 instala.

---

## 13. Participantes

| Nome | Matrícula |

|Lucas Santana|211060666|

|Guilherme Kauã F. do Nascimento|222001449|
|  |  |
|  |  |
