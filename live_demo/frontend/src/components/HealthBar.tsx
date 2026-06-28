import type { Health } from "../lib/api";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-dim">
        {label}
      </span>
      <span className="font-mono text-sm text-text-muted">{value}</span>
    </div>
  );
}

export default function HealthBar({ health }: { health: Health }) {
  const mock = health.demo_servers[0];
  const mockAlive = mock?.alive ?? false;

  return (
    <div className="flex flex-wrap items-center gap-x-8 gap-y-4 rounded-lg border border-line bg-surface/60 px-5 py-4 backdrop-blur">
      <div className="flex items-center gap-2.5">
        <span
          className={`h-2 w-2 rounded-full ${mockAlive ? "animate-pulse-dot bg-ok" : "bg-text-dim"}`}
          aria-hidden
        />
        <span className="font-mono text-sm text-text">
          {mockAlive ? "operacional" : "offline"}
        </span>
      </div>
      <Metric label="versão" value={`v${health.version}`} />
      <Metric
        label="automações"
        value={`${health.active_automations.length} ativas`}
      />
      <Metric
        label="execução"
        value={`${health.limits.run_timeout_s}s · ${health.limits.max_concurrent_runs} simultâneas`}
      />
      <Metric
        label="rede do robô"
        value={health.limits.egress_lockdown ? "isolada" : "aberta"}
      />
      <Metric label="sandbox" value={mockAlive ? `mock :${mock?.port}` : "—"} />
    </div>
  );
}
