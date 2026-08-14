import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ContractError } from "../lib/spreadsheets";
import ErrorBoundary from "./ErrorBoundary";
import SpreadsheetJourney from "./SpreadsheetJourney";

/**
 * Comportamento da jornada, com a camada HTTP mockada.
 *
 * O teste central e `nao desmonta a aplicacao`: ele reproduz o payload real que
 * derrubou a tela (avisos como OBJETOS) e prova que agora o diagnostico
 * aparece, com a estrutura da pagina de pe.
 */

const AVISO_OBJETO = {
  code: "linhas_duplicadas",
  message: "16 linha(s) completamente identica(s) a outra",
  column: null,
  row: null,
};

function respostaAnalise(over: Record<string, unknown> = {}) {
  return {
    token: "tok-1",
    status: "analysis_ready",
    needs_choice: false,
    preview: "Código Venda | Data\n65200 | 2019-12-01",
    ambiguities: [],
    selected_sheet: "Plan1",
    header_row: 1,
    schema_suggestion_available: true,
    analysis: {
      metadata: { source_file: "Vendas - Dez (2).xlsx", extension: ".xlsx" },
      leitura: {
        selected_sheet: "Plan1",
        header_row: 1,
        header_confidence: 1,
        confidence: 0.95,
        available_sheets: [{ name: "Plan1", score: 0.94, rows: 7089, cols: 7 }],
      },
      estrutura: { row_count: 7089, column_count: 7 },
      columns: [
        { name: "Código Venda", inferred_type: "inteiro", empty_count: 0 },
        { name: "Valor Final", inferred_type: "moeda", empty_count: 0 },
      ],
      findings: [{ ...AVISO_OBJETO, severity: "aviso" }],
      reader_warnings: [AVISO_OBJETO],
    },
    ...over,
  };
}

function mockFetch(
  resposta: unknown,
  { status = 200 }: { status?: number } = {},
): ReturnType<typeof vi.fn> {
  const espia = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => resposta,
  } as Response);
  vi.stubGlobal("fetch", espia);
  return espia;
}

/**
 * Mock que responde conforme a rota — a jornada faz chamadas diferentes em
 * sequencia (analise, schema, validacao) e cada uma tem contrato proprio.
 */
function mockFetchPorRota(): ReturnType<typeof vi.fn> {
  const espia = vi.fn(async (url: unknown) => {
    const alvo = String(url);
    let corpo: unknown = respostaAnalise();
    if (alvo.includes("/schema")) {
      corpo = {
        token: "tok-1",
        status: "schema_ready",
        schema_origin: "suggested",
        summary: {
          columns: [
            {
              name: "Código Venda",
              type: "str",
              required: true,
              format: null,
              validator_br: null,
              unique: false,
            },
          ],
          detect_duplicate_rows: false,
          group_keys: [],
          group_checks: [],
          derived_checks: [],
        },
      };
    } else if (alvo.includes("/validate")) {
      corpo = {
        token: "tok-1",
        status: "validating",
        stream_url: "/api/stream/tok-1",
        result_url: "/api/result/tok-1",
      };
    }
    return {
      ok: true,
      status: 200,
      json: async () => corpo,
    } as Response;
  });
  vi.stubGlobal("fetch", espia);
  // A jornada abre um SSE ao validar; no jsdom nao existe EventSource.
  vi.stubGlobal(
    "EventSource",
    class {
      close(): void {}
      addEventListener(): void {}
      removeEventListener(): void {}
    },
  );
  return espia;
}

/** Leva a jornada ate a etapa de revisao (a ultima antes de executar). */
async function irAteRevisao(): Promise<ReturnType<typeof vi.fn>> {
  const espia = mockFetchPorRota();
  montar();
  await userEvent.click(
    screen.getByRole("button", { name: /Testar com exemplo/i }),
  );
  await waitFor(() => {
    expect(screen.getByText("Diagnóstico do arquivo")).toBeTruthy();
  });
  await userEvent.click(
    screen.getByRole("button", { name: /Escolher como validar/i }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: /Confirmar schema sugerido/i }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: /Revisar configuração/i }),
  );
  await waitFor(() => {
    expect(screen.getByText("Revise antes de executar")).toBeTruthy();
  });
  return espia;
}

/** Sobe a jornada dentro da barreira, como o app real faz. */
function montar() {
  return render(
    <div>
      <nav aria-label="principal">navegação</nav>
      <ErrorBoundary area="jornada de planilhas">
        <SpreadsheetJourney />
      </ErrorBoundary>
    </div>,
  );
}

