# Card 02 — roadmap de execução

Matriz consolidada das etapas que faltam para o **Backup automático verificável**
deixar de ser "enviar arquivo, executar, baixar ZIP" e virar produto operado
pelo Live.

Baseline de partida: **`19d1064`** — núcleo 2.547 · backend 189 · frontend 79 ·
E2E 8 · cobertura 92,87%. Nenhuma contagem pode cair.

---

## 1. Matriz de etapas e dependências

Duas trilhas correm juntas. A **trilha G** constrói a plataforma (identidade,
agente, telas). As **capacidades 02.x** são o que o backup passa a saber fazer.
Uma capacidade só entra depois que a trilha G entrega o lugar onde ela mora.

### 1.1 Trilha G — plataforma

| Etapa | O que entrega | Depende de | Estado |
| --- | --- | --- | --- |
| **G.0** | `live_demo` → `apps/web` + `apps/api` | — | ✅ `9c77a3b` |
| **G.1** | Nome do card, modelo de capacidades, linguagem honesta | G.0 | ✅ `b671270` |
| **G.1.1** | Correções da homologação manual da G.1 | G.1 | ✅ `19d1064` |
| **G.2.1** | Modelo de dados multiempresa e persistência | G.1 | ✅ implementada |
| **G.2.2** | Identidade: OIDC Relying Party + sessão + guarda de organização | G.2.1 | ✅ implementada |
| **G.2.3** | Cofre de segredos com chave mestra externa | G.2.1 | ✅ implementada |
| **G.3.1** | Esqueleto do Agente: processo, configuração local, par de chaves Ed25519 | G.2.1 | ✅ implementada |
| **G.3.2** | Pareamento por código temporário e registro do dispositivo | G.3.1 · G.2.2 | ✅ implementada |
| **G.4.1** | Canal WSS de saída: autenticação por assinatura, heartbeat, reconexão | G.3.2 | ✅ implementada |
| **G.4.2** | Protocolo de comandos e telemetria (fila, entrega, idempotência) | G.4.1 | ✅ implementada |
| **G.5.1** | Raízes autorizadas, com consentimento **na própria máquina** | G.4.2 | ✅ implementada |
| **G.5.2** | Backup executado pelo Agente, com streaming (arquivo grande) | G.5.1 | ✅ implementada |
| **G.5.3** | Destinos reais: disco local, disco externo, pasta de rede | G.5.2 | ✅ implementada |
| **G.6** | Telas de operação: dispositivos e pastas | G.5.3 | ✅ implementada — a tela de política ficou para a G.7.4 |
| **G.7.1** | Diário de execuções no Agente e sincronização do histórico | G.6 | ✅ implementada |
| **G.7.2** | Pacotes resolvidos pelo nome: listagem e restauração sem caminho local | G.7.1 | ✅ implementada |
| **G.7.3** | Telas de histórico, artefatos e restauração guiada | G.7.2 | ✅ implementada |
| **G.7.4** | Tela de política: origens, destino, horário, retenção, retry, avisos | G.7.3 | ✅ implementada |
| **G.8.1** | O Agente sobe sozinho: registro no Agendador de Tarefas | G.5.2 | ✅ implementada |
| **G.8.2** | Pacote do Agente com só o que ele usa, baixável pelo Live | G.8.1 | ✅ implementada |
| **G.8.3** | Instalação guiada na tela: baixar, rodar, parear | G.8.2 · G.7.3 | ✅ implementada |
| **G.9** | Homologação dos 20 passos com navegador real | todas | ✅ 20/20 em 6m12s |
| **G.10** | Instalador de um clique: `.exe` único, sem Python, sem terminal | G.8 · G.9 | ✅ implementada |
| **G.2.4** | Reentrada pelo console, em servidor sem provedor de identidade | G.2.2 | ✅ implementada |
| **G.2.5** | Revogar corta o canal aberto e recusa comando | G.4.1 | ✅ implementada |

### 1.2 Capacidades do Card 02

| Etapa | O que entrega | Depende de | Estado |
| --- | --- | --- | --- |
| **02.A** | Segurança de caminhos, ciclos, ressalvas visíveis | — | ✅ `90193f5`, `5870838` |
| **02.B** | Assinatura HMAC com chave externa — autenticidade | 02.A · **G.2.3** | ✅ implementada |
| **02.C** | Criptografia AES e gestão da senha | 02.B · G.2.3 | ✅ implementada |
| **02.D** | VSS para arquivo aberto | **G.5.2** (só existe no Agente) | ✅ implementada · teste com elevação pendente |
| **02.E** | Agendamento, retry/backoff, notificações, retenção GFS | G.5.2 · **G.6** | ✅ implementada · envio de e-mail exige SMTP no cofre |
| **02.F** | Destino externo e conector S3 compatível | 02.C · G.5.3 | ✅ implementada · nuvem real pendente |
| **02.H** | Restauração guiada pela interface | 02.B · G.6 | ✅ implementada — tela na G.7.3 |
| **02.I** | Incremental por arquivo, com catálogo | 02.E | ✅ implementada |
| **02.J** | Hooks de segurança com falha fechada | G.6 | ✅ implementada |

