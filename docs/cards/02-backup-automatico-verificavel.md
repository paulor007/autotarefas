# Card 02 — Backup automático verificável

**Status: IMPLEMENTADO, AGUARDANDO HOMOLOGAÇÃO FINAL.**
Todas as subetapas têm commit próprio e teste. Os vinte passos da homologação
passam com navegador real, backend real e Agente real
(`tests/e2e/test_homologacao_card_02_e2e.py` — 20/20).
**Nada aqui está homologado**: quem homologa é o proprietário, com o roteiro
de [02-homologacao-manual.md](02-homologacao-manual.md).
Documento de decisão aprovado conceitualmente pelo proprietário em 20/08/2026.

Este documento é o contrato funcional do card: o que ele resolve, o que promete,
o que **não** promete, e como cada capacidade chega ao cliente. Ele vale mais
pelo que recusa do que pelo que oferece.

---

## 1. Problema

Entre os problemas recorrentes de proteção de dados em empresas pequenas estão
a **rotina manual que não é executada** (o backup vira tarefa de segunda-feira e
morre na terceira semana), o **backup que nunca foi testado** (o arquivo existe,
mas ninguém sabe se abre) e a **cópia mantida no mesmo disco** (que não sobrevive
ao defeito do disco nem ao ransomware, que criptografa tudo o que alcança).

Dois desses três não são problemas de tecnologia — são de disciplina. E
disciplina não se resolve com um botão melhor: resolve-se tirando o humano do
caminho.

## 2. Cliente-alvo

Escritório de contabilidade, consultório, comércio, prestador de serviço, setor
administrativo de órgão público: de 1 a 20 pessoas, sem TI própria, Windows,
dados em pasta compartilhada ou no computador de alguém. Quem decide a compra é
o dono ou o administrativo, não um técnico.

**Consequência de projeto:** cada tela precisa ser compreendida por quem não
sabe o que é um arquivo ZIP.

## 3. Diferencial

O diferencial não é fazer backup — ferramenta que copia arquivo existe de graça
no Windows. É **poder provar que o backup serve**.

> Configure uma vez. O AutoTarefas protege sozinho, verifica a proteção, repete
> o que falhar e solicita intervenção apenas quando necessário.

Automação orientada a exceções: sucesso é registrado em silêncio; ressalva é
tratada automaticamente quando possível; só o que exige decisão humana vira
notificação — com explicação e ação recomendada.

## 4. Nome e descrição

**Nome: `Backup automático verificável`.**

"Verificável" é permanente e honesto: descreve o produto, não um estágio de
implementação. Não haverá renomeação automática do card quando a restauração de
amostra existir.

> **Este nome pertence ao produto, e só a ele.** A demonstração do Live aberto
> — envio avulso de arquivos, até 10 MB cada, empacotados uma vez — chamava-se
> igual, e as duas coisas conviviam na mesma página. Quem experimentava a
> demonstração concluía que já tinha backup automático. Ela passou a se chamar
> **`Compactar arquivos com comprovante`**, com o subtítulo "Experimente sem
> instalar nada", e vive em `/` (a vitrine). O produto vive em `/app`.
>
> "Empacotamento verificável" foi o primeiro nome tentado, e era jargão nosso:
> ninguém que administra uma padaria diz "empacotar" nem "verificável".
> "Compactar" e "comprovante" são palavras que a pessoa já usa.

O que evolui é o **estado de cada execução**, que carrega o nível de prova
alcançado:

```
Pacote íntegro
Destino verificado
Restauração de amostra aprovada
Restauração completa testada
```

**Descrição do card:**

> Configure suas pastas e destinos uma vez. O AutoTarefas faz o backup sozinho,
> guarda versões, confere se os arquivos podem ser recuperados e avisa apenas
> quando algo precisar de você.

Nomes recusados, por descreverem a implementação e não o problema:
`Backup compactado`, `Criar ZIP`, `Compactar arquivos`.

Fluxos manuais existem como porta de entrada, nunca como produto principal:
**Executar agora** (com agente) e **Proteger arquivos avulsos** (por upload).

## 5. Jornada de configuração

Cinco passos, uma única vez: instalar e parear o agente · escolher o que
proteger · escolher onde guardar (com destaque para uma cópia fora do
computador) · definir quando (padrão sugerido, não campo em branco) · ativar.

O último passo mostra o resumo em português corrente — *"Todo dia às 20h,
D:\\Empresa vai para E:\\Backups; guardamos 7 dias, 4 semanas e 12 meses;
avisamos por e-mail se algo falhar"* — e um botão **Ativar proteção**.

