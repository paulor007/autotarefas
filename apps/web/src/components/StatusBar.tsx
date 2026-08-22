import {
  CheckCircle2,
  Clock,
  Layers,
  Lock,
  Server,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import type { Health } from "../lib/api";

type Tone = "ok" | "cyan" | "signal";
interface Chip {
  icon: LucideIcon;
  title: string;
  desc: string;
  tone: Tone;
}

const TONE: Record<Tone, string> = {
  ok: "bg-ok/10 text-ok",
  cyan: "bg-cyan/10 text-cyan",
  signal: "bg-signal/10 text-signal",
};

function buildChips(health: Health | null): Chip[] {
  const mock = health?.demo_servers[0];
  return [
    {
      icon: CheckCircle2,
      title: "API Online",
      desc: health ? "Endpoints ativos" : "Conectando…",
      tone: "ok",
    },
    {
      icon: Server,
      title: "Mock Interno",
      desc: mock ? (mock.alive ? `Porta ${mock.port} ativa` : "Offline") : "—",
      tone: "cyan",
    },
    {
      icon: Layers,
      title: health
        ? `${health.active_automations.length} Automações`
        : "Automações",
      desc: "Prontas para uso",
      tone: "signal",
    },
    {
      icon: Lock,
      title: "Rede Isolada",
      desc: health?.limits.egress_lockdown ? "Egress bloqueado" : "—",
      tone: "ok",
    },
    {
      icon: Clock,
      title: "Timeout",
      desc: health ? `${health.limits.run_timeout_s}s por execução` : "—",
      tone: "cyan",
    },
    {
      icon: ShieldCheck,
      title: "Sandbox Seguro",
      desc: health
        ? `${health.limits.max_concurrent_runs} execuções simultâneas`
        : "—",
      tone: "ok",
    },
  ];
}

export default function StatusBar({ health }: { health: Health | null }) {
  const chips = buildChips(health);
  return (
    <section className="border-b border-white/[0.06] py-8">
      <div className="container-page">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {chips.map((chip) => (
            <div
              key={chip.title}
              className="flex items-center gap-3 rounded-[10px] border border-white/[0.06] bg-surface p-3.5 transition-colors hover:border-white/[0.12]"
            >
              <div
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${TONE[chip.tone]}`}
              >
                <chip.icon className="h-4 w-4" />
              </div>
              <div className="flex min-w-0 flex-col">
                <span className="truncate text-[0.82rem] font-semibold text-fg">
                  {chip.title}
                </span>
                <span className="truncate text-[0.68rem] text-muted">
                  {chip.desc}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