### 1.3 Ordem de execução

A ordem abaixo respeita todas as dependências acima e não pula nada:

```
G.2.1 → G.2.2 → G.2.3 → 02.B → 02.C
      → G.3.1 → G.3.2 → G.4.1 → G.4.2
      → G.5.1 → G.5.2 → 02.D → G.5.3 → 02.F
      → G.6   → 02.E  → 02.I → 02.H → 02.J
      → G.7   → G.8
```

`02.A` e `G.0`/`G.1`/`G.1.1` já estão implementadas e não voltam à fila.
**`02.K` não existe** — a letra foi retirada quando as capacidades novas
passaram a ocupar H, I e J.

---

## 2. Decisão de identidade (OIDC) — recomendação

Pendência aberta desde a decisão **H-2**. Recomendação, com o porquê:

### 2.1 O AutoTarefas é *Relying Party*, nunca provedor de identidade

Guardar senha de cliente é assumir um passivo que o produto não precisa ter:
redefinição de senha, força bruta, vazamento, segundo fator, rotação. O
cliente-alvo — micro e pequena empresa — **já tem** identidade corporativa, em
Google Workspace ou Microsoft 365. Entrar com a conta que a pessoa já usa é
menos atrito e menos risco.

Fluxo: **Authorization Code + PKCE**, cliente confidencial (o segredo fica no
backend). O `id_token` é validado por assinatura contra o JWKS do provedor, com
conferência de `iss`, `aud`, `exp` e `nonce`. O token **nunca** vai para o
frontend: a sessão do navegador é um cookie próprio, `HttpOnly`, `SameSite=Lax`,
`Secure` em produção.

### 2.2 Provedor genérico, não um provedor amarrado

A configuração aponta para um `.well-known/openid-configuration`. Isso faz
Google, Microsoft Entra ID, Keycloak e Authentik funcionarem **por configuração**,
sem código novo. Começar amarrado a um SDK proprietário custaria uma migração
depois.

### 2.3 Como a organização nasce

O domínio verificado do e-mail define a organização. Domínio público
(`gmail.com`, `hotmail.com`, `outlook.com`) **nunca** entra em organização
alheia: vira organização pessoal. Entrar numa organização existente exige
convite explícito de quem administra, ou domínio que o administrador provou
controlar.

### 2.4 O que depende de você, e o que não depende

Registrar um cliente OAuth no Google ou na Microsoft é gratuito, mas exige a
**sua conta**. Para não travar o card nisso:

| Caminho | Real? | Precisa de você? |
| --- | --- | --- |
| **OIDC** com provedor configurado | sim — é o caminho do cliente | sim: `client_id` e `client_secret` |
| **Bootstrap de primeira execução** | sim — token de uso único impresso no console do servidor, como Jupyter, Grafana e Jenkins fazem | não |
| Provedor OIDC de teste | só na suíte automatizada | não |

O **bootstrap de primeira execução** é o que permite você homologar o produto
inteiro sem registrar nada: quando não existe nenhuma organização, o servidor
imprime **no console** uma URL de uso único, válida por poucos minutos, que cria
a primeira organização e o primeiro administrador. Não é login falso: é um
mecanismo real, de uso único, disponível só enquanto o banco está vazio.

Se nenhum provedor estiver configurado e já existir organização, a tela de
entrada **diz isso** — não oferece botão que não funciona.

**Pendência externa registrada:** teste do login OIDC contra um provedor real
(Google ou Entra) exige `client_id`/`client_secret` seus. Tudo o mais é
implementado e testado sem isso.

### 2.5 Banco de dados

A decisão **H-3** é PostgreSQL. A camada de persistência usa SQLAlchemy com
`DATABASE_URL`: **PostgreSQL em produção**, SQLite em desenvolvimento e na
suíte. Nenhum SQL específico de fornecedor é escrito, e o esquema é o mesmo nos
dois. Exigir um PostgreSQL de pé para rodar teste travaria a suíte sem ganho de
verdade.

---

## 2.6 Limitação registrada — migração de esquema

