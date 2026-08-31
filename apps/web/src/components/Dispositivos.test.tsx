import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Dispositivos from "./Dispositivos";
import { comVolta, enderecoDa } from "../lib/rotas";

/**
 * Testes da tela de máquinas.
 *
 * O que se protege aqui não é layout: é a recusa de mentir. Botão que não
 * funciona, "conectado" para máquina desligada e "erro" para computador
 * fechado à noite são os três jeitos mais fáceis de uma interface enganar
 * quem confia nela.
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

/** Responde por rota, como o servidor faria. */
function mockRotas(
  respostas: Record<string, { corpo: unknown; status?: number }>,
): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      // Casa pelo FIM da URL primeiro. `/api/dispositivos` também aparece
      // dentro de `/api/dispositivos/d1/consultar`, e casar por conteúdo
      // faria a consulta receber a lista de dispositivos.
      const rotas = Object.keys(respostas);
      const chave =
        rotas.find((rota) => url.endsWith(rota)) ??
        rotas.find((rota) => url.includes(rota));
      const item = chave ? respostas[chave] : undefined;
      const status = item?.status ?? (item ? 200 : 404);
      return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => item?.corpo ?? { detail: "rota não simulada" },
      } as Response;
    }),
  );
}

describe("Dispositivos", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState(null, "", enderecoDa("dispositivos"));
  });

  it("mostra 'Desligado' para máquina cadastrada e sem canal aberto", async () => {
    // Mostrar "ativo" só porque existe uma linha no banco faria alguém
    // confiar num backup que não vai acontecer.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            { dispositivo_id: "d1", nome: "PC da loja", conectado: false, desde: "" },
          ],
          total_conectados: 0,
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("Desligado")).toBeTruthy();
    });
  });

  it("mostra 'Conectado' quando há canal aberto", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            {
              dispositivo_id: "d1",
              nome: "PC da loja",
              conectado: true,
              desde: "2026-08-25T10:00:00+00:00",
            },
          ],
          total_conectados: 1,
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("Conectado")).toBeTruthy();
    });
  });

  it("revogado ganha do estado de conexão", async () => {
    // Um dispositivo revogado que por acaso ainda aparecesse conectado não
    // pode ser mostrado como se estivesse em serviço.
    mockRotas({
      "/api/dispositivos": {
        corpo: { dispositivos: [{ ...DISPOSITIVO, estado: "revogado" }] },
      },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            { dispositivo_id: "d1", nome: "PC", conectado: true, desde: "" },
          ],
          total_conectados: 1,
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("Revogado")).toBeTruthy();
    });
  });

  it("máquina desligada vira frase clara, não erro", async () => {
    // Tratar como falha faria a tela acusar problema toda noite, quando o
    // computador da loja está simplesmente fechado.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
      "/consultar": {
        corpo: { detail: "nao ha canal aberto com este dispositivo" },
        status: 409,
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /Ver pastas autorizadas/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/está desligada ou sem conexão/i)).toBeTruthy();
    });
  });

  it("avisa quando o dispositivo não tem pasta autorizada", async () => {
    // Um Agente pareado sem pasta autorizada não copia nada, e isso é fácil
    // de confundir com "está funcionando".
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            { dispositivo_id: "d1", nome: "PC", conectado: true, desde: "" },
          ],
          total_conectados: 1,
        },
      },
      "/consultar": {
        corpo: {
          dispositivo_id: "d1",
          estado: { ok: true, raizes: [], pode_copiar: false, versao_agente: "0.1.0" },
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /Ver pastas autorizadas/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/não copiaria nada/i)).toBeTruthy();
    });
    expect(screen.getByText(/no próprio computador/i)).toBeTruthy();
  });

  it("quem só lê não vê botão de parear nem de revogar", async () => {
    // O papel vem do servidor; a tela não pode oferecer o que ele recusaria.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="leitor" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    expect(screen.queryByRole("button", { name: /Parear nova máquina/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Revogar/i })).toBeNull();
    expect(
      screen.queryByRole("button", { name: /Executar backup agora/i }),
    ).toBeNull();
  });

  it("operador executa mas não pareia", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="operador" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    expect(
      screen.getByRole("button", { name: /Executar backup agora/i }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Parear nova máquina/i })).toBeNull();
  });

  it("enquanto carrega, não afirma que não há máquina", async () => {
    // A frase "Nenhuma máquina pareada ainda" aparecia no intervalo entre
    // abrir a tela e o servidor responder — falsa, curta, e exatamente na
    // cara de quem tem máquina pareada.
    let responder: (valor: unknown) => void = () => {};
    const espera = new Promise((pronto) => {
      responder = pronto;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        await espera;
        return {
          ok: true,
          status: 200,
          json: async () =>
            url.includes("conectados")
              ? { conectados: [], total_conectados: 0 }
              : { dispositivos: [DISPOSITIVO] },
        } as Response;
      }),
    );
    render(<Dispositivos papel="dono" />);

    expect(screen.queryByText(/Nenhuma máquina pareada/i)).toBeNull();
    expect(screen.getByText(/Carregando/i)).toBeTruthy();

    responder(null);
    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
  });

  it("sem máquina pareada, explica o que falta", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText(/Nenhuma máquina pareada ainda/i)).toBeTruthy();
    });
    expect(screen.getByText(/depende do Agente instalado/i)).toBeTruthy();
  });

  it("parear leva ao roteiro de instalação, com o código dentro do comando", async () => {
    // O código sozinho não instala nada. Quem vai proteger a máquina precisa do
    // pacote, do comando e do prazo — e o prazo importa porque o código serve
    // uma vez só.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
      "/api/dispositivos/codigo": {
        corpo: {
          codigo: "ABCD-EFGH",
          expira_em: "2026-08-25T10:10:00+00:00",
          validade_minutos: 10,
        },
      },
      "/api/agente/instalador/ficha": {
        corpo: {
          nome: "autotarefas-agente.zip",
          tamanho_bytes: 451000,
          arquivos: 152,
          precisa_de_python: "3.13",
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Parear nova máquina/i }),
      ).toBeTruthy();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /Parear nova máquina/i }),
    );

    const comando = await screen.findByText(/instalar\.ps1/);
    expect(comando.textContent).toContain("ABCD-EFGH");
    expect(screen.getByText(/serve uma vez só/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: /baixar o agente/i })).toBeTruthy();
  });
});