Depois disso o cliente não precisa abrir o navegador: o agente executa em
segundo plano, e o Live vira painel de acompanhamento.

## 6. Política de backup

A entidade central não é a execução, é a **política**:

```
Política
├── identidade      nome · organização · dispositivo · ativa/pausada
├── escopo          origens · exclusões · seguir links (não, por padrão)
├── destinos        [local, externo, rede, S3] com ordem e obrigatoriedade
├── quando          agendamento · janela permitida · gatilhos
├── retenção        diários · semanais · mensais
├── proteção        VSS · criptografia · assinatura
├── verificação     nível exigido (seção 10)
├── resiliência     tentativas · intervalo · retomada
└── avisos          canais · quando notificar
```

Duas decisões de modelagem:

- **A política é versionada.** Cada execução guarda o retrato da política que a
  gerou. Sem isso, mudar a retenção reescreve o passado.
- **A política pertence à organização; a execução pertence à política.** O
  isolamento multiempresa nasce do modelo, não de um filtro esquecível.

## 7. Gatilhos

| Gatilho | Classificação |
| --- | --- |
| Diário, semanal, mensal | MVP |
| Executar agora | MVP |
| Nova tentativa após falha transitória | MVP |
| Antes de outra automação modificar arquivos | MVP |
| Retomada após queda de internet (retomar o envio) | MVP |
| Ao conectar disco externo autorizado | evolução |
| Ao detectar alterações relevantes | evolução |
| Após outra automação gerar artefatos | evolução |

Proteger *antes* de destruir importa mais que arquivar depois — daí a ordem.

## 8. Destinos — estado real por camada

Esta tabela existe porque "funciona" significa coisas diferentes em cada camada,
e confundi-las produziria promessa falsa ao cliente.

| Destino | Núcleo/CLI | Live por upload | Pelo agente | Homologado pela interface |
| --- | --- | --- | --- | --- |
| Pasta local | funciona | sessão temporária | previsto | **não** |
| Outro volume do mesmo computador | funciona | não aplicável | previsto | **não** |
| Disco externo | funciona | não aplicável | previsto | **não** |
| Unidade de rede (UNC) | funciona | não aplicável | previsto | **não** |
| Pasta sincronizada por aplicativo de terceiros | funciona como pasta local | não aplicável | previsto | **não** |
| S3-compatível | não existe | não aplicável | 02.F | **não** |

**Nenhum destino está disponível para o cliente pelo Live hoje.** Outro volume,
disco externo e caminho de rede foram verificados por linha de comando em
20/08/2026 — isso comprova o núcleo, e nada mais. Só aparecem na interface
depois do agente (G.3–G.6) e da sua homologação.

### 8.1 Pasta sincronizada não é conector de nuvem

Uma pasta do OneDrive ou do Google Drive pode ser usada como **destino local**,
desde que o aplicativo do serviço esteja instalado e sincronizando. Deve ser
apresentada exatamente assim:

> Pasta local sincronizada por aplicativo de terceiros

Isso **não** equivale a: conector nativo · autenticação pelo AutoTarefas ·
confirmação de que o arquivo chegou ao servidor remoto · verificação da cópia na
nuvem · controle de versão pelo AutoTarefas · proteção contra uma exclusão que o
próprio sincronizador propague. Quem apaga na pasta apaga na nuvem.

### 8.2 Regra 3-2-1

Quando existir apenas uma cópia, e ainda por cima no mesmo volume da origem, a
interface diz isso com todas as letras e recomenda um segundo destino. Aviso,
nunca bloqueio — travar quebraria o backup agendado.

Upload para nuvem só com consentimento e configuração explícitos.

## 9. Estratégia incremental

Backup completo diário é inviável em produção: uma pasta de 20 GB com sete
cópias consome 140 GB e horas de envio. Mas incremental tem armadilha conhecida:
**a corrente** — se restaurar exige o completo mais todos os incrementais na
ordem, um elo perdido inutiliza o conjunto, e quem restaura está sob pressão.

Desenho aprovado, que resolve os dois lados:

- **catálogo local** por política (caminho, tamanho, data, hash, pacote onde o
  arquivo vive);
- tamanho e data iguais → arquivo considerado inalterado; mudaram → calcula-se
  o hash, e **hash igual não entra** (protege contra data alterada sem conteúdo
  alterado, que é comum e incharia o pacote à toa);
