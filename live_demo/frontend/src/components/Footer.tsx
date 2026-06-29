import { CheckSquare } from "lucide-react";

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.06] py-8">
      <div className="container-page flex flex-col items-center justify-between gap-4 sm:flex-row">
        <div className="flex items-center gap-2 text-sm font-medium text-muted">
          <CheckSquare className="h-4 w-4 text-signal" />
          <span>AutoTarefas · Live System</span>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-muted">
          <span>Execução real em sandbox seguro</span>
          <span className="opacity-30">|</span>
          <span>Ambiente isolado</span>
          <span className="opacity-30">|</span>
          <span>Sem instalação</span>
        </div>
      </div>
    </footer>
  );
}
