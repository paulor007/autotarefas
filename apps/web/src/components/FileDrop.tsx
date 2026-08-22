import { useRef, useState, type DragEvent } from "react";
import { Upload, X } from "lucide-react";

// Extensoes/limites espelham o backend (allowed_upload_extensions, max 10MB, 50 arquivos).
const ALLOWED = [
  ".csv",
  ".tsv",
  ".txt",
  ".pdf",
  ".docx",
  ".xlsx",
  ".jpg",
  ".jpeg",
  ".png",
  ".json",
  ".yaml",
  ".yml",
];
const MAX_BYTES = 10 * 1024 * 1024;
const MAX_FILES = 50;

function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  accept: string;
  multiple: boolean;
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}

export default function FileDrop({
  accept,
  multiple,
  files,
  onChange,
  disabled = false,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [warn, setWarn] = useState<string | null>(null);

  const acceptExts = accept
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);

  const validate = (incoming: File[]): File[] => {
    const ok: File[] = [];
    for (const file of incoming) {
      const ext = extOf(file.name);
      if (acceptExts.length > 0 && !acceptExts.includes(ext)) {
        setWarn(`Arquivo "${file.name}" não é do tipo aceito (${accept}).`);
        continue;
      }
      if (!ALLOWED.includes(ext)) {
        setWarn(`Extensão ${ext || "?"} não permitida.`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        setWarn(`"${file.name}" excede 10 MB.`);
        continue;
      }
      ok.push(file);
    }
    return ok;
  };

  const merge = (incoming: File[]) => {
    setWarn(null);
    const valid = validate(incoming);
    if (valid.length === 0) return;
    const next = multiple
      ? [...files, ...valid].slice(0, MAX_FILES)
      : [valid[0]];
    onChange(next);
  };

  const openPicker = () => {
    if (!disabled) inputRef.current?.click();
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    merge(Array.from(e.dataTransfer.files));
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label="Selecionar arquivo de entrada"
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openPicker();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          disabled
            ? "cursor-not-allowed border-white/6 opacity-50"
            : dragging
              ? "cursor-pointer border-signal/60 bg-signal/4"
              : "cursor-pointer border-white/10 hover:border-signal/40"
        }`}
      >
        <Upload className="h-6 w-6 text-muted" />
        <span className="text-sm text-fg">
          Arraste {multiple ? "arquivos" : "um arquivo"} ou clique para
          selecionar
        </span>
        <span className="text-xs text-muted">
          Aceita {accept} · até 10 MB cada
        </span>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          hidden
          disabled={disabled}
          onChange={(e) => {
            merge(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
      </div>

      {warn && <p className="mt-2 text-xs text-danger">{warn}</p>}

      {files.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {files.map((file, i) => (
            <li
              key={`${file.name}-${i}`}
              className="flex items-center justify-between rounded-md border border-white/6 bg-ink px-3 py-2"
            >
              <span className="truncate font-mono text-xs text-fg">
                {file.name}
              </span>
              <span className="ml-3 flex shrink-0 items-center gap-3">
                <span className="text-[0.68rem] text-muted">
                  {humanSize(file.size)}
                </span>
                {!disabled && (
                  <button
                    type="button"
                    onClick={() =>
                      onChange(files.filter((_, idx) => idx !== i))
                    }
                    aria-label={`Remover ${file.name}`}
                    className="text-muted transition-colors hover:text-danger"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
