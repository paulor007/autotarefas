# Card 02 — entrega para homologação final

Este documento reúne o que foi feito, o que foi provado, o que **não** foi
provado e o que depende de você. Ele existe para você não precisar confiar na
minha palavra em nada: cada afirmação aponta para um commit, um teste ou um
arquivo que você pode abrir.

**Status: IMPLEMENTADO, AGUARDANDO HOMOLOGAÇÃO FINAL.**
Quem homologa é você, com o roteiro de
[02-homologacao-manual.md](02-homologacao-manual.md).

---

## 1. O que mudou no produto

Antes, "backup" no Live era: escolher arquivos no navegador, executar à mão,
baixar um ZIP. Isso ainda existe — e continua limitado a 10 MB, que é limite do
**envio pelo navegador**, não do produto.

Agora existe o outro caminho, que é o do produto de verdade:

1. o cliente cria a organização com o convite impresso no console do servidor;
2. baixa o Agente **pela própria tela**, com tamanho e requisitos ditos antes do
   clique;
3. instala e pareia com um código temporário;
4. autoriza pastas **na própria máquina** — nenhuma tela na nuvem concede acesso
   ao disco de ninguém;
5. cria uma política pelo Live: pastas, destino, horário, retenção GFS, retry,
   avisos, incremental, cifra, assinatura, verificação, VSS;
6. o backup roda **no horário, com o navegador fechado**, porque o agendamento
   vive na máquina;
7. o histórico, a saúde do dispositivo, os artefatos e a trilha de auditoria
   aparecem no Live — inclusive o que rodou de madrugada com a internet caída;
8. restaura por fluxo guiado, com o conteúdo do pacote à vista antes de escrever
   qualquer coisa;
9. ação destrutiva só acontece com prova de backup recente e conferido.

---

## 2. Matriz de etapas concluídas

A matriz completa, com dependências e ordem, está em
[02-roadmap-execucao.md](02-roadmap-execucao.md). Todas as etapas listadas lá
estão implementadas.

| Trilha | Etapas |
| --- | --- |
| **Plataforma (G)** | G.0, G.1, G.1.1, G.2.1–G.2.3, G.3.1–G.3.2, G.4.1–G.4.2, G.5.1–G.5.3, G.6, G.7.1–G.7.4, G.8.1–G.8.3, G.9 |
| **Capacidades (02.x)** | 02.A, 02.B, 02.C, 02.D, 02.E, 02.F, 02.H, 02.I, 02.J |

`02.K` não existe — a letra foi retirada quando as capacidades novas passaram a
ocupar H, I e J. `02.G` **é** a trilha G inteira.

---

## 3. Um commit por subetapa

Partindo de `19d1064`, na ordem:

| Hash | Subetapa | O que entregou |
| --- | --- | --- |
| `6d424ce` | — | Matriz consolidada e decisão de identidade (OIDC) |
| `b3ec3e5` | G.2.1 | Modelo multiempresa com isolamento estrutural |
| `cc91cb9` | G.2.2 | Identidade OIDC, sessão própria, primeiro acesso |
| `c389e7b` | G.2.3 | Cofre de segredos com chave mestra fora do repositório |
| `2fdad84` | 02.B | Assinatura HMAC fecha o buraco da adulteração intencional |
| `c519b4b` | 02.C | Pacote cifrado em AES-256 no padrão WinZip |
| `9b267f5` | G.3.1 | Esqueleto do Agente: identidade Ed25519, configuração local |
| `1fb4098` | G.3.2 | Pareamento por código temporário, das duas pontas |
| `49ea17a` | G.4.1 | Canal de saída autenticado por assinatura |
| `4bc9586` | G.4.2 | Protocolo de comandos com idempotência |
| `14667ba` | G.5.1 | Pastas autorizadas na própria máquina, com falha fechada |
| `d9da5c8` | G.5.2 | Backup executado pelo Agente, com streaming medido |
| `b69f957` | 02.D | Instantâneo de volume (VSS) para copiar arquivo aberto |
| `e389493` | G.5.3 | Destinos reais, com conferência no próprio destino |
| `84f41ab` | 02.F | Conector S3 compatível, com conferência do objeto enviado |
| `3967c3a` | G.6 | Telas de primeiro acesso, entrada e dispositivos |
| `05e5e3b` | 02.E | Política, agendamento na máquina, retry e retenção GFS |
| `b38bbdf` | 02.I | Backup incremental por arquivo, com catálogo |
| `4972f41` | 02.H | Restauração, com as quatro guardas que ela exige |
| `6b176cb` | 02.J | Antes de destruir, prove que existe backup |
| `131e9f2` | G.7.1 | O backup de madrugada aparece no Live |
| `fd699b6` | G.7.2 | A tela pede pacote pelo nome; a máquina resolve onde ele está |
| `5b1f2ce` | G.7.3 | Histórico e restauração guiada no Live |
| `6483f37` | G.8 | O Agente sobe sozinho, e o cliente consegue instalá-lo |
| `9579119` | G.7.4 | A tela de política, que faltava para o Live bastar |
| `ec97a5a` | G.9 | A homologação de ponta a ponta, e os seis buracos que ela achou |