O esquema é criado por `create_all`. Enquanto o formato ainda muda a cada
subetapa, migração versionada seria retrabalho a cada commit. Quando as tabelas
estabilizarem (previsto ao fim da G.6), entra migração versionada. Registrado
como limitação, não como decisão definitiva.

---

## 2.7 Chave mestra — o que o dono precisa guardar

O cofre de segredos (chave de assinatura do manifesto, senha de criptografia,
credenciais de destino) e protegido por uma **chave mestra que o produto nunca
guarda**. Ela vem de `AUTOTAREFAS_MASTER_KEY` ou do cofre do sistema
operacional.

```bash
autotarefas cofre nova-chave
```

Sem a chave, o cofre fica **trancado** e quem depende dele falha com mensagem
clara. Não há queda silenciosa para uma chave embutida: chave embutida em
código publicado não protege nada, e daria a falsa impressão de que há
criptografia onde não há.

Perder a chave mestra é perder os segredos já cifrados. Isso é propositado, e o
comando avisa antes.

---

## 2.8 Verificações que exigem privilégio ou credencial

Registradas aqui para não se perderem, e **não** contadas como feitas.

| O quê | Por que não roda na suíte | Como verificar |
| --- | --- | --- |
| **Instantâneo de volume (VSS) real** | Criar instantâneo é operação administrativa do Windows; a suíte roda sem elevação | Rodar `pytest apps/agente/tests/test_vss.py` num terminal **como administrador**. Os dois testes de `TestComElevacao` deixam de ser pulados |
| **Login OIDC contra provedor real** | Exige `client_id`/`client_secret` registrados na conta do proprietário | Registrar um cliente OAuth no Google ou no Entra e configurar `OIDC_*` |
| **Envio de e-mail de aviso** | Exige um servidor SMTP: endereço, remetente e, quase sempre, credencial | Guardar `smtp.servidor` e `smtp.remetente` (e `smtp.usuario`/`smtp.senha`, se houver) no cofre da organização. Sem isso, o aviso **existe no histórico** e o registro diz que o e-mail não saiu, com o motivo |
| **Nuvem S3 real** | A suíte valida contra um servidor S3 compatível **local**, o que prova o protocolo e não a nuvem de ninguém | Guardar `s3.balde`, `s3.chave` e `s3.segredo` no cofre da organização, apontando para um endpoint autorizado, e rodar um backup com destino em nuvem |

Tudo o que **não** depende disso está implementado e testado: sem elevação, o
Agente **recusa** o instantâneo com o motivo — não tenta, não finge e não cai
em silêncio para o modo antigo. Esse caminho tem teste.

---

## 2.9 O que a G.6 entregou, e o que ficou para a 02.E

A G.6 entrega as telas do que **já existe**: primeiro acesso, entrada,
organização, dispositivos (parear, ver conexão, consultar pastas autorizadas,
executar agora, revogar).

A tela de **política** — horário, retenção, retry, notificação — ficou para a
02.E, e isso é decisão, não atraso. Desenhar a tela antes do motor produziria
campos que não configuram nada: exatamente o "botão sem função" que o produto
recusa. Quando o agendamento existir, a tela nasce sobre ele.

Três regras de honestidade estão nos testes da tela, não só no código:

- **"Conectado" vem da presença, não do cadastro.** Máquina cadastrada e
  desligada aparece como desligada.
- **Máquina desligada não é erro.** O servidor responde 409 e a tela diz "está
  desligada" — tratar como falha faria a tela acusar problema toda noite.
- **Sem provedor de identidade, não há botão de entrar.** A tela diz o que
  falta configurar.

E autorizar pasta **não** acontece na tela: ela mostra o que foi autorizado e
diz onde autorizar. O consentimento é dado na própria máquina.

---

## 2.10 O que o incremental **não** é

Implementado: incremental **por arquivo**, com catálogo local que guarda
tamanho, data, SHA-256 e **em qual pacote** cada arquivo está.

Não implementado, e não pode ser dito que está: **deduplicação** e **delta em
nível de bloco**. Um arquivo que muda um byte é copiado inteiro de novo — há
teste que verifica exatamente isso, para que ninguém planeje banda de upload
com números que não existem.

Consequência que a tela precisa dizer: um pacote incremental **não se sustenta
sozinho**. Ele depende dos pacotes anteriores que o manifesto cita, e a
conferência informa quais são. O padrão continua sendo o backup completo.

---

## 2.11 A guarda de ação destrutiva, e a saída que fica registrada

Restaurar por cima de arquivos existentes é a operação que não se desfaz. A
regra da 02.J é curta: **antes de substituir, prove que existe backup recente e
conferido daquilo**.

