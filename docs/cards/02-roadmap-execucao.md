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
| **G.6** | Telas de operação: dispositivos, pastas, política | G.5.3 | ✅ implementada — política e destino vêm com 02.E |
| **G.7** | Saúde do dispositivo, histórico, artefatos e notificações | G.6 | a fazer |
| **G.8** | Empacotamento: serviço do Windows, instalador, download guiado | G.5.2 | a fazer |

### 1.2 Capacidades do Card 02

| Etapa | O que entrega | Depende de | Estado |
| --- | --- | --- | --- |
| **02.A** | Segurança de caminhos, ciclos, ressalvas visíveis | — | ✅ `90193f5`, `5870838` |
| **02.B** | Assinatura HMAC com chave externa — autenticidade | 02.A · **G.2.3** | ✅ implementada |
| **02.C** | Criptografia AES e gestão da senha | 02.B · G.2.3 | ✅ implementada |
| **02.D** | VSS para arquivo aberto | **G.5.2** (só existe no Agente) | ✅ implementada · teste com elevação pendente |
| **02.E** | Agendamento, retry/backoff, notificações, retenção GFS | G.5.2 · **G.6** | ✅ implementada · envio de e-mail exige SMTP no cofre |
| **02.F** | Destino externo e conector S3 compatível | 02.C · G.5.3 | ✅ implementada · nuvem real pendente |
| **02.H** | Restauração guiada pela interface | 02.B · G.6 | a fazer |
| **02.I** | Incremental por arquivo, com catálogo | 02.E | a fazer |
| **02.J** | Hooks de segurança com falha fechada | G.6 | a fazer |

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