describe("voltar de onde se veio", () => {
  const VOLTA = comVolta(enderecoDa("dispositivos"), enderecoDa("backups"));

  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState(null, "", VOLTA);
  });

  it("sem máquina ainda, avisa que há uma configuração esperando", async () => {
    // Parear acontece em OUTRO computador e leva minutos. Sem esta faixa, a
    // pessoa volta e não lembra de onde saiu.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText(/estava configurando um backup/i)).toBeTruthy();
    });
  });

  it("com a máquina pronta, a faixa vira o convite para terminar", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="dono" />);

    const volta = await screen.findByRole("link", {
      name: /Voltar para a configuração do backup/i,
    });
    expect(volta.getAttribute("href")).toBe(enderecoDa("backups"));
  });

  it("sem `voltar` na URL, nenhuma faixa aparece", async () => {
    window.history.replaceState(null, "", enderecoDa("dispositivos"));
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    expect(screen.queryByText(/Voltar para a configuração/i)).toBeNull();
  });

  it("um `voltar` para fora do produto é ignorado", async () => {
    // O parâmetro vem da URL, logo de fora. Sem o filtro, seria um botão com a
    // cara do AutoTarefas levando para outro lugar.
    window.history.replaceState(
      null,
      "",
      comVolta(enderecoDa("dispositivos"), "https://exemplo.invalido"),
    );
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    expect(screen.queryByText(/Voltar para a configuração/i)).toBeNull();
  });
});

/**
 * As maquinas na demonstracao publica.
 *
 * "Ver pastas autorizadas" parece leitura e nao e: a rota e `POST`, porque
 * manda um comando pelo canal ate o computador. Numa sessao publica ela
 * responde 403 — e um botao que so sabe falhar e um botao sem funcao.
 */
describe("Dispositivos na demonstracao publica", () => {
  it("nao oferece o botao que responderia 403", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            { dispositivo_id: "d1", nome: "PC da loja", conectado: true, desde: "" },
          ],
          total_conectados: 1,
        },
      },
    });

    render(<Dispositivos papel="leitor" somenteLeitura />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    expect(
      screen.queryByRole("button", { name: /ver pastas autorizadas/i }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /executar backup agora/i }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /parear nova máquina/i }),
    ).toBeNull();
  });

  it("explica de quem e a maquina, em vez de deixar o cartao mudo", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });

    render(<Dispositivos papel="leitor" somenteLeitura />);

    expect(
      await screen.findByText(/pertence ao ambiente do projeto/i),
    ).toBeTruthy();
  });
});