O que a guarda faz com cada situação:

| Situação | Decisão |
| --- | --- |
| Backup recente, conferido, com a corrente completa | libera |
| Backup mais velho que 26 h | bloqueia, dizendo a idade e o limite |
| Backup que não confere com o manifesto | bloqueia, dizendo o que não conferiu |
| Pacote incremental sem os anteriores na pasta | bloqueia, nomeando os que faltam |
| Nenhum pacote reconhecido na pasta | bloqueia, pedindo um backup |
| Pasta que não existe, ou que não deu para ler | **bloqueia** |

A última linha é a que separa uma proteção de um enfeite. Liberar "porque
provavelmente está tudo bem" transformaria a guarda numa formalidade que só
funciona quando não era necessária.

**A idade vem da data no nome do pacote**, não da data do arquivo. Copiar a
pasta de backups para outro disco atualiza a data de modificação de tudo, e a
guarda passaria a achar que há backup de hoje quando o mais novo é de janeiro.

**A saída existe, e é registrada.** `--dispensar-protecao MOTIVO` na linha de
comando, `dispensar_protecao` no pedido do Live: a substituição acontece e o
motivo entra no relatório da restauração, que vira registro de auditoria no
servidor. Uma proteção sem saída as pessoas desligam de vez; uma saída sem
registro ninguém sabe se estava ligada.

**Quem decide é o Agente**, na máquina. A pasta de proteção passa pela mesma
guarda de pastas autorizadas que o pacote e o destino — o Live não ganha o
direito de apontar para qualquer lugar do disco só porque o parâmetro se chama
"proteção". Se a decisão dependesse de o servidor lembrar de enviar o parâmetro
certo, ela seria uma convenção, e convenção não segura ninguém.

Limite conhecido: a guarda confere o pacote **mais recente** da pasta, e não se
aquele backup cobre exatamente os arquivos que serão substituídos. Cobrir isso
exigiria comparar o manifesto com o destino arquivo a arquivo; hoje não é feito,
e por isso não pode ser dito que é.

---

## 2.12 Como o backup de madrugada chega ao Live

O agendamento roda na máquina, com o navegador fechado — e, muitas vezes, com a
internet caída. Essa é a hora em que o backup mais importa e em que menos gente
está olhando.

Se o registro da execução dependesse de contar ao servidor, esse backup **não
existiria** no histórico. O Live mostraria uma noite vazia para uma noite em que
o backup foi feito, e o cliente concluiria — com razão — que não pode confiar na
tela.

Por isso o caminho é este, nesta ordem:

1. o Agente executa a política e **grava o resultado em disco**, no diário
   (`execucoes.jsonl`), antes de qualquer tentativa de envio;
2. quando o canal volta, ele manda o que ainda não foi entregue;
3. o servidor grava e **confirma** os identificadores que aceitou;
4. só a confirmação marca o registro como entregue no diário.

Detalhes que sustentam isso:

- **O identificador nasce na máquina.** É ele que torna o reenvio inofensivo:
  mandar de novo depois de uma queda no meio do envio não vira duas linhas no
  histórico. O servidor confirma o repetido também — para o Agente, "já está
  gravado" e "acabou de ser gravado" significam a mesma coisa.
- **Uma linha JSON por execução.** Acrescentar uma linha é a operação mais
  difícil de corromper: uma queda de energia estraga no máximo a última, e as
  anteriores continuam legíveis.
- **A poda nunca descarta o que não foi entregue.** Só as antigas já
  sincronizadas saem — perder uma pendente seria perder justamente o histórico
  que a queda de rede segurou.
- **A execução entra na organização do dispositivo**, não na que a mensagem
  disser, e a política citada só é aceita se for da mesma organização.
- **Resultado desconhecido vira falha, nunca sucesso.** Um Agente mais novo pode
  mandar algo que este servidor ainda não conhece; "backup ok" para algo que
  ninguém sabe o que foi é pior que um erro.

Prova: `apps/agente/tests/test_canal.py::TestHistoricoDoAgendamento` sobe o
backend de verdade numa porta livre, conecta com o cliente WebSocket de
produção e verifica que execuções gravadas offline aparecem na rota
`/api/historico` depois da reconexão.

---

## 2.13 Por que a tela pede pacote pelo nome

O Live nunca recebeu o caminho local de um pacote — recebeu a ficha do artefato,
que tem nome, tamanho e soma. O caminho revela a estrutura de pastas da empresa,
e mandá-lo ao servidor entregaria de graça um mapa que ninguém pediu.

