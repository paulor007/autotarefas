import { useCallback, useEffect, useRef, useState } from "react";

import type { TerminalLine } from "../components/TerminalView";
import {
  getResult,
  runAutomation,
  type Automation,
  type RunResult,
} from "../lib/api";
import { classifyLine } from "../lib/terminal";

export type RunStatus =
  | "idle"
  | "starting"
  | "running"
  | "done"
  | "timeout"
  | "error";

interface RunOptions {
  files?: File[];
  useSample?: boolean;
}

export interface UseExecution {
  status: RunStatus;
  lines: TerminalLine[];
  result: RunResult | null;
  error: string | null;
  token: string | null;
  run: (automation: Automation, opts: RunOptions) => Promise<void>;
  reset: () => void;
}

export function useExecution(): UseExecution {
  const [status, setStatus] = useState<RunStatus>("idle");
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const doneRef = useRef(false);

  const closeStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  const reset = useCallback(() => {
    closeStream();
    doneRef.current = false;
    setStatus("idle");
    setLines([]);
    setResult(null);
    setError(null);
    setToken(null);
  }, [closeStream]);

  // Fecha o stream se o componente desmontar no meio de uma execucao.
  useEffect(() => closeStream, [closeStream]);

  const run = useCallback(
    async (automation: Automation, opts: RunOptions) => {
      closeStream();
      doneRef.current = false;
      setLines([]);
      setResult(null);
      setError(null);
      setStatus("starting");

      let started;
      try {
        started = await runAutomation(automation.id, opts);
      } catch (e: unknown) {
        setError(
          e instanceof Error ? e.message : "Falha ao iniciar a execução.",
        );
        setStatus("error");
        return;
      }

      setToken(started.token);
      setStatus("running");

      const es = new EventSource(started.stream_url);
      esRef.current = es;

      es.onmessage = (event) => {
        setLines((prev) => [...prev, classifyLine(event.data)]);
      };

      es.addEventListener("done", (event) => {
        doneRef.current = true;
        try {
          const data = JSON.parse((event as MessageEvent).data) as RunResult;
          setResult(data);
          setStatus(data.exit_code === 124 ? "timeout" : "done");
        } catch {
          setStatus("done");
        }
        closeStream();
      });

      es.addEventListener("timeout", (event) => {
        doneRef.current = true;
        try {
          const data = JSON.parse((event as MessageEvent).data) as RunResult;
          setResult(data);
        } catch {
          /* evento sem payload */
        }
        setLines((prev) => [
          ...prev,
          {
            kind: "error",
            text: "[ERROR] Tempo de execução excedido (timeout).",
          },
        ]);
        setStatus("timeout");
        closeStream();
      });

      es.onerror = () => {
        if (doneRef.current) {
          return; // ja terminou normalmente; ignora o fechamento do stream
        }
        closeStream();
        // Fallback: o job pode ter concluido mesmo com o stream caindo.
        getResult(started.token)
          .then((data) => {
            setResult(data);
            setStatus(data.exit_code === 124 ? "timeout" : "done");
          })
          .catch(() => {
            setError("Conexão com o stream interrompida.");
            setStatus("error");
          });
      };
    },
    [closeStream],
  );

  return { status, lines, result, error, token, run, reset };
}
