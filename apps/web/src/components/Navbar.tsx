import { CheckSquare } from "lucide-react";

/**
 * O que a barra oferece como caminho.
 *
 * "Terminal" e "Artefatos" saíram. Eles continuam na página — quem rola chega
 * neles, e para quem sabe o que são eles mostram bem o que o motor faz. O que
 * não podiam continuar sendo é **caminho oferecido**: ninguém precisa de um
 * terminal para entender um backup automático, e uma barra que sugere isso
 * transforma um produto em ferramenta de linha de comando na cabeça de quem
 * está decidindo se olha ou fecha.
 */
const LINKS: [string, string][] = [
  ["Backup automático", "#produto"],
  ["Catálogo", "#catalogo"],
  ["Execução", "#execucao"],
];

export default function Navbar({ online }: { online: boolean }) {
  return (
    <nav className="fixed inset-x-0 top-0 z-50 border-b border-white/[0.06] bg-ink/85 backdrop-blur-xl">
      <div className="container-page flex h-16 items-center justify-between">
        <a href="#topo" className="flex items-center gap-2.5">
          <CheckSquare className="h-5 w-5 text-signal" />
          <span className="text-[1.05rem] font-bold tracking-tight">
            AutoTarefas
          </span>
          <span className="rounded bg-signal px-1.5 py-0.5 text-[0.6rem] font-bold tracking-wider text-black">
            LIVE
          </span>
        </a>

        <div className="hidden items-center gap-8 md:flex">
          {LINKS.map(([label, href]) => (
            <a
              key={href}
              href={href}
              className="text-sm font-medium text-muted transition-colors hover:text-fg"
            >
              {label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${online ? "animate-pulse-dot bg-ok" : "bg-muted"}`}
              aria-hidden
            />
            <span className="hidden text-xs font-medium text-muted sm:inline">
              {online ? "Sistema operacional" : "Conectando…"}
            </span>
          </div>
          {/* Havia um "Entrar" aqui, e ele levava ao MESMO lugar que o
              "Acessar" do Backup automatico logo abaixo — dois caminhos para a
              mesma coisa, e um deles com nome de login numa porta que nao pede
              credencial nenhuma.

              "Entrar" volta a fazer sentido quando existir autenticacao de
              cliente: ai sao duas coisas diferentes, "acessar o ambiente
              publico" e "entrar na minha organizacao". Ate la, o botao
              prometia uma porta que nao existe. */}
        </div>
      </div>
    </nav>
  );
}