---

## 4. Diff consolidado

`19d1064..HEAD`: **121 arquivos, 27.419 linhas acrescentadas, 107 removidas.**

| Área | Linhas tocadas |
| --- | --- |
| Núcleo (`src/autotarefas`) | 2.548 |
| Backend (`apps/api`) | 7.703 |
| Agente (`apps/agente`) | 9.417 |
| Frontend (`apps/web`) | 3.853 |
| Testes do núcleo (`tests/`) | 3.110 |
| Documentação | 786 |

As 107 remoções são o que mudou de lugar ou deixou de ser verdade — nenhuma
reescrita de commit anterior.

---

## 5. Contagens finais e cobertura

| Suíte | Antes (`19d1064`) | Agora |
| --- | --- | --- |
| Núcleo | 2.547 | **2.705** |
| Backend + Agente | 189 | **576** (+2 pulados) |
| Frontend | 79 | **135** |
| E2E com navegador real | 8 | **28** |
| Cobertura do núcleo | 92,87 % | **92,76 %** |

A cobertura caiu 0,11 ponto porque o núcleo cresceu com código que o Agente
exercita (o caminho da corrente incremental, por exemplo) e que a suíte do
núcleo cobre parcialmente. Nenhum baseline de contagem caiu.

Os 2 pulados são os testes de VSS que exigem elevação — eles pulam com o motivo
dito, e não passam em silêncio.

---

## 6. Validações estáticas e de segurança

| Ferramenta | Resultado |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 345 arquivos já formatados |
| `mypy src` (strict) | Success: no issues found in 126 source files |
| `bandit -r src apps` | Nenhum achado |
| `detect-secrets` | Passed |
| `tsc --noEmit` (frontend) | sem erros |

---

## 7. A homologação automática dos 20 passos

`tests/e2e/test_homologacao_card_02_e2e.py` — **20/20 em 6m12s.**

Nada é simulado: backend `uvicorn` num banco temporário, frontend servido do
`dist/` pelo próprio backend, Agente rodando **a partir do ZIP que a tela oferece
para baixar**, e Chromium clicando na tela.

| Passo | O que prova |
| --- | --- |
| 1 | Organização e usuário nascem do convite do console |
| 2 | O pacote baixado da tela **executa** numa pasta vazia |
| 3 | Pareamento pelo código que a tela mostrou |
| 4 | Pasta autorizada na máquina; dispositivo aparece Conectado |
| 5 | Política criada pela tela, sem CLI e sem API na mão |
| 6 | "Disco externo" para uma pasta que não é de disco externo é **recusado** |
| 7 | Execução imediata com as escolhas da própria política |
| 8 | Horário marcado e navegador **fechado** |
| 9 | Pacote novo aparece no disco sem ninguém olhando (116 s de espera real) |
| 10 | Reabrir o Live não pede login de novo |
| 11 | O que rodou de madrugada aparece marcado como "Pelo horário agendado" |
| 12 | O pacote confere com o manifesto |
| 13 | O destino recebeu o pacote, com o mesmo SHA-256 |
| 14 | Restauração guiada devolve o arquivo com o conteúdo original |
| 15–17 | Arquivo alterado é copiado; os demais vêm do pacote anterior |
| 18 | Arquivo de 12 MB atravessa inteiro |
| 19–20 | Falha provocada, **duas** tentativas registradas, notificação e trilha íntegra |

Os dois passos longos (116 s e 206 s) são espera real por agendamento. Não há
relógio falso: se o agendador não disparasse, o teste falharia.

---

## 8. Capturas do fluxo

Em [capturas-02/](capturas-02/), geradas **pelo teste que passou** — não por uma
sessão manual que ninguém viu:

| Arquivo | Momento |
| --- | --- |
| `01-organizacao-criada.png` | Empresa criada pelo convite |
| `02-instalacao-guiada.png` | Download do Agente, código e comando |
| `03-dispositivo-conectado.png` | Máquina conectada, com as pastas autorizadas |
| `04-politica-e-execucao.png` | Política salva e backup concluído |
| `05-historico-com-agendamento.png` | Execução do horário no histórico |
| `06-restauracao-concluida.png` | Restauração guiada |
| `07-retry-e-auditoria.png` | Falhas do retry e trilha íntegra |

---

## 9. Pacote do Agente

Montado pelo servidor, na hora, a partir do código que ele está rodando:
**442 KB, 152 arquivos**. Guardar um ZIP pronto deixaria o cliente baixar uma
versão mais velha que o servidor com quem vai conversar.

