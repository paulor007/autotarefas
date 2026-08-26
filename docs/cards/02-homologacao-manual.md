# Card 02 — roteiro único de homologação manual

Este é o roteiro para **você** conferir o produto com as próprias mãos. Ele
cobre os mesmos vinte passos que a suíte automatizada percorre com navegador
real (`tests/e2e/test_homologacao_card_02_e2e.py`), mais os quatro que só uma
pessoa com hardware e credenciais consegue fazer.

Cada passo diz **o que fazer**, **o que precisa acontecer** e, quando existe,
**o que provaria que está mentindo**. Este último é o que separa uma conferência
de um passeio pela tela.

---

## Antes de começar

Você vai precisar de:

- Python 3.13 na máquina que será protegida;
- uma pasta com alguns arquivos de teste (**não use a sua planilha real**);
- opcional, mas recomendado: um **pen drive ou HD externo** — é o único jeito de
  homologar destino externo de verdade.

Suba o Live:

```bash
python -m uvicorn apps.api.app.main:app --port 8000
```

O console imprime, uma única vez, o endereço de primeiro acesso com o convite.
Ele vale 30 minutos e serve uma vez só.

> **O que provaria mentira:** abrir `http://localhost:8000` sem o convite e
> conseguir criar organização assim mesmo.

**Se você já criou a organização antes e a sessão venceu:** o console imprime,
a cada partida, um link de reentrada — porque sem provedor OIDC configurado ele
é o único jeito de entrar. Vale uma vez, 30 minutos. Com OIDC configurado, nada
é impresso e o caminho é o provedor.

---

## Parte 1 — a empresa e a máquina

### 1. Criar organização e usuário

Abra o endereço impresso no console, preencha nome da empresa, seu e-mail e seu
nome, e clique em **Criar organização**.

**Precisa acontecer:** a tela passa a mostrar o nome da empresa e o seu papel.

> **O que provaria mentira:** abrir o mesmo link de novo e conseguir criar uma
> segunda organização. O convite é de uso único.

### 2. Baixar o Agente

Em **Dispositivos**, clique em **Parear nova máquina**. A tela mostra o nome do
arquivo, o tamanho e se precisa de Python — **antes** do clique. Baixe.

**Precisa acontecer:** o download é um `.exe` de ~29 MB, e a tela diz "não
precisa instalar mais nada".

> **Se a tela disser que precisa de Python 3.13:** este servidor ainda não gerou
> o executável. Quem administra o servidor roda
> `python tools/construir_agente.py`. Até lá o download é o pacote com código, e
> o roteiro é o da seção "Caminho alternativo", no fim.

### 3. Instalar e parear — dois cliques

Dê **dois cliques** no arquivo baixado.

**Precisa acontecer:**

1. abre uma janela dizendo o endereço do seu Live — você não digitou nada;
2. clique em **Começar**. Ele registra a máquina e mostra a **impressão
   digital**;
3. confira se é a mesma que aparece no Live, na lista de dispositivos.

> **O que provaria mentira:** a janela pedir endereço e código. Isso significa
> que o carimbo não chegou no arquivo — e a promessa de "um clique" não se
> cumpriu.

> **O Windows vai avisar** que o programa não é reconhecido (SmartScreen). É
> esperado: o executável não é assinado, e assinatura exige certificado pago.
> Está registrado como limitação.

### 4. Autorizar as pastas

Na mesma janela, clique em **Adicionar pasta…** e escolha. Repita para quantas
quiser — a lista vai crescendo.

**Precisa acontecer:** cada pasta escolhida aparece na lista; **Concluir** só
habilita com pelo menos uma. Ao concluir, a janela diz que o Agente vai subir
junto com o Windows. No Live, o dispositivo aparece como **Conectado** — sem
reiniciar nada.

**Leia a última tela com atenção.** Ela diz por qual caminho o Agente vai subir,
e os dois não prometem a mesma coisa:

- *"dispara quando alguém entra no Windows"* — tarefa no Agendador;
- *"dispara quando VOCÊ entra no Windows"* — lista de logon do seu usuário, que
  é a queda usada quando o Agendador pede administrador. Nesse caso o backup roda
  com o navegador fechado, mas **não** com a máquina deslogada.

Para o backup rodar com a máquina ligada e ninguém logado, é preciso instalar
como administrador.

