import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Politicas from "./Politicas";

/**
 * Tela de políticas de backup.
 *
 * É a tela que transforma "posso mandar fazer backup" em "tenho backup". O que
 * se protege aqui são as três suposições que custam caro:
 *
 * 1. que um pacote na própria máquina protege alguma coisa;
 * 2. que a política já está valendo, quando a máquina está desligada;
 * 3. que uma máquina sem pasta autorizada vai copiar algo.
 */

const DISPOSITIVO = {
  id: "d1",
  nome: "PC da loja",
  sistema: "Windows 11",
  versao_agente: "0.1.0",
  estado: "ativo" as const,
  impressao: "AAAA-BBBB-CCCC-DDDD",
  pareado_em: "2026-08-25T10:00:00+00:00",
  ultimo_contato: "2026-08-25T10:05:00+00:00",
};

const ESTADO = {
  dispositivo_id: "d1",
  estado: { ok: true, pode_copiar: true, raizes: ["C:\\Loja\\Dados"] },
};

const SEM_RAIZ = {
  dispositivo_id: "d1",
  estado: { ok: true, pode_copiar: false, raizes: [] },
};

function mockRotas(respostas: Record<string, unknown>) {
  const espiao = vi.fn(async (url: string, opcoes?: RequestInit) => {
    void opcoes;
    const rotas = Object.keys(respostas);
    const chave =
      rotas.find((rota) => url.endsWith(rota)) ??
      rotas.find((rota) => url.includes(rota));
    const corpo = chave ? respostas[chave] : { detail: "rota não simulada" };
    return {
      ok: Boolean(chave),
      status: chave ? 200 : 404,
      json: async () => corpo,
    } as Response;
  });
  vi.stubGlobal("fetch", espiao as unknown as typeof fetch);
  return espiao;
}