Contém: `apps/agente/agente/`, `autotarefas/`, `requisitos.txt` (11 pacotes),
`instalar.ps1` e `LEIA-ME.txt`.

Não contém — e há teste varrendo a lista: `.env`, banco, chave, `agente.json`,
testes, `__pycache__`. Outro teste **extrai o ZIP numa pasta vazia e executa o
Agente**, que é a diferença entre um arquivo com o conteúdo certo e um instalador
que funciona.

---

## 10. Limitações reais

**O que o produto não faz, e não diz que faz:**

- **Não há executável único.** O pacote exige Python 3.13 instalado, e isso está
  dito na primeira tela e no LEIA-ME.
- **Não há deduplicação nem delta em nível de bloco.** O incremental é por
  arquivo: um arquivo que muda um byte é copiado inteiro. Há teste que verifica
  exatamente isso, para ninguém planejar banda com números que não existem.
- **Não há tela de edição de política.** Mudar o horário significa remover e
  criar de novo.
- **Retenção GFS colapsa execuções do mesmo dia.** Duas rodadas no mesmo dia
  guardam uma. A base de uma corrente incremental é protegida (não é apagada
  enquanto sustentar um pacote guardado), mas o pacote intermediário some.
- **`ONLOGON` é o padrão do serviço.** O Agente sobe quando alguém **entra** no
  Windows. Para rodar com a máquina ligada e ninguém logado, é preciso
  `--ao-ligar` num terminal de administrador.
- **Migração de esquema não existe.** O banco é criado por `criar_esquema()`;
  não há Alembic. Uma mudança de modelo em produção exigiria migração manual.

---

## 11. O que depende de você — credenciais e hardware

Estas quatro verificações **não foram feitas**, e não estão marcadas como feitas
em lugar nenhum:

| Pendência | Por quê | O que preciso de você |
| --- | --- | --- |
| **Disco externo físico** | A suíte não tem como plugar um HD USB | Um pen drive ou HD externo, e rodar o passo 5 do roteiro manual apontando para a letra dele |
| **VSS com elevação** | Instantâneo de volume exige administrador | Um terminal como administrador e uma planilha aberta |
| **Envio de e-mail** | Não há SMTP no cofre | Servidor, porta, usuário, senha e remetente para gravar no cofre |
| **Nuvem S3 real** | Validada só contra servidor compatível local (moto) | Endpoint autorizado, chave e bucket |

Sobre a nuvem: o conector foi exercitado contra um servidor S3 **de verdade** em
modo servidor — assinatura v4 real, multipart real, leitura de volta do objeto.
Isso **não** autoriza dizer "nuvem real homologada", e não está dito.

---

## 12. Comprovação de que não há botão, status ou integração fictícia

Cada item da sua lista de proibições, e onde ele é impedido:

| Proibição | Como o produto impede |
| --- | --- |
| **Agente falsamente conectado** | "Conectado" vem da **presença** (canal aberto agora), nunca do cadastro. `apps/api/app/canal.py::Presenca` é memória do processo, de propósito: um registro em banco sobreviveria a uma queda do servidor dizendo que a máquina está online |
| **Botão sem função** | Sem provedor OIDC configurado, a tela **diz isso** em vez de mostrar "Entrar". O download do Agente aponta para um ZIP montado na hora. Teste: `InstalarAgente.test.tsx` |
| **Status simulado** | "Com ressalva" tem cor própria, não a de sucesso. Resultado desconhecido vindo do Agente vira **falha**, nunca sucesso |
| **Destino externo fictício** | O tipo do destino é perguntado ao **sistema** (`GetDriveTypeW`), não ao texto digitado. Declarar "externo" para uma pasta local é recusa — passo 6 da homologação |
| **Confirmação de nuvem sem consulta real** | O envio S3 relê o objeto e compara o SHA-256 antes de dizer que chegou |
| **Agendamento que depende do navegador aberto** | O agendador vive na máquina, gravado em disco. Passo 9: o pacote aparece com o navegador fechado |
| **Incremental apenas nominal** | O manifesto cita, por arquivo, em qual pacote o conteúdo está. Passo 17 confere que o alterado foi copiado e os demais não |
| **Restauração sem teste** | Passos 12 e 14, mais `tests/tasks/test_restauracao.py`. E a tela deixou de recalcular o veredito: quem decide é quem abriu o pacote |
| **Rota de cliente baseada em mock** | Mock, fixture e moto existem **apenas** em `tests/` e `apps/*/tests/`. Nenhuma rota do produto os importa |

---

## 13. Como repetir tudo

```bash
python -m playwright install chromium
npm --prefix apps/web run build
python -m pytest tests/e2e/test_homologacao_card_02_e2e.py -p no:randomly
```

E, para as suítes completas:

```bash
python -m pytest tests && python -m pytest apps --no-cov && npm --prefix apps/web run test -- --run
```