- o pacote leva só o que mudou; **o manifesto leva o estado completo** daquele
  instante;
- **base completa periódica** limita a corrente;
- **invariante inegociável:** a retenção nunca apaga um pacote referenciado por
  um manifesto ainda mantido.

**MVP:** completo + retenção. **Evolução imediata:** incremental. O manifesto do
MVP já nasce com os campos que o incremental exigirá, para não haver migração de
pacotes antigos.

Enquanto o incremental não existir, a interface informa que políticas com
arquivos muito grandes consomem mais tempo e espaço — e o produto **não** é
apresentado como adequado a backups recorrentes de grandes coleções de vídeo.

## 10. Arquivos grandes e mídia

Três problemas distintos: comprimir o que já está comprimido (vídeo, foto, PDF)
gasta processador sem reduzir tamanho — esses entram **sem compressão**; o limite
de 4 GB do ZIP clássico exige ZIP64, com teste explícito; e recopiar arquivos
grandes toda noite só é resolvido pelo incremental.

Dividir o pacote em partes fica como evolução: multiplica a complexidade da
restauração, que é justamente o momento em que nada pode dar errado.

## 11. Verificação

| Nível | O que é | Classificação |
| --- | --- | --- |
| 1 | manifesto + hash por arquivo | MVP (existe) |
| 2 | conferir o pacote depois de gravar | MVP (existe como comando) |
| 3 | conferir no destino depois do envio | MVP local/rede · com 02.F para S3 |
| 4 | **restaurar uma amostra e comparar com o manifesto** | MVP |
| 5 | teste completo periódico de restauração | evolução |

### 11.1 Restauração de amostra — regras

Extrair alguns arquivos para uma área temporária e comparar o hash com o
**manifesto** — nunca com a origem atual, que pode ter mudado legitimamente
desde o backup. A amostra escolhe arquivos de tipos e tamanhos diferentes,
registra quais foram testados, com data, resultado e nível, e apaga a área
temporária com segurança.

O texto exibido é literal quanto ao que foi provado:

```
Restauração de amostra aprovada:
5 de 5 arquivos selecionados foram extraídos
e coincidiram com o manifesto.
```

E **nunca**:

```
Todos os arquivos foram restaurados com sucesso.
```

Amostra aprovada é evidência de que o pacote devolve arquivo íntegro. Não é
prova de que o pacote inteiro restaura — só o nível 5 seria.

## 12. Falhas

| Situação | Classificação | Tratamento |
| --- | --- | --- |
| Rede caiu · nuvem indisponível · arquivo momentaneamente bloqueado | transitória | nova tentativa com intervalo crescente |
| Disco externo desconectado | aguardando | espera reconexão; avisa se persistir |
| Espaço insuficiente | permanente | não inicia, ou interrompe sem deixar pacote parcial |
| Credencial expirada | ação humana | notifica com o que fazer |
| Arquivo não lido | ressalva | registra qual e por quê; com VSS, tenta pelo instantâneo |

Nenhuma falha é mascarada. Execução com ressalva nunca aparece como sucesso
limpo — regra já implementada em 02.A.

## 13. Notificações — estado real

Correção de uma afirmação anterior imprecisa. O que existe hoje:

| Canal | Núcleo/CLI | No Live | Como canal de aviso do backup |
| --- | --- | --- | --- |
| E-mail | **integração real** (SMTP, STARTTLS, autenticação) | **indisponível** — não está em `ACTIVE_AUTOMATIONS` | **não existe** |
| Telegram | **integração real** (HTTP para `api.telegram.org`) | **apontado para o servidor de simulação local**, e o Live roda com bloqueio de saída de rede | **não existe** |

Ou seja: o **código de envio** é real e testado no núcleo, mas **não há canal de
notificação entregue**: falta interface, guarda de credenciais, configuração por
política e disparo automático. Reaproveitaremos as tarefas existentes em 02.E —
o que não é o mesmo que dizer que a notificação já está pronta.

## 14. Integração com as outras automações

O backup é a rede de segurança das demais automações, por um mecanismo
deliberadamente pequeno — dois eventos, sem framework:

```
before_destructive_action     antes de modificar, mover, renomear ou excluir
artifacts_created             depois que uma automação gera artefatos
```

`before_task` e `after_task` ficam fora do MVP: gerariam evento em toda execução
do sistema sem consumidor, e evento sem consumidor é acoplamento com custo e sem
benefício.

O backup se inscreve nos eventos; nenhuma automação conhece o backup.

### 14.1 Falha fechada

