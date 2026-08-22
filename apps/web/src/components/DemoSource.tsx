import { Database, Lock, ShieldCheck } from "lucide-react";

import type { Automation } from "../lib/api";

/**
 * Bloco de origem das automacoes SEM upload.
 *
 * Estas automacoes nao recebem arquivo: elas rodam contra um servico de
 * demonstracao interno. Este componente responde, para o visitante, as
 * quatro perguntas obvias: de onde vem os dados, quantos sao, como sao
 * acessados e por que nao existe upload.
 *
 * E orientado a DADOS, nao a id: o que aparece vem do proprio catalogo do
 * backend (`upload_hint`, `source_label`, `source_detail`). Uma automacao
 * nova sem upload passa a exibir o bloco apenas preenchendo esses campos —
 * sem nenhuma condicional por id aqui.
 */
export default function DemoSource({ automation }: { automation: Automation }) {
  const temOrigem = automation.source_label.length > 0;

  return (
    <div className="space-y-3 rounded-lg border border-cyan/20 bg-cyan/6 px-4 py-3">
      {/* Explicacao: o que vai acontecer e o que seria diferente num uso real */}
      <div className="flex items-start gap-3">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-fg">
            Demonstração segura
          </div>
          <p className="mt-1 text-sm text-muted">
            {automation.upload_hint ||
              "Esta automação não recebe arquivo: ela roda no sandbox contra os serviços de demonstração internos."}
          </p>
        </div>
      </div>

      {/* Origem: de onde vem os dados, quantos sao e como sao acessados */}
      {temOrigem && (
        <div className="flex items-start gap-3 rounded-lg border border-white/6 bg-ink px-3 py-2.5">
          <Database className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <div className="min-w-0">
            <div className="text-[0.68rem] font-semibold uppercase tracking-wider text-muted">
              Origem da demonstração
            </div>
            <div className="mt-0.5 text-sm font-medium text-fg">
              {automation.source_label}
            </div>
            <div className="text-xs text-muted">{automation.source_detail}</div>
          </div>
        </div>
      )}

      {/* Limite de seguranca do Live */}
      <div className="flex items-center gap-2 text-xs text-muted">
        <Lock className="h-3.5 w-3.5 shrink-0" />
        <span>
          No Live, URLs externas e credenciais reais não são permitidas.
        </span>
      </div>
    </div>
  );
}
