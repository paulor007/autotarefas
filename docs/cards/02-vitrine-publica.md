# Card 02 — a vitrine pública

O AutoTarefas faz parte de um **portfólio**. Quem chega não é desenvolvedor do
projeto: é alguém avaliando o trabalho — um recrutador, uma empresa, um curioso.
Essa pessoa clica em "Acessar projeto" e precisa estar dentro, diante de um
sistema que já está de pé.

Ela **não** abre terminal, não instala `.exe`, não pareia máquina, não copia
token, não configura variável de ambiente e não precisa saber que existem SQLite,
OIDC ou porta 7860. Também não deveria precisar executar um backup manualmente
para descobrir se o sistema funciona.

Nada disso é conseguido com simulação. O que existe do outro lado é o
AutoTarefas de verdade — mesmo banco, mesmo agendador, mesmo Agente — num
ambiente que **pertence ao projeto** e roda sozinho.

## 1. As duas separações que sustentam o resto

**Dev/homologação × produto publicado.** Terminal, `pytest`, `tools/ensaio.py`,
bancos isolados, log técnico e token servem para desenvolver e testar. Nada
disso aparece na experiência final. `tools/vitrine.py` fica do lado de cá: é
quem **monta** o ambiente, e não parte do que o visitante usa.

**Sessão pública × sessão de cliente.** A trava é da sessão, e não do papel. Um
`dono` de empresa de verdade continua vendo a tela que sempre viu; a sessão
pública é somente leitura, e o servidor recusa antes de qualquer rota.

## 2. Como a porta se abre

Duas variáveis, e as duas juntas de propósito:

    DEMONSTRACAO_PUBLICA=1
    DEMONSTRACAO_ORG="AutoTarefas Demonstracao"

Sem o nome da organização a porta fica fechada. Cair na "primeira organização
que aparecer" seria a receita para publicar o dado de um cliente num servidor
que hospeda mais de uma.

Três regras mantêm isso honesto, e estão em `identidade/demonstracao.py`:

1. **Só quando alguém liga.** Não há valor padrão verdadeiro; uma instalação de
   cliente nunca ganha esta porta por descuido de quem implanta.
2. **Só numa organização, escolhida a dedo.**
3. **Sempre somente leitura.** A marca viaja na sessão e é conferida por
   middleware, antes de qualquer rota — inclusive as que ainda não existem. Um
   teste varre o esquema OpenAPI e exige 403 em toda rota de escrita, para que
   a rota criada amanhã nasça fechada.

O papel no banco é `leitor`, **além** da marca. São duas travas independentes:
afrouxar uma não abre a outra.

## 3. O ambiente controlado

`tools/vitrine.py` monta tudo pelo caminho de um cliente: código temporário de
pareamento, autorização de pasta na própria máquina, políticas pelo mesmo
schema. Um atalho que gravasse o dispositivo direto no banco provaria menos e
esconderia a metade do fluxo que costuma quebrar.

    python tools/vitrine.py preparar          # idempotente
    python tools/vitrine.py agente            # sobe o Agente da vitrine
    python tools/vitrine.py primeira-execucao # semeia o histórico

`VITRINE_CASA` decide onde o ambiente mora. Fora do repositório em produção; numa
pasta temporária na homologação de ponta a ponta.

**Quatro políticas diárias** (03:00, 09:00, 15:00, 21:00). Não é enfeite: com
uma só, um visitante estaria em média doze horas depois da última execução, e o
painel mostraria evidência velha.

**Arquivos de exemplo sintéticos, e obviamente sintéticos.** Cada um se declara
no próprio conteúdo, inclusive os CSV — um arquivo restaurado sai do pacote
sozinho, longe daqui, e números plausíveis sem marca seriam confundidos com dado
de alguém.

## 4. O destino, e a verdade incômoda

Num servidor único o destino fica no mesmo disco da origem. O produto detecta
isso e mostra **Proteção parcial**, com o motivo — e está certo: cópia ao lado
do original não sobrevive ao disco morrer.

Para o painel dizer **Protegido**, o destino precisa ser mesmo externo. Não há
atalho: declarar "disco externo" para uma pasta local seria exatamente a mentira
que o produto inteiro foi feito para não contar.

O caminho pronto é o balde S3-compatível:

    VITRINE_DESTINO_TIPO=nuvem
    VITRINE_S3_BALDE=...
    VITRINE_S3_CHAVE=...
    VITRINE_S3_SEGREDO=...
    VITRINE_S3_ENDPOINT=...   # vazio = Amazon S3
    VITRINE_S3_REGIAO=...
    VITRINE_S3_PREFIXO=...

Elas ficam no ambiente de quem publica, nunca no repositório. Do ambiente vão
para o cofre da organização, cifradas, e saem só para viajar pelo canal
autenticado até a máquina, no momento do envio. Não passam pelo navegador e não
são gravadas no disco do Agente.

Sem essas variáveis o provisionamento **recusa** o tipo `nuvem`, dizendo qual
falta: sem balde, o pacote seria feito e não teria para onde ir — e a política
que o painel conta como proteção nunca entregaria nada.

## 5. O que o visitante encontra

    entra pelo portfólio  →  /app, sem login e sem conta
    → faixa dizendo que é demonstração, e que nada muda
    → máquina real conectada (presença, não cadastro)
    → quatro políticas ativas
    → último backup real, com data, tamanho e resultado
    → próxima execução, no relógio da máquina
    → trilha de auditoria íntegra
    → histórico de execuções
    → execução em andamento, quando houver
    → detalhe da execução, com SHA-256 e conferência no destino

