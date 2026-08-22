# 09 — Critérios de Aceite e Definition of Done

Um requisito só recebe **CONCLUÍDO** quando cumpre o DoD geral **e** o DoD do seu
tipo, com evidências registradas na matriz (05). "Funciona na minha máquina" não
é evidência; comando + resultado + caminho é.

**Regra reafirmada em 10/08/2026:** aprovação documental **não** conclui
requisito — e **conclusão de auditoria também não**: a Fase A1 foi encerrada como
atividade de auditoria sem que nenhum requisito mudasse de status; seus achados
viraram os gates obrigatórios A1.1–A1.4 (`06`). A DP-01 fixou o recorte obrigatório da V1 em 41 requisitos e promoveu
RF-INT-005 a obrigatório; RF-INT-005 permanece **NÃO INICIADO** até ter código,
testes, critérios de aceite cumpridos e evidência na matriz.

## 1. DoD geral (todo requisito)

1. Ficha do requisito em `03` atualizada (status, evidências, lacunas zeradas ou
   movidas para requisito próprio).
2. Critérios de aceite da ficha demonstrados um a um.
3. Implementação integrada (CLI e/ou Live conforme a ficha) — nada de módulo
   solto sem chamada.
4. Tratamento de falhas com mensagens em português orientando a correção; erro
   individual nunca derruba o lote onde a ficha exige tolerância.
5. Saída útil: artefato/relato que encerra a tarefa de alguém (não só log).
6. Testes automatizados novos cobrindo o comportamento e os erros; suítes
   inteiras verdes (núcleo com gate de cobertura ≥ 85%, mypy `src/ tests/`
   limpo, pre-commit passando).
7. Nenhum segredo em código, log, audit, relatório ou fixture.
8. Audit registrando a execução quando o requisito é uma task.
9. Matriz (05) e checklist (00 §5) atualizados no mesmo commit.
10. Commit local com a mensagem sugerida no roadmap (06); sem push/tag fora do
    ritual de release.
11. **Status sempre da legenda oficial (00 §2)** — não existe "CONCLUÍDO com
    ressalva": se a ficha prevê evidência e2e e ela não foi executada, o status é
    PARCIAL (ou NÃO COMPROVADO, quando só há afirmação) até a homologação.
12. **Nenhuma decisão incerta silenciosa** — no fluxo de planilhas, toda
    ambiguidade ou conflito fora de regra declarada gera item de revisão
    identificado nos artefatos, nunca uma escolha automática.

## 2. DoD por tipo

**Task do núcleo (BaseTask):** herda BaseTask e devolve TaskResult; `--dry-run`
simula fielmente; suporte a `--yes` quando destrutiva; testes de unidade +
fixtures com casos plantados (válidos, inválidos, limítrofes); documentação de
uso no `--help`.

**Comando/Subcomando CLI:** `--help` completo e em português; exit codes
corretos (0 sucesso, ≠0 falha, distinção para parcial quando aplicável); testes
em `tests/cli/` cobrindo parsing, fluxo feliz e erros de uso; nenhuma traceback
crua ao usuário.

**Funcionalidade do Live backend:** allowlist respeitada (argv 100% do servidor;
recusas 404/501/429/413 corretas); limites de `config.py` aplicados; artefatos
apenas em `out/` com download de nome simples; testes em
`apps/api/tests` cobrindo sucesso, recusas e limites; egress lockdown
inalterado.

**Frontend do Live:** typecheck e build verdes; estado de erro/offline tratado;
teste de componente para todo fluxo novo (mínimo: renderiza payload real sem
desmontar); sem dado mockado embutido — tudo vem da API; `npm audit` continua em
0.

**Ativação de card (LIVE-006a):** ramo em `build_argv` + inclusão na régua +
exemplo de 1 clique quando fizer sentido + teste de engine + verificação manual
dos downloads registrada.

**Retirada de promessa pública (LIVE-006b / A4, DP-02):** o card deixa de aparecer
como executável, a demonstração em vídeo/GIF fica publicada com o comando real
equivalente, nenhum código ou teste é removido e nenhum card visível responde 501.

**Mapeamento de importação (RF-INT-005 — obrigatório V1):** as 12 exigências funcionais consolidadas em 11 critérios de aceite da ficha
(03) demonstradas uma a uma, com destaque para: mapa por CLI e por
arquivo produzindo o mesmo resultado; campo obrigatório do destino sem origem →
falha de configuração com zero envio; mapa repetido/incompatível → erro nomeando o
conflito; prévia do payload antes do primeiro envio; dry-run sem nenhuma escrita
externa; arquivo de entrada byte-idêntico ao final; mapa efetivo registrado no
relatório e no audit; relatório separando aceitos, rejeitados e falhos; testes
cobrindo três estruturas diferentes (contatos, produtos, vendas); nenhuma
credencial na configuração; nenhuma decisão incerta aplicada em silêncio.

**Documentação (docs/requisitos):** alteração reflete a realidade auditável;
nenhum número sem fonte; decisões viram DP-xx antes de virarem texto normativo.

**RPA com navegador real (RF-WEB-003) — decisão aprovada em 10/08/2026:** o
**teste automatizado com navegador real é obrigatório**; a **homologação manual é
apenas complementar e não o substitui**. WEB-003 só é promovido a CONCLUÍDO com
esse teste verde. Se o teste ainda não existir, ele precisa ser criado antes da
conclusão do requisito.
Referência de execução para a C1: `playwright install chromium` seguido de
`python -m pytest tests/e2e`.

**Homologação de release (Fase C1):** depende de A1 (concluída), **A1.1–A1.4**,
A2, A4 e **B1–B7** concluídos — incluindo **RF-INT-005**, que bloqueia a
homologação e o release.
Roteiro de 01 §20 executado e evidenciado; `playwright install chromium && python -m pytest tests/e2e` verde
(promove **WEB-002**; **WEB-003** exige o teste automatizado com navegador real —
obrigatório, sem substituição por homologação manual, conforme `05` ressalva 1);
jornada completa do fluxo de
planilhas — analisar, comparar, conciliar, corrigir, planilha tratada e
**importação com mapeamento configurável** — cronometrada ≤ 3 min.

## 3. Anti-critérios (nunca aceitos como "pronto")

Percentual arbitrário; "só falta teste"; teste desligado/skipado para passar;
lacuna descoberta e não registrada; funcionalidade visível no Live sem executar
(501 ou erro); README prometendo o que a matriz não confirma; **requisito marcado
como concluído por decisão documental, sem código, testes e evidências**;
requisito recomendado entrando à frente de um obrigatório.
