import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