async function enviarArquivo(nome = "Vendas - Dez (2).xlsx") {
  const arquivo = new File(["a,b\n1,2\n"], nome, {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  expect(input).not.toBeNull();
  await userEvent.upload(input as HTMLInputElement, arquivo);
}

describe("SpreadsheetJourney", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("mostra a etapa inicial com as duas origens", () => {
    montar();
    expect(screen.getByText("Escolha o arquivo")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Testar com exemplo/i }),
    ).toBeTruthy();
  });

  it("não desmonta a aplicação ao analisar o payload real (regressão)", async () => {
    mockFetch(respostaAnalise());
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );

    // O diagnóstico aparece...
    await waitFor(() => {
      expect(screen.getByText("Diagnóstico do arquivo")).toBeTruthy();
    });
    expect(screen.getByText("7089")).toBeTruthy();
    // ...o aviso que era objeto agora é texto legível...
    // A mesma mensagem aparece como ACHADO da análise e como AVISO do leitor —
    // são duas seções distintas, por isso `getAllByText`. O que importa é que
    // ambas rendam TEXTO: era exatamente aqui que o objeto derrubava o React.
    expect(
      screen.getAllByText(/16 linha\(s\) completamente identica/).length,
    ).toBeGreaterThanOrEqual(1);
    // ...e a estrutura da página continua de pé.
    expect(screen.getByLabelText("principal")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("oferece as correções seguras na revisão, desligadas por padrão", async () => {
    await irAteRevisao();

    const caixa = screen.getByRole("checkbox", {
      name: /Aplicar as correções seguras/i,
    }) as HTMLInputElement;
    expect(caixa.checked).toBe(false);
  });

  it("explica o que a confirmação faz com um XLSX antes de executar", async () => {
    await irAteRevisao();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Aplicar as correções seguras/i }),
    );

    expect(screen.getByText(/planilha tratada/i)).toBeTruthy();
  });

  it("não envia apply_cleaning quando a pessoa não confirma", async () => {
    const espia = await irAteRevisao();
    await userEvent.click(
      screen.getByRole("button", { name: /Executar validação/i }),
    );

    const chamada = espia.mock.calls.find((args) =>
      String(args[0]).includes("/validate"),
    );
    expect(chamada).toBeTruthy();
    const corpo = (chamada?.[1] as { body?: FormData })?.body;
    expect(corpo?.get("apply_cleaning")).toBeNull();
  });

  it("envia apply_cleaning quando a pessoa confirma as correções", async () => {
    const espia = await irAteRevisao();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Aplicar as correções seguras/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Executar validação/i }),
    );

    const chamada = espia.mock.calls.find((args) =>
      String(args[0]).includes("/validate"),
    );
    const corpo = (chamada?.[1] as { body?: FormData })?.body;
    expect(corpo?.get("apply_cleaning")).toBe("true");
  });

  it("usa o exemplo pelo backend real, sem resultado embutido", async () => {
    const espia = mockFetch(respostaAnalise());
    montar();
    await userEvent.click(
      screen.getByRole("button", { name: /Testar com exemplo/i }),
    );
    await waitFor(() => {
      expect(screen.getByText("Diagnóstico do arquivo")).toBeTruthy();
    });
    expect(String(espia.mock.calls[0][0])).toContain("use_sample=true");
  });

  it("oferece a escolha quando há ambiguidade de aba", async () => {
    mockFetch(
      respostaAnalise({
        status: "needs_selection",
        needs_choice: true,
        analysis: {},
        ambiguities: [
          {
            kind: "sheet",
            confidence: 0,
            sheet_options: [
              { name: "Vendas", score: 0.94, rows: 10, cols: 3 },
              { name: "Estoque", score: 0.94, rows: 8, cols: 2 },
            ],
            header_options: [],
          },
        ],
      }),
    );
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => {
      expect(screen.getByText("Abas encontradas")).toBeTruthy();
    });
    expect(screen.getByLabelText(/Vendas/)).toBeTruthy();
    expect(screen.getByLabelText(/Estoque/)).toBeTruthy();
  });

  it("oferece as linhas quando há ambiguidade de cabeçalho", async () => {
    mockFetch(
      respostaAnalise({
        status: "needs_selection",
        needs_choice: true,
        analysis: {},
        ambiguities: [
          {
            kind: "header",
            confidence: 0.3,
            sheet_options: [],
            header_options: [1, 4],
          },
        ],
      }),
    );
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => {
      expect(screen.getByText(/Linhas candidatas/)).toBeTruthy();
    });
    expect(screen.getByLabelText("Linha 4")).toBeTruthy();
  });

  it("mostra a recusa quando o arquivo não pode ser lido", async () => {
    mockFetch({
      token: "tok-2",
      status: "rejected_file",
      needs_choice: false,
      detail: "não foi possível ler este arquivo (BadZipFile)",
    });
    montar();
    await enviarArquivo("quebrado.xlsx");
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain(
        "não foi possível ler este arquivo",
      );
    });
    expect(
      screen.getByRole("button", { name: /Escolher outro arquivo/i }),
    ).toBeTruthy();
  });

  it("mostra erro controlado quando a resposta foge do contrato", async () => {
    // O produto REGISTRA o erro tecnico no console — e isso e desejado. Aqui
    // o spy captura esse log especifico para (a) nao poluir a saida da suite
    // e (b) PROVAR que o diagnostico foi registrado. Erros inesperados de
    // outros testes continuam aparecendo: o spy e local e restaurado.
    const logErro = vi.spyOn(console, "error").mockImplementation(() => {});

    // 200 OK, mas sem token: divergência de contrato, não falha de dados.
    mockFetch({ status: "analysis_ready" });
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain(
        "não pôde ser interpretada",
      );
    });
    // a estrutura continua visível — nada de tela vazia
    expect(screen.getByLabelText("principal")).toBeTruthy();

    // o erro técnico REALMENTE foi registrado, com o tipo certo
    expect(logErro).toHaveBeenCalled();
    const registrado = logErro.mock.calls.find((args) =>
      args.some((a) => a instanceof ContractError),
    );
    expect(registrado).toBeDefined();
    logErro.mockRestore();
  });

  it("mostra erro amigável em falha HTTP estruturada", async () => {
    mockFetch(
      { detail: "envie um arquivo por vez", code: "too_many_files" },
      { status: 400 },
    );
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain(
        "envie um arquivo por vez",
      );
    });
  });

  it("oferece recomeçar quando a sessão expira", async () => {
    mockFetch(
      { detail: "sessao nao encontrada ou expirada", code: "expired" },
      { status: 404 },
    );
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Recomeçar/i })).toBeTruthy();
    });
  });

  it("não dispara duas análises com dois cliques", async () => {
    const espia = mockFetch(respostaAnalise());
    montar();
    await enviarArquivo();
    const botao = screen.getByRole("button", { name: /Analisar meus dados/i });
    await userEvent.click(botao);
    await userEvent.click(botao);
    await waitFor(() => {
      expect(screen.getByText("Diagnóstico do arquivo")).toBeTruthy();
    });
    expect(espia).toHaveBeenCalledTimes(1);
  });

  it("não mostra a mesma observação duas vezes (regressão)", async () => {
    mockFetch(respostaAnalise());
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => {
      expect(screen.getByText("Diagnóstico do arquivo")).toBeTruthy();
    });
    // O payload traz a MESMA nota em `findings` e em `reader_warnings`.
    expect(
      screen.getAllByText(/16 linha\(s\) completamente identica/),
    ).toHaveLength(1);
  });

  it("nova análise substitui a anterior por completo", async () => {
    mockFetch(respostaAnalise());
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => expect(screen.getByText("7089")).toBeTruthy());

    // segunda análise, com outro arquivo e outro resultado
    mockFetch(
      respostaAnalise({
        analysis: {
          metadata: { source_file: "outro.csv", extension: ".csv" },
          leitura: {
            selected_sheet: null,
            header_row: 1,
            confidence: 1,
            available_sheets: [],
          },
          estrutura: { row_count: 12, column_count: 2 },
          columns: [{ name: "A", inferred_type: "texto", empty_count: 0 }],
          findings: [],
          reader_warnings: [],
        },
      }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar outro arquivo/i }),
    );
    await enviarArquivo("outro.csv");
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );

    await waitFor(() => expect(screen.getByText("12")).toBeTruthy());
    // nada da análise anterior sobrou
    expect(screen.queryByText("7089")).toBeNull();
    expect(screen.queryByText(/16 linha\(s\)/)).toBeNull();
  });

  it("distingue observação estrutural de problema de validação", async () => {
    mockFetch(respostaAnalise());
    montar();
    await enviarArquivo();
    await userEvent.click(
      screen.getByRole("button", { name: /Analisar meus dados/i }),
    );
    await waitFor(() => {
      expect(screen.getByText("Diagnóstico do arquivo")).toBeTruthy();
    });
    expect(screen.getByText(/observações sobre a/i).textContent).toContain(
      "estrutura",
    );
  });
});

describe("ErrorBoundary", () => {
  it("mantém a estrutura da página quando um filho quebra", () => {
    function Quebrado(): never {
      throw new Error("falha de render simulada");
    }
    // O React registra o erro no console; silenciamos só para não poluir a saída.
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <div>
        <nav aria-label="principal">navegação</nav>
        <ErrorBoundary area="teste">
          <Quebrado />
        </ErrorBoundary>
      </div>,
    );

    expect(screen.getByRole("alert").textContent).toContain("Algo deu errado");
    expect(screen.getByLabelText("principal")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Reiniciar análise/i }),
    ).toBeTruthy();
  });
});