Então a conversa acontece por **nome**. A tela diz `backup_2026-08-25_0200.zip`;
o Agente procura na pasta de pacotes que ele mesmo conhece e resolve para um
caminho real. Uma consequência útil cai de brinde: o servidor **não consegue
apontar para um arquivo arbitrário do disco**, porque não é ele quem escolhe a
pasta.

O nome é conferido antes de virar caminho. Nome com separador, com `..` ou fora
do formato do produto é recusado sem ser usado — se o nome virasse caminho, a
guarda de pastas autorizadas teria sido contornada pela porta dos fundos.

Isso também resolve um problema real que existia: a pasta padrão de pacotes fica
**ao lado** da primeira pasta autorizada, e não dentro dela (senão o pacote de
hoje entraria no backup de amanhã). Como consequência, ela não passa na guarda
de pastas autorizadas — e a restauração pela interface não teria como alcançar
os próprios pacotes que o Agente produziu.

O que continua passando pela guarda de pastas autorizadas: o **destino** da
restauração. É a única coisa que a tela escolhe de verdade, e escrever no disco
do cliente não pode ter porta mais larga que ler.

Para a sobrescrita, a tela envia `conferir_backup` em vez de um caminho: ela não
conhece pasta nenhuma da máquina, então pede "confira nos meus pacotes" e o
Agente resolve qual pasta é essa. `--protecao` com caminho continua existindo
para a linha de comando.

A listagem vem **do dispositivo**, não do banco: o servidor guarda a ficha do
artefato, mas quem sabe se o arquivo ainda está lá é a máquina. Listar do banco
ofereceria para restaurar um pacote que alguém já apagou.

---

## 2.14 A tela de restauração, e o que ela se recusa a fazer

Restaurar é o momento em que o backup prova que serviu — e é também o caminho
mais curto para perder arquivo por engano. Três decisões da tela existem só para
isso não acontecer:

1. **Ver antes de mexer.** O conteúdo do pacote aparece antes de qualquer
   escrita. Há teste que confere que nenhuma chamada de restauração sai enquanto
   a pessoa está apenas olhando.
2. **Preservar é o padrão.** Arquivo que já existe no destino não é tocado. Para
   substituir é preciso marcar explicitamente — e aí a operação passa pela
   guarda de ação destrutiva da 02.J.
3. **O destino sai de uma lista, não de um campo livre.** Só aparecem as pastas
   autorizadas **na própria máquina**. Pedir ao cliente que digitasse um caminho
   seria pedir que fizesse o trabalho da CLI dentro do navegador.

A tela também não arredonda o resultado. Uma restauração incompleta é anunciada
como **INCOMPLETA**, com o que faltou, o que foi recusado por tentar sair da
pasta e o que saiu diferente do manifesto. Uma restauração parcial que se
apresenta como sucesso é pior do que uma que falha: a pessoa vai embora achando
que recuperou tudo.

No histórico, "com ressalva" tem cor própria — não a de sucesso. Pintar de verde
um backup com ausências é a forma mais silenciosa de escondê-las de quem um dia
vai restaurar.

Detalhe pequeno que muda a experiência: o erro que o Agente devolve carrega o
nome da exceção (`ProtecaoBloqueou: ...`), útil no log da máquina e inútil na
tela. A interface mostra só a frase — que é a parte que diz o que resolver.

---

## 2.15 Como o Agente chega na máquina do cliente

Três coisas precisavam ser verdade para "instale o Agente" deixar de significar
"clone o repositório".

**Ele sobe sozinho.** Um Agente que só roda enquanto alguém deixa um terminal
aberto não é backup automático — é backup manual com passos a mais. O registro é
feito no **Agendador de Tarefas do Windows**, e não como serviço do Windows, por
três motivos concretos:

- serviço exige elevação sempre, inclusive para instalar, e isso trava a
  instalação de uma micro empresa na primeira tela;
- serviço roda como SYSTEM, que não enxerga mapeamento de rede do usuário — e
  pasta de rede é justamente um dos destinos do produto;
- o Agendador cobre os dois casos: **ao entrar** no Windows (sem elevação, que é
  o computador de escritório ligado de manhã) e **ao ligar** a máquina (com
  elevação, para quem quiser backup antes de alguém logar).

Fora do Windows, cada função recusa dizendo o motivo. Dizer "instalado" onde nada
foi instalado seria a pior mentira possível aqui: o cliente iria embora achando
que o backup roda sozinho.