> **O que provaria mentira:** a janela dizer que vai subir sozinho e **não haver
> registro nenhum** na máquina. Confira:
>
> ```bash
> schtasks /Query /TN "AutoTarefas Agente"
> ```
>
> e, se não houver tarefa:
>
> ```bash
> Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "AutoTarefas Agente"
> ```
>
> Um dos dois tem que existir. Isso já falhou uma vez: o instalador terminava
> dizendo que estava tudo certo, e não havia registro em lugar nenhum.

> **O que provaria mentira:** existir qualquer botão **no Live** que autorize
> pasta. Não existe, e é de propósito: uma tela na nuvem não concede acesso ao
> disco de ninguém. O seletor de pastas roda na sua máquina, e passa pelas mesmas
> recusas do comando de linha.

> **O outro jeito de provar mentira:** terminar com "tudo certo" sem você ter
> escolhido pasta. Se faltar pasta, a última tela tem que dizer que este
> computador **não copia nada**.

---

## Parte 2 — a política e a execução

### 5 e 6. Criar política e escolher destino

Em **Políticas de backup**, clique em **Nova política**. Escolha as pastas, o
destino, o horário, a retenção, o retry e os avisos. Marque **Copiar só o que
mudou**.

Se você tem um disco externo: escolha **Disco externo** e aponte para a letra
dele. Se não tem: escolha **Outra pasta desta máquina** — e note que a tela
avisa que isso **não protege** contra o disco morrer.

**Precisa acontecer:** ao salvar, a tela diz se a política **já foi aplicada** na
máquina ou se vale a partir da próxima conexão.

> **O que provaria mentira:** escolher "Disco externo" apontando para uma pasta
> do `C:` e o backup acontecer assim mesmo. Tem que ser **recusado**, com o
> motivo.

### 7. Executar com o navegador aberto

Clique em **Executar agora** na política.

**Precisa acontecer:** "Backup concluído" com o nome do pacote; o arquivo existe
na pasta de backups **e** no destino escolhido.

### 8. Fechar o navegador

Ajuste o horário da política para dois minutos à frente (remova e crie de novo —
não há tela de edição nesta versão) e **feche o navegador**.

### 9. Executar pelo agendamento

Espere o horário passar. Não abra nada.

**Precisa acontecer:** um pacote novo aparece na pasta de backups, sem ninguém
tocar em nada.

> **O que provaria mentira:** o pacote só aparecer quando você reabrir o Live.
> O agendamento vive na máquina, não no navegador.

### 10 e 11. Reabrir o Live, conferir histórico e saúde

Abra o Live de novo.

**Precisa acontecer:** você continua logado; a execução de madrugada aparece no
histórico marcada como **"Pelo horário agendado"**, com o nome do pacote.

> **O que provaria mentira:** o histórico mostrar só o que você mandou fazer.

---

## Parte 3 — o backup serve para alguma coisa?

### 12. Conferir pacote e manifesto

```bash
autotarefas verificar caminho\do\pacote.zip
```

**Precisa acontecer:** todos os arquivos conferem com o manifesto.

> **O que provaria mentira:** editar um arquivo dentro do ZIP, recalcular o
> manifesto e a conferência passar. Com `AUTOTAREFAS_BACKUP_KEY` configurada,
> tem que acusar adulteração.

### 13. Confirmar presença no destino

Abra o destino (disco externo, pasta de rede) e confira que o pacote está lá,
com o mesmo tamanho.

### 14. Restaurar uma amostra

No Live, **Restaurar arquivos** → escolha o pacote → confira o conteúdo →
escolha a pasta e uma subpasta → **Restaurar**.

**Precisa acontecer:** "Restauração concluída", e os arquivos aparecem no disco
com o conteúdo original.

> **O que provaria mentira:** restaurar um pacote incremental e ele dizer
> "concluída" faltando arquivos. Se faltar, tem que dizer **INCOMPLETA** e listar
> o que ficou de fora.

---

## Parte 4 — incremental, arquivo grande e falha

### 15, 16 e 17. Alterar, executar de novo, comprovar incremental

Altere **um** arquivo. Clique em **Executar agora**.

**Precisa acontecer:** ao conferir o novo pacote, o arquivo alterado aparece
copiado e os demais aparecem como **inalterados**, citando o pacote anterior.

> **O que provaria mentira:** o pacote novo ter o mesmo tamanho do completo.
> Aí "incremental" seria só o nome.