Se uma automação exige proteção antes de alterar arquivos e o backup **não**
atinge o nível exigido, a ação destrutiva **é bloqueada**. A mensagem diz o que
seria alterado, qual proteção foi tentada, por que falhou, o que fazer, e que a
operação original **não** foi executada.

Opção administrativa de prosseguir sem backup **não** entra no MVP. Se um dia
entrar, será com confirmação forte e auditoria.

## 15. Painel de saúde

No topo, um número em letras grandes: **há quanto tempo existe proteção
válida** — validada, não apenas executada. Quatro estados:

```
Protegido
Protegido com ressalvas
Atenção necessária
Sem proteção recente
```

Abaixo: último backup, última verificação, última cópia fora do computador,
próximo horário, volume e quantidade protegidos, políticas ativas, dispositivos
conectados e o que exige ação. A lista de execuções existe, em segundo plano:
ela responde "o que aconteceu", e a pergunta do dono é "estou protegido?".

## 16. Limites — o que este card não promete

- proteção absoluta contra ransomware;
- perda zero de dados;
- arquivos ou volume ilimitados;
- compatibilidade com qualquer nuvem — apenas o protocolo implementado;
- compatibilidade com qualquer sistema operacional — Windows é o alvo;
- restauração garantida sem teste — só o nível 5 sustentaria isso;
- autenticidade sem assinatura: o hash dentro do pacote detecta corrupção e
  alteração acidental, **não** adulteração intencional (02.B).

Quando houver destino com versionamento ou imutabilidade, a proteção oferecida
será descrita com precisão, sem generalizar.

## 17. MVP × evolução

| | MVP | Evolução |
| --- | --- | --- |
| Execução | agendada, manual, retry, antes de ação destrutiva | ao conectar disco, ao detectar alteração, após artefatos |
| Cópia | pacote completo + retenção | incremental com catálogo e base periódica |
| Destinos | local, externo, rede, S3 | outros conectores, pacote em partes |
| Verificação | níveis 1 a 4 | nível 5 periódico |
| Proteção | VSS, assinatura HMAC | AES, mediante decisão |
| Avisos | exceção + resumo semanal opcional | escalonamento, painel de alertas |

## 18. Riscos técnicos

| Risco | Gravidade | Mitigação |
| --- | --- | --- |
| Retenção apagar pacote ainda referenciado | crítico | invariante da seção 9, com teste dedicado |
| Cliente achar que está protegido e não estar | crítico | seções 11 e 15 existem para isso |
| Máquina hibernar no meio do backup | alto | marcar incompleto e refazer, nunca concluído |
| Catálogo local corromper | alto | tratar como cache: inválido → refaz completo |
| Antivírus bloquear o agente | alto | validar cedo; assinar o executável quando viável |
| Backup consumir a máquina no expediente | médio | janela permitida na política |
| Relógio alterado quebrar o carimbo | médio | ordenar por identificador sequencial |
| Instantâneo VSS não removido | médio | remoção garantida mesmo em falha |

## 19. Critérios de aceite do card

O card só é "pronto" quando, **pela interface**: o cliente cria e ativa uma
política sem digitar comando; o backup roda sozinho no horário com o navegador
fechado; a execução aparece com o estado correto e as ressalvas nomeadas; existe
evidência registrada de restauração de amostra; o envio ao destino externo é
confirmado; a retenção mantém exatamente o previsto sem tocar em arquivo alheio;
uma falha transitória se recupera sozinha; o cliente é avisado só quando precisa;
e ele consegue restaurar pela tela. Com testes automatizados em cada camada e
homologação manual do proprietário.

## 20. Criptografia em nuvem — decisão pendente

Antes de qualquer implementação de destino S3, será apresentada decisão
específica sobre: criptografia em trânsito; criptografia no armazenamento;
criptografia do lado do cliente; geração e custódia da chave; recuperação;
rotação; perda da chave; e separação entre a chave HMAC (autenticidade) e a
chave AES (confidencialidade).

Enquanto essa decisão estiver pendente, o destino em nuvem **não** será
apresentado como proteção empresarial concluída.

---

## 21. Subetapas do Card 02 — mapa completo

As letras vinham sendo atribuídas conforme surgiam, e isso abriu uma lacuna: a
letra **H** nunca foi usada como subetapa (só como rótulo de decisões numa
conversa), e as capacidades novas haviam sido propostas como I, J e K — o que
deixaria um buraco no meio. Corrigido aqui: as três passam a ocupar **H, I e J**,
em sequência, e **K não existe**.