**O pacote leva só o que o Agente usa.** Isto exigiu uma mudança no núcleo:
`autotarefas/tasks/__init__.py` passou a importar sob demanda (PEP 562). Antes,
`import autotarefas.tasks.backup` arrastava `pandas`, `playwright`, `bs4` e
`openpyxl` — e o instalador teria que listar tudo isso. Uma máquina de escritório
que faz backup não deve precisar de navegador automatizado para copiar uma pasta.
Resultado medido: **441 KB, 152 arquivos**, e `requisitos.txt` com 11 pacotes.

Também foi corrigido um risco silencioso: `websockets` era usado direto pelo
Agente mas vinha de carona no `uvicorn[standard]`. Um Agente instalado sem o
servidor ficaria sem o próprio transporte. Agora é dependência declarada.

**O download é real, e a tela diz o que vem.** O ZIP é montado na hora, a partir
do código que aquele servidor está rodando — guardar um pronto criaria a chance
de o cliente baixar uma versão mais velha que o servidor com quem vai conversar.
A tela mostra tamanho, número de arquivos e o requisito de Python **antes** do
clique; requisito escondido até o meio do caminho vira armadilha.

O que **não** entra no pacote importa mais que o que entra: nenhum `.env`, banco,
chave, `agente.json`, teste ou `__pycache__`. Segredo distribuído não se recolhe.
Há teste que varre a lista de nomes, e outro que **extrai o ZIP numa pasta vazia
e executa o Agente** — a diferença entre um arquivo com o conteúdo certo e um
instalador que funciona.

Limitação real, registrada: **o pacote exige Python 3.13 instalado**. Não há
executável único (PyInstaller) nesta versão. Isso está dito na primeira tela e no
LEIA-ME, e não escondido atrás de "instale e pronto".

---

## 2.16 A tela de política, e por que ela faltava

A matriz dizia que a G.6 tinha entregue "telas de operação: dispositivos, pastas,
política". As duas primeiras existiam; a terceira, não. Criar uma política de
backup exigia chamar a API na mão — ou seja, o produto tinha um requisito de
linha de comando escondido no meio do caminho, contra a regra mais dura do card:
o cliente não deve precisar de CLI para a operação normal.

Isso foi encontrado ao montar a homologação e está corrigido na G.7.4. A linha
da G.6 na matriz também foi corrigida: dizia mais do que ela entregou.

A tela cobre, num formulário só, o que a política precisa: pastas de origem
(vindas do dispositivo, não digitadas), destino e caminho, frequência e hora,
retenção GFS, tentativas e espera de retry, avisos por e-mail, e as opções de
como copiar — incremental, cifra, assinatura, verificação e VSS.

Quatro coisas ela se recusa a esconder:

1. **"Só nesta máquina" não é backup.** Quando o destino é esse, a tela diz — e
   continua deixando salvar, porque é um começo legítimo. O que não pode é a
   pessoa achar que está protegida.
2. **"Vai valer" não é "está valendo".** Máquina desligada recebe a política na
   próxima conexão, e a tela diz isso em vez de fingir que já aplicou.
3. **Máquina sem pasta autorizada não copiaria nada** — e o botão de salvar fica
   desabilitado, em vez de gravar uma política que nunca vai produzir pacote.
4. **Agendamento desligado é dito como desligado.** "Só executa quando alguém
   manda" é escolha válida; confundi-la com backup automático não é.

---

## 2.17 O que a homologação de ponta a ponta encontrou

Montar os vinte passos como teste de navegador real não foi só empacotar o que
já existia: quatro problemas apareceram **porque** o fluxo inteiro foi
percorrido, e nenhum deles era visível na suíte de unidades.

**1. A tela de política não existia.** A matriz dizia que a G.6 tinha entregue
"dispositivos, pastas, política". As duas primeiras existiam. Criar uma política
exigia chamar a API na mão — um requisito de linha de comando escondido no meio
do produto. Corrigido na G.7.4, e a linha da G.6 foi corrigida junto.

**2. "Executar agora" não usava a política.** O botão da tela de dispositivos
roda as pastas autorizadas para a pasta padrão, ignorando destino e incremental.
Alguém configuraria um destino externo, clicaria em executar, veria "concluído" —
e o pacote não teria ido para lá. Agora a política tem o próprio "Executar
agora", que manda exatamente as escolhas dela.

**3. A retenção apagava a base da corrente incremental.** Duas execuções no mesmo
dia: a regra diária guarda a mais nova e apaga a anterior — que era justamente a
base de que a mais nova depende. O pacote continuaria lá, com cara de inteiro, e
só não restauraria o que promete. Agora a retenção protege os pacotes citados
pela corrente dos que ela decidiu guardar.