### 18. Arquivo maior que 10 MB

Coloque um vídeo (ou qualquer arquivo com mais de 10 MB) na pasta e execute.

**Precisa acontecer:** o backup conclui e o arquivo está inteiro dentro do
pacote.

> **O que provaria mentira:** aparecer um limite de 10 MB. Esse limite é do
> **envio pelo navegador**, e nunca foi capacidade do produto.

### 19 e 20. Falha controlada, retry, notificação e auditoria

Crie uma política apontando para uma pasta de rede que não existe, com horário
próximo, **2 tentativas** e **1 minuto** de espera. Espere.

**Precisa acontecer:** o histórico mostra **duas** linhas de falha, a segunda
marcada como "tentativa 2", com o motivo. A trilha de **Auditoria** registra o
que aconteceu com a notificação — inclusive "não enviada", quando não há SMTP
configurado. O selo diz **Trilha íntegra**.

> **O que provaria mentira:** uma linha só. Aí não houve retry, houve desistência.

---

## Parte 4.1 — revogar corta de verdade

Este passo não estava na lista original. Ele entrou porque a primeira
homologação encontrou um botão que não fazia o que dizia.

Com a máquina **conectada**, clique em **Revogar** no dispositivo.

**Precisa acontecer:**

1. o crachá fica **vermelho**, escrito "Revogado";
2. os botões de executar e restaurar **somem** — máquina revogada não recebe
   comando;
3. o Agente na máquina perde a conexão na hora, sem esperar reiniciar.

> **O que provaria mentira:** o crachá continuar verde, ou os botões
> continuarem lá e funcionarem. A chave privada fica na máquina do cliente — se
> o corte não acontece no servidor, ele não acontece em lugar nenhum.

Para voltar a usar aquela máquina, pareie de novo. O pareamento antigo não volta.

---

## Parte 5 — o que só você pode homologar

Estes quatro dependem de hardware, privilégio ou credencial que a suíte
automatizada não tem. Eles estão **pendentes**, e não "feitos".

| O que | Por que depende de você | Como conferir |
| --- | --- | --- |
| **Disco externo físico** | A suíte não tem como plugar um HD USB | Política com destino **Disco externo** apontando para a letra do pen drive; o pacote tem que chegar lá |
| **VSS (arquivo aberto)** | Exige terminal como administrador | Deixe uma planilha **aberta**, marque "usar instantâneo" e execute. O arquivo tem que entrar no pacote |
| **E-mail de aviso** | Exige SMTP no cofre da organização | Configure o SMTP, provoque uma falha, confira o e-mail |
| **Nuvem S3 real** | Exige endpoint e credencial de terceiro | Configure a credencial no cofre, marque destino **Nuvem**, confira no bucket |

---

## Caminho alternativo — pacote com Python

Use quando o servidor ainda não gerou o executável, ou quando a política da
máquina proíbe binário baixado. Para forçar este formato mesmo havendo
executável, acrescente `?formato=zip` ao endereço do download.

1. extraia o ZIP. **Dentro dele há a pasta `AutoTarefas-Agente`** — é nela que o
   terminal precisa abrir. O extrator do Windows cria outra pasta em volta, e
   abrir o terminal no lugar errado dá "o termo não é reconhecido";
2. se o Windows recusar por política de execução:
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`;
3. `.\instalar.ps1 -Codigo SEU-CODIGO -Servidor http://localhost:8000`;
4. autorize a pasta:
   `.\venv\Scripts\python.exe -m apps.agente.agente autorizar C:\caminho\da\pasta`

> **O que provaria mentira:** o ZIP conter `.env`, banco, chave ou o
> `agente.json` de outro cliente. Abra e confira: só código, `LEIA-ME.txt`,
> `instalar.ps1` e `requisitos.txt`.

---

## Como repetir a homologação automática

```bash
python -m playwright install chromium
npm --prefix apps/web run build
python -m pytest tests/e2e/test_homologacao_card_02_e2e.py -p no:randomly
```

Ela sobe o backend de verdade, serve o frontend do `dist/`, extrai o pacote do
Agente que a própria tela oferece para baixar, roda o Agente como processo
separado e conduz o Chromium pelos vinte passos. Nada de transporte simulado:
socket de verdade, assinatura conferida de verdade, arquivos de verdade no
disco.
