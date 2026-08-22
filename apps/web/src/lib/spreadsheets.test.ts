import { describe, expect, it } from "vitest";

import {
  ContractError,
  notasUnificadas,
  parseAnalysis,
  parseSchemaResponse,
} from "./spreadsheets";

/**
 * A fronteira de confianca.
 *
 * O primeiro teste reproduz a REGRESSAO que derrubou a aplicacao: o backend
 * devolve `reader_warnings` como lista de OBJETOS, e o front tratava como
 * lista de textos. O React lancava "Objects are not valid as a React child"
 * durante o render e a arvore inteira desmontava.
 */

/** Recorte fiel do payload real do backend (Vendas - Dez, com duplicatas). */
const PAYLOAD_REAL = {
  token: "abc123",
  status: "analysis_ready",
  needs_choice: false,
  preview: "linha 1\nlinha 2",
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
      {
        name: "Código Venda",
        inferred_type: "inteiro",
        empty_count: 0,
        distinct_count: 3787,
      },
    ],
    findings: [
      {
        code: "linhas_duplicadas",
        severity: "aviso",
        message: "16 linha(s) completamente identica(s) a outra",
        column: null,
        row: null,
      },
    ],
    // O ponto exato do bug: OBJETOS, nao textos.
    reader_warnings: [
      {
        code: "linhas_duplicadas",
        message: "16 linha(s) completamente identica(s) a outra",
        column: null,
        row: null,
      },
    ],
  },
};

describe("parseAnalysis", () => {
  it("normaliza reader_warnings em objetos para texto exibível (regressão)", () => {
    const dados = parseAnalysis(PAYLOAD_REAL);
    expect(dados.analysis).not.toBeNull();
    const avisos = dados.analysis!.reader_warnings;
    expect(avisos).toHaveLength(1);
    // O que o componente renderiza tem de ser primitivo.
    expect(typeof avisos[0].message).toBe("string");
    expect(avisos[0].code).toBe("linhas_duplicadas");
  });

  it("achata a estrutura aninhada do relatório", () => {
    const dados = parseAnalysis(PAYLOAD_REAL);
    expect(dados.analysis?.source_file).toBe("Vendas - Dez (2).xlsx");
    expect(dados.analysis?.row_count).toBe(7089);
    expect(dados.analysis?.column_count).toBe(7);
    expect(dados.analysis?.columns[0].name).toBe("Código Venda");
  });

  it("aceita aviso que venha como texto puro", () => {
    const dados = parseAnalysis({
      ...PAYLOAD_REAL,
      analysis: {
        ...PAYLOAD_REAL.analysis,
        reader_warnings: ["aviso simples"],
      },
    });
    expect(dados.analysis?.reader_warnings[0].message).toBe("aviso simples");
  });

  it("descarta nota sem mensagem em vez de exibir vazio", () => {
    const dados = parseAnalysis({
      ...PAYLOAD_REAL,
      analysis: {
        ...PAYLOAD_REAL.analysis,
        reader_warnings: [{ code: "x", column: null }, 42, null],
      },
    });
    expect(dados.analysis?.reader_warnings).toHaveLength(0);
  });

  it("preenche arrays ausentes em vez de deixar undefined", () => {
    const dados = parseAnalysis({
      ...PAYLOAD_REAL,
      ambiguities: undefined,
      analysis: {
        ...PAYLOAD_REAL.analysis,
        findings: undefined,
        reader_warnings: undefined,
      },
    });
    expect(dados.ambiguities).toEqual([]);
    expect(dados.analysis?.findings).toEqual([]);
    expect(dados.analysis?.reader_warnings).toEqual([]);
  });

  it("normaliza ambiguidade de aba", () => {
    const dados = parseAnalysis({
      ...PAYLOAD_REAL,
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
    });
    expect(dados.needs_choice).toBe(true);
    expect(dados.ambiguities[0].sheet_options.map((o) => o.name)).toEqual([
      "Vendas",
      "Estoque",
    ]);
  });

  it("normaliza ambiguidade de cabeçalho preservando numeração física", () => {
    const dados = parseAnalysis({
      ...PAYLOAD_REAL,
      status: "needs_selection",
      needs_choice: true,
      analysis: {},
      ambiguities: [
        {
          kind: "header",
          confidence: 0.3,
          sheet_options: [],
          header_options: [1, 4, 7],
        },
      ],
    });
    expect(dados.ambiguities[0].header_options).toEqual([1, 4, 7]);
  });

  it("descarta ambiguidade sem opções respondíveis", () => {
    const dados = parseAnalysis({
      ...PAYLOAD_REAL,
      ambiguities: [
        { kind: "sheet", confidence: 0, sheet_options: [], header_options: [] },
      ],
    });
    expect(dados.ambiguities).toHaveLength(0);
    expect(dados.needs_choice).toBe(false);
  });

  it("aceita arquivo recusado com a explicação", () => {
    const dados = parseAnalysis({
      token: "t1",
      status: "rejected_file",
      needs_choice: false,
      detail: "arquivo corrompido",
    });
    expect(dados.status).toBe("rejected_file");
    expect(dados.rejection).toBe("arquivo corrompido");
  });

  describe("invariantes", () => {
    it("recusa análise pronta sem relatório utilizável", () => {
      expect(() =>
        parseAnalysis({ ...PAYLOAD_REAL, analysis: { columns: [] } }),
      ).toThrow(ContractError);
    });

    it("recusa seleção pedida sem opções", () => {
      expect(() =>
        parseAnalysis({
          ...PAYLOAD_REAL,
          status: "needs_selection",
          ambiguities: [],
        }),
      ).toThrow(ContractError);
    });

    it("recusa recusa sem explicação", () => {
      expect(() =>
        parseAnalysis({
          token: "t",
          status: "rejected_file",
          needs_choice: false,
        }),
      ).toThrow(ContractError);
    });

    it("recusa corpo sem token", () => {
      expect(() => parseAnalysis({ status: "analysis_ready" })).toThrow(
        ContractError,
      );
    });

    it("recusa corpo que não é objeto", () => {
      expect(() => parseAnalysis("texto")).toThrow(ContractError);
      expect(() => parseAnalysis(null)).toThrow(ContractError);
    });
  });
});