**4. A tela dizia INCOMPLETA para uma restauração completa.** O relatório do
núcleo devolve `restaurados` como **contagem** e já traz `completa`; a interface
recalculava o veredito e fazia `.length` de um número — que é `undefined`. Toda
restauração bem-sucedida aparecia como incompleta. Agora quem decide é quem abriu
o pacote. O erro inverso — dizer "concluída" para uma restauração pela metade —
teria sido bem pior, e é a mesma linha de código.

Além desses, dois buracos de honestidade foram fechados no caminho:

- **Notificação só existia no caminho manual.** A falha de madrugada — a que
  ninguém viu acontecer — não avisava ninguém. Agora a execução sincronizada do
  agendamento passa pelo mesmo aviso, e o aviso escolhe a política **daquela**
  execução, não "alguma" política da máquina.
- **A trilha de auditoria não aparecia em lugar nenhum.** Ela era gravada e
  encadeada por hash desde a G.2.1, mas nenhuma tela a mostrava — e evidência que
  ninguém consegue olhar não serve de evidência. Agora há rota e seção no Live,
  com o selo de integridade em cima.

### Limites reais da homologação automática

- **Disco externo físico**: a suíte não tem como plugar um HD USB. A política do
  roteiro copia para outra pasta da mesma máquina, e a tela diz em voz alta que
  isso não protege contra o disco morrer. A outra metade **é** verificada: o
  passo 6 declara "disco externo" para uma pasta que não está num disco externo e
  a operação é **recusada**, com o motivo.
- **VSS**: exige elevação; continua na homologação manual.
- **E-mail**: sem SMTP no cofre não há envio. O passo 20 verifica que a trilha
  registra `notificacao.nao_enviada` com o motivo — que é o comportamento
  correto sem credencial, e não um silêncio.
- **Nuvem S3 real**: validada contra servidor compatível local; endpoint externo
  autorizado continua pendente.

---

## 2.18 O instalador de um clique, e por que ele era obrigatório

A primeira homologação manual travou no terceiro passo. O comando `.\instalar.ps1`
não foi encontrado — o extrator do Windows cria uma pasta em volta da que vem no
ZIP, e o terminal abriu um nível acima. Depois disso viria a política de
execução, e antes de tudo isso já era preciso ter Python instalado.

O diagnóstico não é "faltou uma instrução". É que **exigir terminal já é a
parede**: o produto promete "um clique e acabou o trabalho repetitivo", e a
instalação pedia conhecimento de programador.

Ter um Agente instalado **não** é desvio de rota. Nenhum navegador alcança
`D:\Financeiro`, e nenhum navegador roda às 2h da manhã fechado — isso é limite
do navegador, não escolha de projeto. O desvio era **como** se instalava.

### O que passou a existir

**Um executável, 29 MB, duplo clique.** Traz o Python dentro; a máquina do
cliente não instala nada.

**Ele já sabe de onde veio.** O Live cola endereço e código no fim do arquivo na
hora do download — um acréscimo de bytes, não um build por download (construir um
executável leva dezenas de segundos, e um download não espera). Tanto `.exe`
quanto ZIP ignoram sobra no fim, então o carimbo não atrapalha a execução.

**A pasta é escolhida no seletor do Windows.** A autorização continua sendo dada
**na máquina** — essa regra não afrouxou: a janela chama a mesma função que o
comando de linha chamava, com as mesmas recusas. O que mudou é que ela deixou de
ser um comando e virou um botão "Procurar…".

**O serviço sobe na hora**, sem esperar o próximo login. Sem isso a máquina só
apareceria conectada depois de reiniciar, e a pessoa fecharia a janela achando
que deu errado.

### O que o carimbo carrega, e o que nunca carrega

Endereço do servidor e código de pareamento. O código vale poucos minutos, serve
uma vez só e já aparece na tela de quem pediu — carregá-lo ali não cria exposição
nova. O servidor **confere de quem é o código** antes de colar: carimbar o que o
navegador mandou permitiria um instalador apontando para outra empresa.

Nunca entram: chave, senha, token de sessão, credencial de nuvem. Um instalador
que vazasse qualquer um deles seria um vazamento por download, e não há como
recolher. Há teste que verifica quais campos saem.

### O caminho com Python continua existindo

`formato=zip` no download pede o pacote com código mesmo havendo executável — há
máquina onde a política proíbe binário baixado, e há quem prefira ler antes de
rodar. A tela mostra **o roteiro do servidor que está atendendo**: com executável,
"dois cliques"; sem, o roteiro com Python — e aí ela diz, em voz alta, que o
executável ainda não foi gerado e qual comando o gera.

