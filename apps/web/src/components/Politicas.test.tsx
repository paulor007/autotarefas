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
  it("sem máquina pareada, oferece o caminho para adicionar uma", async () => {
    // Dizer "precisa de uma máquina" e parar aí deixava a pessoa procurando
    // onde. O aviso vira uma porta, e a porta guarda o caminho de volta: quem
    // sai daqui para parear vai mexer em OUTRO computador, e precisa
    // reencontrar esta tela sem refazer nada.
    mockRotas({ "/api/politicas": { politicas: [] }, "/api/dispositivos": { dispositivos: [] } });

    render(<Politicas papel="dono" />);

    expect(await screen.findByText(/Nenhuma máquina conectada/i)).toBeTruthy();
    const porta = screen.getByRole("link", { name: /Adicionar máquina/i });
    expect(porta.getAttribute("href")).toBe(
      "/app/dispositivos?voltar=%2Fapp%2Fbackups",
    );
    expect(screen.queryByRole("button", { name: /configurar backup/i })).toBeNull();
  });

  it("com máquina e sem política, o assistente já abre", async () => {
    // Quem chega aqui nesse estado veio configurar. Exigir um clique para
    // revelar o formulário seria cobrar um clique por uma tela vazia.
    mockRotas(BASE);

    render(<Politicas papel="dono" />);

    expect(await screen.findByRole("button", { name: /ativar backup/i })).toBeTruthy();
  });

  it("quem só lê vê a explicação, e não o assistente", async () => {
    // Lista vazia sem explicação faria alguém supor que já existe agendamento.
    mockRotas(BASE);

    render(<Politicas papel="leitor" />);

    expect(await screen.findByText(/nenhuma política ainda/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /ativar backup/i })).toBeNull();
  });

  it("quem não administra não vê o botão de criar", async () => {
    mockRotas(BASE);

    render(<Politicas papel="leitor" />);

    await screen.findByText(/nenhuma política ainda/i);
    expect(screen.queryByRole("button", { name: /configurar backup/i })).toBeNull();
  });

  it("as pastas oferecidas são as autorizadas na máquina", async () => {
    // Nenhuma tela na nuvem concede acesso ao disco: a lista vem do próprio
    // dispositivo.
    mockRotas(BASE);

    render(<Politicas papel="dono" />);

    expect(await screen.findByText("C:\\Loja\\Dados")).toBeTruthy();
  });

  it("máquina sem pasta autorizada avisa que não copiaria nada", async () => {
    mockRotas({ ...BASE, "/consultar": SEM_RAIZ });

    render(<Politicas papel="dono" />);

    expect(await screen.findByText(/não copiaria nada/i)).toBeTruthy();
    const salvar = await screen.findByRole("button", { name: /ativar backup/i });
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
    await screen.findByText("C:\\Loja\\Dados");

    await userEvent.type(
      screen.getByLabelText(/caminho do destino/i),
      "E:\\Backups",
    );
    await userEvent.click(screen.getByRole("button", { name: /ativar backup/i }));

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
    await screen.findByText("C:\\Loja\\Dados");
    await userEvent.click(screen.getByRole("button", { name: /ativar backup/i }));

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

describe("assistente de configuração", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("o que é raro fica atrás de Configurações avançadas", async () => {
    // Retry, cifra, assinatura e VSS têm padrão sensato e quase ninguém muda.
    // Deixá-los sempre à vista fazia a tela parecer difícil e escondia as
    // quatro decisões que importam.
    mockRotas(BASE);

    render(<Politicas papel="dono" />);

    const avancadas = await screen.findByText(/Configurações avançadas/i);
    const bloco = avancadas.closest("details");
    expect(bloco).toBeTruthy();
    expect((bloco as HTMLDetailsElement).open).toBe(false);
    expect(bloco?.contains(screen.getByLabelText("Tentativas"))).toBe(true);
    expect(
      bloco?.contains(screen.getByLabelText(/Copiar só o que mudou/i)),
    ).toBe(true);

    // E as decisões que importam ficam fora dele.
    expect(bloco?.contains(screen.getByLabelText("Tipo de destino"))).toBe(
      false,
    );
    expect(bloco?.contains(screen.getByLabelText("Frequência"))).toBe(false);
  });

  it("antes de ativar, a tela diz em português o que vai acontecer", async () => {
    // Uma tela só de campos deixa a pessoa ativar sem nunca ter visto, junto,
    // o que combinou.
    mockRotas(BASE);

    render(<Politicas papel="dono" />);
    await screen.findByText("C:\\Loja\\Dados");

    const frase = screen.getByRole("status").textContent ?? "";
    expect(frase).toContain("1 pasta");
    expect(frase).toContain("PC da loja");
    expect(frase).toContain("um disco externo");
    expect(frase).toContain("todo dia às 02:00");
    expect(frase).toContain("7 diários");
  });

  it("sem horário, o resumo não promete backup automático", async () => {
    mockRotas(BASE);

    render(<Politicas papel="dono" />);
    await screen.findByText("C:\\Loja\\Dados");
    await userEvent.selectOptions(
      screen.getByLabelText("Frequência"),
      "desligado",
    );

    expect(screen.getByText(/só executa quando alguém clicar/i)).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(
      "só quando alguém mandar",
    );
  });

  it("sem pasta escolhida, ativar fica indisponível e a tela diz por quê", async () => {
    mockRotas(BASE);

    render(<Politicas papel="dono" />);
    const pasta = await screen.findByText("C:\\Loja\\Dados");
    await userEvent.click(
      pasta.closest("label")?.querySelector("input") as HTMLInputElement,
    );

    expect(screen.getByText(/Escolha ao menos uma pasta/i)).toBeTruthy();
    const ativar = screen.getByRole("button", { name: /ativar backup/i });
    expect((ativar as HTMLButtonElement).disabled).toBe(true);
  });

  it("com a nuvem escolhida, ativar continua disponível", async () => {
    // Houve uma fase em que o servidor recusava destino na nuvem, porque o
    // agendamento nao tinha como entregar. Agora tem: o pacote nasce offline e
    // sobe quando ha canal. Deixar o botao travado aqui seria manter na tela a
    // marca de um limite que nao existe mais.
    mockRotas(BASE);

    render(<Politicas papel="dono" />);
    await screen.findByText("C:\\Loja\\Dados");
    await userEvent.selectOptions(
      screen.getByLabelText("Tipo de destino"),
      "nuvem",
    );

    const ativar = screen.getByRole("button", { name: /ativar backup/i });
    expect((ativar as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByRole("status").textContent).toContain("a nuvem");
  });
});

/**
 * A mesma tela na demonstração pública.
 *
 * Quem chega pelo portfólio não veio operar backup nenhum: veio descobrir o
 * que o produto faz. Antes disto a tela resolvia o assunto escondendo tudo —
 * um `leitor` não via o assistente, e portanto não via que existe disco
 * externo, pasta de rede ou nuvem. Escondia também um botão que respondia 403.
 *
 * O que estes testes fixam é o meio-termo: mostrar as escolhas, e não fingir
 * que elas seriam gravadas.
 */
describe("Backups na demonstração pública", () => {
  const POLITICA = {
    id: "p1",
    nome: "Backup diario 03:00",
    dispositivo_id: "d1",
    ativa: true,
    configuracao: {
      origens: ["/dados"],
      destino: { tipo: "local", caminho: "/destino" },
      agendamento: {
        tipo: "diario",
        hora: "03:00",
        dia_da_semana: 0,
        dia_do_mes: 1,
      },
      retencao: { diarias: 7, semanais: 4, mensais: 12 },
      retry: { tentativas: 3, espera_inicial_min: 5 },
      notificacao: { quando: "problema", emails: [] },
      usar_vss: false,
      cifrar: false,
      assinar: true,
      incremental: false,
    },
    protege_de_verdade: false,
    criada_em: "2026-08-30T11:36:00",
    atualizada_em: "2026-08-30T11:36:00",
  };

  const COM_POLITICA = {
    ...BASE,
    "/api/politicas": { politicas: [POLITICA] },
  };

  it("não oferece botão que o servidor recusaria", async () => {
    // "Executar agora" e "Remover" respondem 403 nesta sessao. Um botao que
    // so sabe recusar e um botao sem funcao — e o 403 chegaria como erro
    // vermelho, que e a forma mais cara de explicar uma regra de produto.
    mockRotas(COM_POLITICA);

    render(<Politicas papel="leitor" somenteLeitura />);
    await screen.findByText("Backup diario 03:00");

    expect(screen.queryByRole("button", { name: /executar agora/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /remover/i })).toBeNull();
  });

  it("diz que os backups rodam sozinhos, em vez de deixar a lista muda", async () => {
    mockRotas(COM_POLITICA);

    render(<Politicas papel="leitor" somenteLeitura />);

    expect(await screen.findByText(/rodam sozinhos/i)).toBeTruthy();
  });

  it("deixa ver as opções de destino, que era o que estava escondido", async () => {
    mockRotas(COM_POLITICA);

    render(<Politicas papel="leitor" somenteLeitura />);
    await userEvent.click(
      await screen.findByRole("button", { name: /ver como se configura/i }),
    );

    const destino = await screen.findByLabelText("Tipo de destino");
    const opcoes = Array.from(
      destino.querySelectorAll("option"),
      (item) => item.textContent ?? "",
    );
    expect(opcoes).toContain("Disco externo");
    expect(opcoes).toContain("Pasta de rede");
    expect(opcoes.some((item) => /nuvem/i.test(item))).toBe(true);
  });

  it("a frase do resumo acompanha o destino escolhido", async () => {
    // O valor do assistente aberto e este: a pessoa muda o destino e ve o
    // produto responder. Sem isso seriam campos bonitos e inertes.
    mockRotas(COM_POLITICA);

    render(<Politicas papel="leitor" somenteLeitura />);
    await userEvent.click(
      await screen.findByRole("button", { name: /ver como se configura/i }),
    );
    await userEvent.selectOptions(
      await screen.findByLabelText("Tipo de destino"),
      "nuvem",
    );

    expect(screen.getByRole("status").textContent).toContain("a nuvem");
  });

  it("a nuvem explica que o pacote sobe depois", async () => {
    // O agendamento roda offline de proposito e o Agente nao grava chave de
    // nuvem em disco. O que destrava as duas coisas e o envio ser diferido —
    // e quem escolhe o destino precisa saber disso ANTES, ou vera "aguardando
    // envio" no painel de madrugada e pensara em defeito.
    mockRotas(COM_POLITICA);

    render(<Politicas papel="leitor" somenteLeitura />);
    await userEvent.click(
      await screen.findByRole("button", { name: /ver como se configura/i }),
    );
    await userEvent.selectOptions(
      await screen.findByLabelText("Tipo de destino"),
      "nuvem",
    );

    expect(screen.getByText(/sobe assim que houver conexão/i)).toBeTruthy();
    expect(screen.getByText(/nunca é gravada na máquina/i)).toBeTruthy();
  });

  it("o passo das pastas não abre em erro", async () => {
    // Perguntar as pastas ao Agente e um POST — a rota manda um comando pelo
    // canal ate o computador — e o middleware da sessao publica recusa. O
    // assistente abria com o passo 2 em vermelho e o passo 6 pedindo "escolha
    // ao menos uma pasta" a quem nao tinha como escolher nenhuma. As pastas
    // vem das politicas em vigor, que as declaram.
    mockRotas(COM_POLITICA);

    render(<Politicas papel="leitor" somenteLeitura />);
    await userEvent.click(
      await screen.findByRole("button", { name: /ver como se configura/i }),
    );

    expect(await screen.findByText("/dados")).toBeTruthy();
    expect(screen.queryByText(/não tem pasta autorizada/i)).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("1 pasta");
    expect(screen.getByRole("status").textContent).toContain("PC da loja");
  });

  it("não oferece ativar, e diz por quê", async () => {
    mockRotas(COM_POLITICA);

    render(<Politicas papel="leitor" somenteLeitura />);
    await userEvent.click(
      await screen.findByRole("button", { name: /ver como se configura/i }),
    );

    expect(screen.queryByRole("button", { name: /ativar backup/i })).toBeNull();
    expect(screen.getByText(/não grava/i)).toBeTruthy();
  });

  it("fora da demonstração nada disto muda", async () => {
    // A trava e da sessao publica, e nao do papel: um `dono` de empresa de
    // verdade continua vendo a tela que sempre viu.
    mockRotas(COM_POLITICA);

    render(<Politicas papel="dono" />);
    await screen.findByText("Backup diario 03:00");

    expect(
      screen.getByRole("button", { name: /executar agora/i }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /^configurar backup$/i })).toBeTruthy();
  });
});
