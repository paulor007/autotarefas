import {
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
  Sparkles,
  Table2,
} from "lucide-react";

import type { ValidationReport } from "../lib/api";

// Rotulos legiveis para as categorias de erro (espelha o XLSX do backend).
const CATEGORY_LABELS: Record<string, string> = {
  cpf: "CPF inválido",
  cnpj: "CNPJ inválido",
  email: "E-mail inválido",
  telefone: "Telefone inválido",
  obrigatorio: "Campo obrigatório vazio",
  duplicado: "Duplicados",
  tamanho: "Texto muito curto",
  intervalo: "Fora do intervalo",
  enum: "Valor não permitido",
  tipo: "Tipo inválido",
  formato: "Formato inválido",
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
    <div className="flex items-center gap-3 rounded-xl border border-white/6 bg-surface p-4">
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

export default function ValidationSummary({
  report,
}: {
  report: ValidationReport;
}) {
  const categories = Object.entries(report.issues_by_category);
  const clean = report.total_invalid === 0;

  return (
    <div className="mx-auto mb-8 max-w-3xl space-y-4">
      {/* Banner: normalizacao segura (regra de ouro da Auditoria) */}
      <div className="flex items-start gap-3 rounded-xl border border-cyan/20 bg-cyan/6 px-4 py-3">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
        <p className="text-sm text-muted">
          <span className="font-semibold text-fg">Normalização segura:</span> o
          sistema não inventa dados — só padroniza o que é determinístico
          (espaços extras, e-mail em minúsculo, máscara de CPF/telefone quando
          os dígitos já são válidos). Todo ajuste fica registrado na aba
          Auditoria da planilha.
        </p>
      </div>

      {/* Cards do resumo */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard
          label="Registros"
          value={report.rows}
          tone="neutral"
          icon={Table2}
        />
        <SummaryCard
          label="Válidos"
          value={report.total_valid}
          tone="ok"
          icon={CheckCircle2}
        />
        <SummaryCard
          label="Inválidos"
          value={report.total_invalid}
          tone="danger"
          icon={AlertTriangle}
        />
        <SummaryCard
          label="Normalizados"
          value={report.total_cleaned}
          tone="signal"
          icon={Sparkles}
        />
      </div>

      {/* Erros por categoria (ou estado positivo) */}
      {clean ? (
        <div className="flex items-center gap-2 rounded-xl border border-ok/20 bg-ok/6 px-4 py-3 text-sm">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-ok" />
          <span className="text-fg">
            Nenhum registro inválido — base pronta para o próximo passo
            (importar, enviar via API…).
          </span>
        </div>
      ) : (
        categories.length > 0 && (
          <div className="rounded-xl border border-white/6 bg-surface p-4">
            <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
              Problemas por categoria
            </div>
            <div className="flex flex-wrap gap-2">
              {categories.map(([key, count]) => (
                <span
                  key={key}
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/8 bg-ink px-3 py-1 text-xs text-fg"
                >
                  {CATEGORY_LABELS[key] ?? key}
                  <span className="font-mono font-semibold text-signal">
                    {count}
                  </span>
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-muted">
              Os motivos linha a linha estão em{" "}
              <span className="font-mono text-fg">registros_invalidos.csv</span>{" "}
              e na planilha validada.
            </p>
          </div>
        )
      )}
    </div>
  );
}