/**
 * O cartao da maquina.
 *
 * Ele dizia "Windows 11 · Agente 0.1.0 · impressao AAAA-..." numa linha so, e
 * parava ai. Quem chega precisa entender quatro coisas em sequencia: existe
 * uma maquina, existe um Agente, ele esta conectado, e as automacoes estao
 * acontecendo. As tres ultimas nao estavam na tela.
 */
describe("o que o cartao da maquina conta", () => {
  const POLITICA = {
    id: "p1",
    nome: "Backup diario 03:00",
    dispositivo_id: "d1",
    ativa: true,
    configuracao: {
      origens: ["/dados"],
      destino: { tipo: "local", caminho: "/destino" },
      agendamento: { tipo: "diario", hora: "03:00", dia_da_semana: 0, dia_do_mes: 1 },
      retencao: { diarias: 7, semanais: 4, mensais: 12 },
      retry: { tentativas: 3, espera_inicial_min: 5 },
      notificacao: { quando: "problema", emails: [] },
      usar_vss: false,
      cifrar: false,
      assinar: true,
      incremental: false,
    },
    protege_de_verdade: false,
    criada_em: "2026-08-30T11:00:00+00:00",
    atualizada_em: "2026-08-30T11:00:00+00:00",
  };

  const COMPLETO = {
    "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
    "/api/agente/conectados": {
      corpo: {
        conectados: [
          { dispositivo_id: "d1", nome: "PC da loja", conectado: true, desde: "" },
        ],
        total_conectados: 1,
      },
    },
    "/api/politicas": { corpo: { politicas: [POLITICA] } },
    "/api/historico": {
      corpo: {
        execucoes: [
          {
            id: "e1",
            dispositivo_id: "d1",
            politica_id: "p1",
            origem: "agendamento",
            resultado: "sucesso",
            iniciada_em: "2026-08-30T17:10:00+00:00",
            terminada_em: "2026-08-30T17:13:00+00:00",
            arquivos: 5,
            bytes_copiados: 2048,
            ressalva: "",
            artefatos: [],
          },
        ],
      },
    },
    "/api/atividade/ao-vivo": {
      corpo: {
        agora: "2026-08-30T18:00:00+00:00",
        executando: [],
        proximas: [
          {
            politica_id: "p1",
            nome: "Backup diario 03:00",
            maquina: "PC da loja",
            proxima_no_relogio_da_maquina: "2026-08-31T03:00:00",
            quando: "diario",
            hora: "03:00",
          },
        ],
      },
    },
  };

  it("conta quantos backups aquela maquina executa", async () => {
    mockRotas(COMPLETO);

    render(<Dispositivos papel="leitor" somenteLeitura />);

    expect(await screen.findByText("Backups ativos")).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
  });

  it("mostra o ultimo backup com o desfecho, e nao so a data", async () => {
    // "Com ressalva" nao pode virar "Concluido": um backup que copiou quase
    // tudo tem ausencias, e quem for restaurar precisa saber antes.
    mockRotas(COMPLETO);

    render(<Dispositivos papel="leitor" somenteLeitura />);

    expect(await screen.findByText("Último backup")).toBeTruthy();
    expect(screen.getByText(/Concluído/)).toBeTruthy();
  });

  it("mostra quando e a proxima execucao", async () => {
    mockRotas(COMPLETO);

    render(<Dispositivos papel="leitor" somenteLeitura />);

    expect(await screen.findByText("Próxima execução")).toBeTruthy();
    expect(screen.getByText(/Backup diario 03:00/)).toBeTruthy();
  });

  it("sem as rotas acessorias, o cartao continua de pe", async () => {
    // A afirmacao principal e "existe uma maquina, e o Agente esta
    // conectado". Uma rota acessoria fora do ar nao pode apagar da tela a
    // maquina que esta ali, funcionando.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            { dispositivo_id: "d1", nome: "PC da loja", conectado: true, desde: "" },
          ],
          total_conectados: 1,
        },
      },
    });

    render(<Dispositivos papel="leitor" somenteLeitura />);

    expect(await screen.findByText("PC da loja")).toBeTruthy();
    expect(screen.getByText("Conectado")).toBeTruthy();
    expect(screen.getByText("nenhum ainda")).toBeTruthy();
  });
});
