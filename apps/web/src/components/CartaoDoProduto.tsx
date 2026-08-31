import { ArrowRight, HardDriveDownload } from "lucide-react";

import { cliqueDeNavegacao, enderecoDa } from "../lib/rotas";

/** Direto para os backups, e não para a porta da frente do produto. */
const PARA_OS_BACKUPS = enderecoDa("backups");

/**
 * A porta do Backup automático, na primeira dobra da página.
 *
 * Ela existe porque o caminho até aqui estava errado. O card do catálogo
 * chamado "backup" é a ferramenta de upload — junta os arquivos que você
 * entrega num .zip com comprovante, uma vez. Quem clicava nele esperando o
 * produto caía num formulário de envio, e de lá em terminal e artefatos: um
 * percurso técnico que não responde nenhuma das perguntas que a pessoa tinha.
 *
 * As duas coisas continuam existindo, e são diferentes:
 *
 * - **Backup automático** protege pastas no horário, sozinho, com o navegador
 *   fechado. É o produto, e mora em `/app`.
 * - **Compactar arquivos com comprovante** é uma ferramenta avulsa, que roda
 *   uma vez sobre o que você enviar.
 *
 * O nome perdeu o "verificável". A característica não sumiu — ela aparece na
 * descrição e, com muito mais força, dentro do produto: cada execução mostra
 * o SHA-256 do pacote e se a cópia foi conferida no destino. Um adjetivo no
 * título prometia o que a tela precisa provar.
 */
export default function CartaoDoProduto() {
  return (
    <section id="produto" className="container-page pb-4 pt-10">
      <div className="rounded-2xl border border-signal/25 bg-signal/[0.05] p-6 sm:p-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex max-w-2xl gap-4">
            <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-signal/15 text-signal sm:flex">
              <HardDriveDownload className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight text-fg">
                Backup automático
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                Protege pastas automaticamente nos horários definidos, verifica
                a integridade das cópias e mantém histórico, retenção e
                evidências das execuções.
              </p>
            </div>
          </div>

          <a
            href={PARA_OS_BACKUPS}
            onClick={cliqueDeNavegacao(PARA_OS_BACKUPS)}
            className="inline-flex shrink-0 items-center gap-2 self-start rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-black transition-opacity hover:opacity-90 sm:self-auto"
          >
            Acessar
            <ArrowRight className="h-4 w-4" aria-hidden />
          </a>
        </div>
      </div>
    </section>
  );
}