Prometer duplo clique onde só existe o pacote seria a mentira mais cara desta
tela: a pessoa baixaria, clicaria, e nada aconteceria.

### Limitações reais que continuam

- **O executável não é assinado.** O Windows SmartScreen vai avisar na primeira
  execução. Assinatura de código exige certificado pago em nome da empresa.
- **Só Windows.** O empacotamento é feito na máquina que publica, e o `.exe` sai
  para o sistema dela.
- **Ele não é versionado.** São 29 MB que incharia o histórico para sempre; um
  servidor recém-clonado o gera com `python tools/construir_agente.py`.

---

## 2.19 O que a segunda homologação manual encontrou

Três defeitos, e os três só aparecem quando alguém usa o produto de verdade por
mais de uma sessão.

### 1. O dono ficava trancado fora do próprio servidor

A sessão vence em 12 horas. Sem provedor OIDC configurado — que é o estado
normal de quem acabou de subir o Live — **não havia como entrar de novo**. Os
dados continuavam lá dentro, e o dono do lado de fora. A única saída era apagar
o banco.

Isso é o pior desfecho possível de um produto de backup: perder o acesso aos
dados que ele existe para proteger.

O mecanismo agora é o mesmo do primeiro acesso, e a razão é a mesma: **quem tem
o console da máquina já controla o serviço** — um link impresso ali não concede
nada que essa pessoa não pudesse tomar de outro jeito. Uso único, 30 minutos, e
**só quando não há provedor configurado**. Com OIDC no ar, nada é impresso:
manter as duas portas abertas seria manter uma que ninguém vigia ao lado de uma
com fechadura.

### 2. Revogar não revogava nada

O botão marcava o dispositivo como revogado no banco — e só. Na prática:

- o **canal já aberto continuava aberto**. O estado só é conferido no aperto de
  mão, e uma máquina conectada pode ficar assim por dias;
- os **comandos continuavam sendo aceitos**: backup e restauração funcionavam
  normalmente numa máquina que a organização tirou de serviço;
- a tela pintava o crachá pela **presença**, então um dispositivo revogado
  aparecia em **verde** — a cor dizia "em serviço" enquanto a palavra dizia
  "revogado", e a cor é o que se lê primeiro;
- e o backup respondia *"não há canal aberto"*, mandando a pessoa conferir o
  cabo de rede de uma máquina que ela mesma revogou.

Agora revogar **fecha o canal na hora** e a resposta diz se cortou agora ou se
vai cortar quando a máquina voltar — a diferença importa para quem revogou um
notebook roubado. Comando em máquina revogada é recusado com o motivo certo, nas
duas rotas (a genérica e a de backup, que tem caminho próprio). A tela pinta pelo
estado, esconde as ações e explica o que aconteceu.

A chave privada fica **na máquina do cliente**: não dá para apagá-la de longe. Se
o corte não acontece no servidor, ele não acontece.

### 3. O instalador autorizava uma pasta só

Uma empresa pequena guarda o que importa em mais de um lugar: `Documentos`, a
pasta do sistema de gestão, a planilha na área de trabalho. O assistente aceitava
a primeira e mandava procurar um comando para a segunda — devolvendo o terminal
pela porta dos fundos, que é exatamente o que ele existe para evitar.

Agora a tela lista as pastas escolhidas e aceita quantas a pessoa quiser. O botão
de concluir só habilita com pelo menos uma: sem pasta autorizada, aquele
computador não copia nada.

### E uma frase que tinha deixado de ser verdade

A tela de envio avulso ainda dizia *"Backup automático de pastas — ainda não
disponível... Ele ainda não existe."* O Agente existe há vários commits. Agora
ela explica a diferença entre os dois modos e aponta para onde a coisa mora:

> o envio avulso protege o que você **entrega**; o Agente protege o que você
> **tem**.

---

## 3. Regras que valem para todas as etapas

- Nada de agente falsamente conectado, botão sem função, status simulado,
  destino fictício, agendamento que dependa do navegador aberto, incremental só
  no nome ou restauração sem teste.
- Mock, fixture e MinIO existem **apenas** na suíte automatizada. Nenhum deles
  pode ser o caminho apresentado ao cliente.
- O limite de 10 MB é do **envio pelo navegador**, e só pode aparecer ali. O
  Agente processa arquivo grande por streaming, sem carregar na memória.
- Segredo nunca em texto puro, nunca no frontend, nunca no terminal, nunca no
  artefato, nunca no repositório.
- Conector S3 validado contra servidor compatível local **não** autoriza dizer
  "nuvem real homologada".