describe("notasUnificadas", () => {
  const base = {
    source_file: "x.xlsx",
    extension: ".xlsx",
    selected_sheet: null,
    header_row: null,
    confidence: null,
    header_confidence: null,
    available_sheets: [],
    row_count: null,
    column_count: null,
    columns: [],
  };

  it("não repete a mesma ocorrência vinda das duas coleções (regressão)", () => {
    // O backend descreve a MESMA linha duplicada em `findings` (com
    // severidade) e em `reader_warnings` (sem). A tela mostrava duas vezes.
    const notas = notasUnificadas({
      ...base,
      findings: [
        {
          code: "linhas_duplicadas",
          severity: "aviso",
          message: "16 linhas iguais",
          column: null,
          row: null,
        },
      ],
      reader_warnings: [
        {
          code: "linhas_duplicadas",
          severity: null,
          message: "16 linhas iguais",
          column: null,
          row: null,
        },
      ],
    });
    expect(notas).toHaveLength(1);
    // fica a versão mais informativa: nenhum metadado se perde
    expect(notas[0].severity).toBe("aviso");
  });

  it("preserva ocorrências distintas com a mesma mensagem", () => {
    // Mesma mensagem em COLUNAS diferentes são dois fatos, não repetição.
    const notas = notasUnificadas({
      ...base,
      findings: [
        {
          code: "vazios",
          severity: "aviso",
          message: "coluna com vazios",
          column: "A",
          row: null,
        },
        {
          code: "vazios",
          severity: "aviso",
          message: "coluna com vazios",
          column: "B",
          row: null,
        },
      ],
      reader_warnings: [],
    });
    expect(notas).toHaveLength(2);
  });

  it("mantém avisos que só o leitor reportou", () => {
    const notas = notasUnificadas({
      ...base,
      findings: [],
      reader_warnings: [
        {
          code: "conversao",
          severity: null,
          message: "valor convertido",
          column: "C",
          row: 5,
        },
      ],
    });
    expect(notas).toHaveLength(1);
    expect(notas[0].row).toBe(5);
  });
});

describe("perfis (1.8C-2)", () => {
  const RESPOSTA_PERFIL = {
    token: "tok",
    status: "schema_ready",
    schema_origin: "profile",
    summary: {
      columns: [],
      detect_duplicate_rows: false,
      group_keys: [],
      group_checks: [],
      derived_checks: [],
    },
    profile: {
      id: "cadastro_contatos",
      version: 1,
      mapping: { nome: "Nome Completo", cpf: "Documento" },
      omitted: ["telefone", "cnpj"],
    },
  };

  it("normaliza a procedência confirmada pelo backend", () => {
    const r = parseSchemaResponse(RESPOSTA_PERFIL);
    expect(r.schema_origin).toBe("profile");
    expect(r.profile?.id).toBe("cadastro_contatos");
    expect(r.profile?.mapping.cpf).toBe("Documento");
    expect(r.profile?.omitted).toContain("telefone");
  });

  it("aceita schema sugerido sem bloco de perfil", () => {
    const r = parseSchemaResponse({
      ...RESPOSTA_PERFIL,
      schema_origin: "suggested",
      profile: undefined,
    });
    expect(r.schema_origin).toBe("suggested");
    expect(r.profile).toBeNull();
  });

  it("recusa schema de perfil sem procedência (invariante)", () => {
    expect(() =>
      parseSchemaResponse({ ...RESPOSTA_PERFIL, profile: undefined }),
    ).toThrow(ContractError);
  });

  it("recusa origem de schema desconhecida", () => {
    expect(() =>
      parseSchemaResponse({ ...RESPOSTA_PERFIL, schema_origin: "inventada" }),
    ).toThrow(ContractError);
  });

  it("descarta mapeamento com valor não textual", () => {
    const r = parseSchemaResponse({
      ...RESPOSTA_PERFIL,
      profile: {
        ...RESPOSTA_PERFIL.profile,
        mapping: { nome: "N", cpf: 42, x: null },
      },
    });
    expect(Object.keys(r.profile!.mapping)).toEqual(["nome"]);
  });
});