| Subetapa | Finalidade | Depende de | Estado | Relação com G |
| --- | --- | --- | --- | --- |
| **02.A** | Correções críticas e segurança de caminhos: junções, ciclos, ressalvas visíveis, aviso de mesmo volume, documentação honesta | — | implementada (`90193f5`, `5870838`) | parte já no Live; aviso de volume e opção de links dependem de G.6 |
| **02.B** | **Assinatura HMAC com chave externa** — autenticidade | 02.A · G.2 (guarda da chave) | implementada (`2fdad84`) | tela em G.6 |
| **02.C** | Criptografia AES e gestão segura da senha | 02.B · G.2 | implementada (`c519b4b`) | tela em G.6 |
| **02.D** | VSS opcional para arquivos abertos | G.3–G.5 (agente) | implementada (`b69f957`) · teste com elevação pendente | exclusiva do agente; nunca no modo upload |
| **02.E** | Agendamento, gatilhos, retry, notificações e retenção diária/semanal/mensal | 02.G.6 (política) | implementada (`05e5e3b`) · envio de e-mail exige SMTP no cofre | telas em G.6 e G.7.4 |
| **02.F** | Destinos externos e conector S3 | 02.C (decisão de chave) · G.5 | implementada (`84f41ab`) · nuvem real pendente | tela em G.7.4 |
| **02.G** | **Agente local e interface operacional** — fundação da plataforma | — | G.0 a G.9 implementadas — matriz em [02-roadmap-execucao.md](02-roadmap-execucao.md) | é a própria trilha G |
| **02.H** | **Restauração guiada pela interface** (era 02.I) | 02.B (mostrar autenticidade) | implementada (`4972f41`) | tela na G.7.3 |
| **02.I** | **Backup incremental com catálogo** (era 02.J) | 02.E (retenção) · G.6 | implementada (`b38bbdf`) | sem tela própria; muda o motor |
| **02.J** | **Hooks e proteção antes de ação destrutiva**, com falha fechada (era 02.K) | 02.G.6 | implementada (`6b176cb`) | aviso na tela da restauração bloqueada |
| **02.K** | — | — | **não existe** | — |

### Critérios de aceite por subetapa

| Subetapa | Aceite |
| --- | --- |
| 02.A | Nenhum arquivo de fora da origem entra sem escolha explícita; ciclo não repete; Live nunca chama ressalva de erro; não lidos visíveis; aviso de mesmo volume presente; documentação sem promessa de autenticidade |
| 02.B | Adulteração com manifesto recalculado passa a ser **detectada**; perda da chave não impede restaurar; pacote sem assinatura mostra "autenticidade não comprovada" |
| 02.C | Pacote cifrado abre no 7-Zip com a senha; manifesto protegido; senha nunca em log, manifesto, tela ou trilha; confirmação dupla no primeiro uso |
| 02.D | Com elevação, arquivo aberto no Excel **entra** no backup; sem elevação, recusa clara e nenhum instantâneo órfão |
| 02.E | Política roda no horário com o navegador fechado; retenção mantém o previsto sem tocar em arquivo alheio; falha transitória se recupera; aviso só em ressalva ou falha |
| 02.F | Backup chega ao destino externo com verificação após o envio; falha de rede não deixa objeto com aparência de completo |
| 02.G | Ver critérios por subetapa G.0–G.8 no planejamento da plataforma |
| 02.H | Restauração reproduz os arquivos byte a byte; recusa caminho malicioso no pacote; não sobrescreve sem confirmação; recusa pacote corrompido |
| 02.I | Arquivo idêntico não é reenviado; data alterada sem conteúdo alterado não infla o pacote; retenção nunca remove pacote referenciado |
| 02.J | Backup que não atinge o nível exigido **bloqueia** a ação destrutiva, explicando o que não foi feito |


---

## 22. Trilha G — estado por subetapa

A matriz completa, com dependências e ordem de execução, está em
**[02-roadmap-execucao.md](02-roadmap-execucao.md)**. Resumo:

