import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Send,
  Table2,
} from "lucide-react";

import type { ImportReport } from "../lib/api";

// Rotulos legiveis das categorias de falha (espelha o XLSX do backend).
const CATEGORY_LABELS: Record<string, string> = {
  validacao: "Dados inválidos",
  duplicado: "Já cadastrado",
  rate_limit: "Limite de requisições",
  temporario: "Instabilidade",
  conexao: "Conexão",
  outro: "Outros",
};

interface CardProps {
  label: string;
  value: number;
  tone: "neutral" | "ok" | "danger" | "signal";
  icon: typeof Table2;
}

const TONE = {
  neutral: { text: "text-fg", chip: "bg-white/[0.04] text-muted" },
  ok: { text: "text-ok", chip: "bg-ok/10 text-ok" },
  danger: { text: "text-danger", chip: "bg-danger/10 text-danger" },
  signal: { text: "text-signal", chip: "bg-signal/10 text-signal" },
} as const;

function SummaryCard({ label, value, tone, icon: Icon }: CardProps) {
  const t = TONE[tone];
  return (
    <div className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-surface p-4">
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md ${t.chip}`}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <div className={`text-2xl font-bold leading-none ${t.text}`}>
          {value}
        </div>
        <div className="mt-1 text-[0.7rem] uppercase tracking-wider text-muted">
          {label}
        </div>
      </div>
    </div>
  );
}

export default function ImportSummary({ report }: { report: ImportReport }) {
  const categories = Object.entries(report.falhas_por_categoria);
  const semFalhas = report.falhas === 0;

  return (
    <div className="mx-auto mb-8 max-w-3xl space-y-4">
      {/* Banner: reenvio seguro por idempotencia (regra de ouro do Cadastro) */}
      <div className="flex items-start gap-3 rounded-xl border border-cyan/20 bg-cyan/[0.06] px-4 py-3">
        <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
        <p className="text-sm text-muted">
          <span className="font-semibold text-fg">Reenvio seguro:</span> o{" "}
          <span className="font-mono text-fg">registros_falhos.csv</span> pode
          ser corrigido e reenviado direto — a chave de idempotência de cada
          registro garante que quem já entrou não é cadastrado em duplicidade.
        </p>
      </div>

      {/* Cards do resumo */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard
          label="Registros"
          value={report.total}
          tone="neutral"
          icon={Table2}
        />
        <SummaryCard
          label="Enviados"
          value={report.enviados}
          tone="ok"
          icon={CheckCircle2}
        />
        <SummaryCard
          label="Falhos"
          value={report.falhas}
          tone="danger"
          icon={AlertTriangle}
        />
        <SummaryCard
          label="Reenviáveis"
          value={report.reenviaveis}
          tone="signal"
          icon={RefreshCw}
        />
      </div>

      {/* Falhas por categoria (ou estado positivo) */}
      {semFalhas ? (
        <div className="flex items-center gap-2 rounded-xl border border-ok/20 bg-ok/[0.06] px-4 py-3 text-sm">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-ok" />
          <span className="text-fg">
            Todos os registros foram cadastrados com sucesso — nenhuma falha.
          </span>
        </div>
      ) : (
        categories.length > 0 && (
          <div className="rounded-xl border border-white/[0.06] bg-surface p-4">
            <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
              Falhas por categoria
            </div>
            <div className="flex flex-wrap gap-2">
              {categories.map(([key, count]) => (
                <span
                  key={key}
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-ink px-3 py-1 text-xs text-fg"
                >
                  {CATEGORY_LABELS[key] ?? key}
                  <span className="font-mono font-semibold text-signal">
                    {count}
                  </span>
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-muted">
              Cada linha enviada com o ID criado está em{" "}
              <span className="font-mono text-fg">registros_enviados.csv</span>;
              os motivos das falhas, em{" "}
              <span className="font-mono text-fg">registros_falhos.csv</span>.
            </p>
          </div>
        )
      )}

      {/* Rodape: ponte de volta ao inicio do pipeline */}
      <div className="flex items-start gap-2 text-xs text-muted">
        <Send className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" />
        <span>
          Enviou uma base ainda não validada? Rode a{" "}
          <span className="text-fg">Auditoria de planilha</span> antes para
          reduzir as falhas de dados inválidos.
        </span>
      </div>
    </div>
  );
}