O assistente de configuração abre **desarmado**: todos os campos vivos, a frase
do passo 6 calculada pelo mesmo código, e nada para ativar no fim. Escondê-lo
escondia justamente o que a pessoa veio ver — que dá para mandar a cópia para
disco externo, pasta de rede ou nuvem.

"Executar agora" e "Remover" não aparecem na sessão pública. Botão que só sabe
responder 403 é botão sem função, e o 403 chegaria como erro vermelho — a forma
mais cara de explicar uma regra de produto.

## 6. O que esta etapa corrigiu no produto

Coisas encontradas ao montar o ambiente público, e que valiam para qualquer
cliente:

| Achado | Efeito no cliente |
| --- | --- |
| Retenção sem escopo | "diário/7 dias" apagava o pacote do "mensal/12 meses" na mesma máquina. Configurou doze meses, recebeu sete dias, sem erro e sem aviso |
| Catálogo incremental compartilhado | duas políticas incrementais dividiam a corrente; a restauração encontraria uma corrente que nunca esteve completa |
| Retenção só na pasta local | disco externo e pasta de rede acumulavam para sempre, até encher — e a partir daí todo backup falhava |
| `destino: nuvem` no agendamento | o pacote ficava no computador e o painel dizia **Protegido** |
| Execução órfã | "Executar agora" numa política não carimbava a política, e o veredito dizia "nunca concluiu" logo após concluir |
| Datas sem fuso | uma execução das 14:30 aparecia como 17:30 — três horas no futuro |
| Caminho local na ficha da entrega | a estrutura de pastas da empresa subia para o servidor e era exibida na tela |
| `politica_id`/`usuario_id` vazios em chave estrangeira | a inserção inteira era recusada, com erro que não falava do campo |

## 7. Escopo da retenção — como o vínculo é feito

O dono do artefato precisa sobreviver a tudo o que acontece com um arquivo: ser
copiado para outro disco, ser levado para outra máquina, ser encontrado meses
depois por alguém que não sabe o que é. Por isso o vínculo é a **pasta**, e não
um registro em banco — o banco fica no servidor, e o pacote precisa dizer de
quem é sem servidor nenhum por perto.

    backups/
        backup_2026-08-30_1015.zip       <- avulso: não é de política alguma
        politica-a1b2.../
            politica.json                <- {"id": ..., "nome": "Diário 03:00"}
            backup_2026-08-01_0300.zip
        politica-c3d4.../
            politica.json
            backup_2026-08-01_2100.zip

A mesma disposição vale no destino externo. O identificador vira nome de pasta e
chega do servidor, então é conferido antes: sem isso, quem controla o servidor
escolheria em que pasta do disco do cliente o Agente escreve — e a retenção,
logo depois, apagaria arquivos lá dentro.

**Pacotes anteriores a esta correção ficam na raiz.** Não há como atribuí-los
agora — era exatamente essa a informação que faltava — e sumir com eles da lista
seria fazer sumir backup que existe. Sem dono, nenhuma retenção de política os
alcança.

## 8. Nuvem no agendamento — entrega diferida

Duas decisões pareciam, juntas, impedir backup agendado com destino na nuvem:

- **o agendamento roda offline** — se dependesse do canal, o backup pararia toda
  vez que a internet caísse, que é a madrugada em que ninguém está olhando;
- **o Agente não grava chave de nuvem em disco** — a credencial mora no cofre da
  organização, no servidor.

O que destrava é notar que **o que precisa de rede é o envio, e não o backup**. O
agendamento faz o pacote sozinho; o envio acontece quando há canal, com a
credencial chegando na hora, sendo usada, e sumindo com a resposta.

Isso cria uma janela real — pacote feito, ainda não subiu — e ela aparece como
tal: o painel diz "aguardando envio", e não "Protegido". `protege_de_verdade` é
uma afirmação sobre a **configuração**; para disco e rede a entrega acontece
dentro da execução, para a nuvem não.

Falha de envio não vira sucesso: o erro fica no artefato, o pacote segue
pendente, e a próxima conexão tenta de novo. A chave do objeto vem do nome do
pacote, então reenviar sobrescreve em vez de multiplicar a conta do cliente.

## 9. O que continua pendente

| Pendência | Por quê |
| --- | --- |
| **Balde S3 de verdade** | precisa de uma conta e de credenciais que só o dono do projeto pode criar. O caminho está pronto e testado contra servidor S3-compatível local; enquanto não houver balde, o painel fica em **Proteção parcial**, e está certo |
| Disco externo físico | nunca testado com hardware removível real |
| Pasta de rede (UNC) | precisa de uma segunda máquina |
| VSS com elevação | 2 testes pulam por falta de privilégio |
| SMTP real | a notificação existe na tela e no histórico; nunca foi enviada de verdade |
| Edição de política | hoje é remover e criar de novo |
| Criptografia em nuvem | decisão da seção 20 do card, ainda pendente |

## 10. Homologação

`tests/e2e/test_jornada_do_visitante_e2e.py` — quinze passos com navegador de
verdade, do clique no portfólio até a evidência, montando o ambiente com a
ferramenta de publicação real. Prova o que a homologação do Card 02 não prova:
não que o produto funciona para quem o **opera**, mas que **quem só chega e olha
encontra tudo pronto** — e não consegue alterar nada, nem pela tela nem por
baixo dela.