const BASE = {
  "/api/politicas": { politicas: [] },
  "/api/dispositivos": { dispositivos: [DISPOSITIVO] },
  "/consultar": ESTADO,
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("Políticas de backup", () => {
  it("sem máquina pareada, diz que a política precisa de uma", async () => {
    mockRotas({ "/api/politicas": { politicas: [] }, "/api/dispositivos": { dispositivos: [] } });

    render(<Politicas papel="dono" />);

    expect(await screen.findByText(/precisa de uma máquina pareada/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /nova política/i })).toBeNull();
  });

  it("sem política, diz que o backup só acontece quando alguém clica", async () => {
    // Lista vazia sem explicação faria alguém supor que já existe agendamento.
    mockRotas(BASE);

    render(<Politicas papel="dono" />);

    expect(await screen.findByText(/nenhuma política ainda/i)).toBeTruthy();
  });

  it("quem não administra não vê o botão de criar", async () => {
    mockRotas(BASE);

    render(<Politicas papel="leitor" />);

    await screen.findByText(/nenhuma política ainda/i);
    expect(screen.queryByRole("button", { name: /nova política/i })).toBeNull();
  });

  it("as pastas oferecidas são as autorizadas na máquina", async () => {
    // Nenhuma tela na nuvem concede acesso ao disco: a lista vem do próprio
    // dispositivo.
    mockRotas(BASE);

    render(<Politicas papel="dono" />);
    await userEvent.click(await screen.findByRole("button", { name: /nova política/i }));

    expect(await screen.findByText("C:\\Loja\\Dados")).toBeTruthy();
  });

  it("máquina sem pasta autorizada avisa que não copiaria nada", async () => {
    mockRotas({ ...BASE, "/consultar": SEM_RAIZ });

    render(<Politicas papel="dono" />);
    await userEvent.click(await screen.findByRole("button", { name: /nova política/i }));

    expect(await screen.findByText(/não copiaria nada/i)).toBeTruthy();
    const salvar = await screen.findByRole("button", { name: /salvar política/i });
    expect((salvar as HTMLButtonElement).disabled).toBe(true);
  });

  it("salva mandando as opções escolhidas", async () => {
    const espiao = mockRotas({
      ...BASE,
      "/api/politicas": { politicas: [] },
    });
    // O POST usa a mesma rota do GET; devolve o corpo do POST na segunda vez.
    let chamadas = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, opcoes?: RequestInit) => {
        if (String(url).endsWith("/api/politicas") && opcoes?.method === "POST") {
          chamadas += 1;
          return {
            ok: true,
            status: 200,
            json: async () => ({
              id: "p1",
              nome: "Backup diário",
              dispositivo_id: "d1",
              ativa: true,
              configuracao: JSON.parse(String(opcoes.body)).configuracao,
              protege_de_verdade: true,
              criada_em: "2026-08-25T10:00:00",
              atualizada_em: "2026-08-25T10:00:00",
              sincronizacao: { aplicada: true, politicas: 1 },
            }),
          } as Response;
        }
        return (espiao as unknown as typeof fetch)(url, opcoes);
      }) as unknown as typeof fetch,
    );

    render(<Politicas papel="dono" />);
    await userEvent.click(await screen.findByRole("button", { name: /nova política/i }));
    await screen.findByText("C:\\Loja\\Dados");

    await userEvent.type(
      screen.getByLabelText(/caminho do destino/i),
      "E:\\Backups",
    );
    await userEvent.click(screen.getByRole("button", { name: /salvar política/i }));

    await waitFor(() => expect(chamadas).toBe(1));
    expect(await screen.findByText(/já aplicada na máquina/i)).toBeTruthy();
  });

  it("máquina desligada: diz que vai valer, e não que está valendo", async () => {
    // A diferença entre "vai valer" e "está valendo" é a diferença entre ter
    // backup hoje à noite e descobrir amanhã que não teve.
    const espiao = mockRotas(BASE);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, opcoes?: RequestInit) => {
        if (String(url).endsWith("/api/politicas") && opcoes?.method === "POST") {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              id: "p1",
              nome: "Backup diário",
              dispositivo_id: "d1",
              ativa: true,
              configuracao: JSON.parse(String(opcoes.body)).configuracao,
              protege_de_verdade: true,
              criada_em: "2026-08-25T10:00:00",
              atualizada_em: "2026-08-25T10:00:00",
              sincronizacao: {
                aplicada: false,
                motivo: "a maquina esta desligada; a politica vale a partir da proxima conexao",
              },
            }),
          } as Response;
        }
        return (espiao as unknown as typeof fetch)(url, opcoes);
      }) as unknown as typeof fetch,
    );

    render(<Politicas papel="dono" />);
    await userEvent.click(await screen.findByRole("button", { name: /nova política/i }));
    await screen.findByText("C:\\Loja\\Dados");
    await userEvent.click(screen.getByRole("button", { name: /salvar política/i }));

    expect(await screen.findByText(/proxima conexao/i)).toBeTruthy();
    expect(screen.queryByText(/já aplicada na máquina/i)).toBeNull();
  });

  it("política que fica só na máquina é marcada como não protegida", async () => {
    // Pacote no mesmo computador não protege contra o disco morrer nem contra
    // ransomware. Dizer "configurado" sem isso seria uma palavra sem sentido.
    mockRotas({
      ...BASE,
      "/api/politicas": {
        politicas: [
          {
            id: "p1",
            nome: "Só local",
            dispositivo_id: "d1",
            ativa: true,
            configuracao: {
              origens: ["C:\\Loja\\Dados"],
              destino: { tipo: "nenhum", caminho: "" },
              agendamento: { tipo: "diario", hora: "02:00", dia_da_semana: 0, dia_do_mes: 1 },
              retencao: { diarias: 7, semanais: 4, mensais: 12 },
              retry: { tentativas: 3, espera_inicial_min: 5 },
              notificacao: { quando: "problema", emails: [] },
              usar_vss: false,
              cifrar: false,
              assinar: true,
              verificar: true,
              incremental: false,
            },
            protege_de_verdade: false,
            criada_em: "2026-08-25T10:00:00",
            atualizada_em: "2026-08-25T10:00:00",
          },
        ],
      },
    });

    render(<Politicas papel="dono" />);

    expect(await screen.findByText(/não protege contra o disco morrer/i)).toBeTruthy();
  });

  it("política sem horário é marcada como sem horário", async () => {
    mockRotas({
      ...BASE,
      "/api/politicas": {
        politicas: [
          {
            id: "p2",
            nome: "Manual",
            dispositivo_id: "d1",
            ativa: true,
            configuracao: {
              origens: ["C:\\Loja\\Dados"],
              destino: { tipo: "externo", caminho: "E:\\Backups" },
              agendamento: { tipo: "desligado", hora: "02:00", dia_da_semana: 0, dia_do_mes: 1 },
              retencao: { diarias: 7, semanais: 4, mensais: 12 },
              retry: { tentativas: 3, espera_inicial_min: 5 },
              notificacao: { quando: "problema", emails: [] },
              usar_vss: false,
              cifrar: false,
              assinar: true,
              verificar: true,
              incremental: false,
            },
            protege_de_verdade: true,
            criada_em: "2026-08-25T10:00:00",
            atualizada_em: "2026-08-25T10:00:00",
          },
        ],
      },
    });

    render(<Politicas papel="dono" />);

    expect(await screen.findByText(/só executa quando alguém manda/i)).toBeTruthy();
  });

  it("executar agora usa as MESMAS escolhas da política", async () => {
    // Um "executar agora" que rodasse diferente do horário faria o cliente
    // testar uma coisa e receber outra de madrugada.
    const politica = {
      id: "p3",
      nome: "Diária",
      dispositivo_id: "d1",
      ativa: true,
      configuracao: {
        origens: ["C:\Loja\Dados"],
        destino: { tipo: "externo", caminho: "E:\Backups" },
        agendamento: { tipo: "diario", hora: "02:00", dia_da_semana: 0, dia_do_mes: 1 },
        retencao: { diarias: 7, semanais: 4, mensais: 12 },
        retry: { tentativas: 3, espera_inicial_min: 5 },
        notificacao: { quando: "problema", emails: [] },
        usar_vss: false,
        cifrar: false,
        assinar: true,
        verificar: true,
        incremental: true,
      },
      protege_de_verdade: true,
      criada_em: "2026-08-25T10:00:00",
      atualizada_em: "2026-08-25T10:00:00",
    };
    const espiao = mockRotas({
      ...BASE,
      "/api/politicas": { politicas: [politica] },
      "/backup": { execucao_id: "e1", ok: true, pacote: "backup_2026-08-25_1200.zip" },
    });

    render(<Politicas papel="dono" />);
    await userEvent.click(await screen.findByRole("button", { name: /executar agora/i }));

    await waitFor(() =>
      expect(
        espiao.mock.calls.some((c) => String(c[0]).endsWith("/backup")),
      ).toBe(true),
    );
    const pedido = espiao.mock.calls.find((c) => String(c[0]).endsWith("/backup"));
    const corpo = JSON.parse(String((pedido?.[1] as RequestInit)?.body));
    expect(corpo.destino_externo).toBe("E:\Backups");
    expect(corpo.tipo_do_destino).toBe("externo");
    expect(corpo.incremental).toBe(true);
    expect(corpo.origens).toEqual(["C:\Loja\Dados"]);
    expect(await screen.findByText(/backup concluído/i)).toBeTruthy();
  });
});