| Subetapa | Estado | Commit |
| --- | --- | --- |
| **G.0** — `live_demo` vira `apps/web` + `apps/api` | implementada | `9c77a3b` |
| **G.1** + **G.1.1** — nome do card, capacidades, linguagem honesta | implementadas | `b671270`, `19d1064` |
| **G.2.1–G.2.3** — dados multiempresa, identidade OIDC, cofre | implementadas | `b3ec3e5`, `cc91cb9`, `c389e7b` |
| **G.3.1–G.3.2** — esqueleto do Agente, pareamento | implementadas | `9b267f5`, `1fb4098` |
| **G.4.1–G.4.2** — canal de saída, protocolo de comandos | implementadas | `49ea17a`, `4bc9586` |
| **G.5.1–G.5.3** — raízes autorizadas, streaming, destinos reais | implementadas | `14667ba`, `d9da5c8`, `e389493` |
| **G.6** — telas de dispositivos e pastas | implementada | `3967c3a` |
| **G.7.1–G.7.4** — histórico do agendamento, pacote por nome, telas, política | implementadas | `131e9f2`, `fd699b6`, `5b1f2ce`, `9579119` |
| **G.8** — serviço, pacote e instalação guiada | implementada | `6483f37` |
| **G.9** — homologação dos 20 passos com navegador real | 20/20 | `ec97a5a` |

Nenhuma delas está **homologada**. O que existe é uma implementação preparada
para homologação, com os vinte passos passando de ponta a ponta — e com quatro
verificações que dependem de hardware, privilégio ou credencial do proprietário,
listadas no roteiro manual.

### 22.1 G.1.1 — o que mudou, mensagem por mensagem

| # | Onde | Antes | Depois |
| --- | --- | --- | --- |
| 1 | Terminal do Live | `C:\Users\<usuário>\AppData\Local\Temp\autotarefas-live\<token>\out\backup.zip` (às vezes partido em duas linhas) | `backup.zip` — e, se algo escapar, `[arquivo interno]` |
| 2 | Terminal do Live | `Para conferir depois: autotarefas verificar C:\...\backup.zip` | `Pacote gerado. Use a opção "Verificar este pacote" na área de artefatos.` |
| 3 | Terminal do Live | `Origem e destino no MESMO disco (...)` + `Prefira outro disco...` | `Destino externo: não aplicável ao upload avulso.` |
| 4 | Resultado da conferência | `Pacote íntegro: N arquivo(s) conferem com o manifesto` | `Pacote gerado e verificado antes do download.` + `N arquivo(s) conferem com o manifesto, lido de dentro do próprio pacote.` |
| 5 | Cabeçalho do terminal | `Saída em tempo real da execução, em espaço isolado` / `autotarefas@sandbox:~` | `Saída em tempo real da execução em espaço isolado` / `autotarefas@espaco-isolado:~` |
| 5 | Rodapé, capa, barra de status, `index.html` | "sandbox seguro", "Sandbox isolado", "Sandbox Seguro" | "espaço isolado", "Espaço isolado" |

### 22.2 Vazamento de caminho — por que aconteceu

O sanitizador do Live trabalha **linha a linha**, e relativizava o caminho
comparando com o caminho **exato** do workspace. O console do robô quebrava a
linha em 80 colunas no meio do caminho: nenhuma das duas metades era igual ao
caminho exato, e as duas passavam.

Três correções em camadas, da origem para a última rede:

1. **A CLI não imprime mais o caminho na tela.** Com `AUTOTAREFAS_UI=web` ela
   mostra só o nome do pacote. No terminal e no agente nada muda.
2. **O console não quebra mais a linha.** O Live executa a CLI com
   `COLUMNS=400`.
3. **O sanitizador virou duas redes.** Além de relativizar o caminho exato,
   agora apaga qualquer caminho absoluto, qualquer token de execução de 32
   hexadecimais, e o pedaço final do workspace quando a linha começa com ele —
   o caso do caminho partido. Vale para **todos os cards**, não só o backup.

O hash SHA-256 tem 64 hexadecimais e continua visível: é informação que a
pessoa precisa ver, e apagá-la junto com o token teria removido a prova de
integridade.

### 22.3 Escopo da verificação

A conferência lê o pacote que está **no servidor**, na pasta desta execução —
o mesmo arquivo que o botão de download entrega. Não confere a cópia já
baixada, que o navegador guarda fora do alcance da página. Por isso o texto é
`Pacote gerado e verificado antes do download.`, e a tela avisa o escopo antes
de a pessoa clicar.

### 22.4 O que a G.1.1 **não** resolve

O fluxo continua sendo: selecionar arquivos no navegador, limite de 10 MB por
arquivo, executar, baixar o ZIP pelo navegador. Pasta local, agendamento,
destino externo e execução sem envio manual dependem do **agente** (G.3–G.5) e
da **tela de política** (G.6). A G.1.1 corrigiu o que a interface **dizia**,
não o que ela **faz**.
