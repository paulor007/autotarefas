"""
Task de Relatórios do AutoTarefas.

Fornece base para geração de relatórios:
    - ReporterTask: Classe base para relatórios
    - ReportFormat: Formatos suportados (TXT, HTML, JSON, CSV, MD)
    - ReportMetadata: Metadados (título, data/hora, app/env, etc.)

Uso:
    from autotarefas.tasks import ReporterTask, ReportFormat

    class MeuRelatorio(ReporterTask):
        @property
        def report_name(self) -> str:
            return "meu_relatorio"

        @property
        def report_title(self) -> str:
            return "Meu Relatório"

        def generate_data(self, **kwargs) -> dict:
            return {"dados": "..."}

    task = MeuRelatorio()
    result = task.run(output_path="relatorio.html", format="html")
"""

from __future__ import annotations

import csv
import html
import io
import json
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from autotarefas.config import settings
from autotarefas.core.base import BaseTask, TaskResult
from autotarefas.core.logger import logger
from autotarefas.utils.helpers import safe_path, sanitize_filename

# =============================================================================
# Helpers internos
# =============================================================================


def _utc_now() -> datetime:
    """
    Retorna datetime timezone-aware em UTC.

    Motivo:
        - Evita misturar datetime naive com timezone-aware no projeto.
        - Facilita logs e auditoria (principalmente quando o app roda em servidores).
    """
    return datetime.now(UTC)


def _json_default(obj: Any) -> str:
    """
    Serializer padrão para JSON (fallback seguro).

    Motivo:
        - JSON padrão não serializa datetime/Path/Enum.
        - Mantém a geração do relatório sempre funcionando, mesmo com tipos “ricos”.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Enum):
        return str(obj.value)
    return str(obj)


def _is_list_of_dicts(value: Any) -> bool:
    """
    Retorna True se value parece ser uma lista de dicts (dados tabulares).

    Motivo:
        - CSV faz mais sentido quando existe uma “tabela” (lista de registros).
    """
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(x, dict) for x in value)
    )


def _escape_md(text: str) -> str:
    """
    Escapes simples para Markdown (principalmente em tabelas).

    Motivo:
        - Evita quebrar tabela Markdown quando houver pipe ("|") no conteúdo.
    """
    return text.replace("|", r"\|")


def _flatten_for_txt(data: dict[str, Any], indent: int = 0) -> list[str]:
    """
    Transforma dict aninhado em linhas TXT legíveis.

    Motivo:
        - Mantém um fallback TXT simples e previsível para qualquer estrutura.
    """
    lines: list[str] = []
    pad = " " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.extend(_flatten_for_txt(value, indent=indent + 2))
        elif isinstance(value, list):
            lines.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{pad}  -")
                    lines.extend(_flatten_for_txt(item, indent=indent + 4))
                else:
                    lines.append(f"{pad}  - {item}")
        else:
            lines.append(f"{pad}{key}: {value}")

    return lines


def _render_html_value(value: Any) -> str:
    """
    Renderiza um valor em HTML com escaping seguro.

    Motivo:
        - Evita HTML injection
        - Permite dict/list renderizarem como tabela/lista (boa legibilidade)
    """
    if isinstance(value, dict):
        rows: list[str] = []
        for k, v in value.items():
            rows.append(
                f"<tr><td><strong>{html.escape(str(k))}</strong></td><td>{_render_html_value(v)}</td></tr>"
            )
        return "<table>" + "".join(rows) + "</table>"

    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.append(f"<li>{_render_html_value(item)}</li>")
        return "<ul>" + "".join(items) + "</ul>"

    return html.escape(str(value))


# =============================================================================
# Enum / Metadata
# =============================================================================


class ReportFormat(Enum):
    """
    Formatos de relatório suportados.

    Valores:
        TXT: Texto simples
        HTML: HTML formatado
        JSON: JSON estruturado
        CSV: CSV para dados tabulares
        MD: Markdown
    """

    TXT = "txt"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    MD = "md"

    @property
    def extension(self) -> str:
        """
        Extensão do formato (inclui ponto).

        Returns:
            Ex: ".txt", ".html", ".json"
        """
        return f".{self.value}"

    @classmethod
    def from_string(cls, value: str) -> ReportFormat:
        """
        Cria ReportFormat a partir de string.

        Aceita:
            - "txt", "html", etc.
            - ".txt", ".html", etc.

        Args:
            value: Formato em string

        Returns:
            ReportFormat

        Raises:
            ValueError: Se formato não for suportado
        """
        raw = (value or "").strip().lower()
        raw = raw[1:] if raw.startswith(".") else raw

        for fmt in cls:
            if fmt.value == raw:
                return fmt

        raise ValueError(f"Formato não suportado: {value}")


@dataclass(slots=True)
class ReportMetadata:
    """
    Metadados do relatório.

    Attributes:
        title: Título do relatório
        description: Descrição
        generated_at: Data/hora de geração
        generated_by: Quem gerou (task name)
        version: Versão do relatório
        format: Formato do relatório
        app_name: Nome do app (config)
        app_env: Ambiente (config)
    """

    title: str
    description: str = ""
    generated_at: datetime = field(default_factory=_utc_now)  # ✅ trocado para UTC
    generated_by: str = "autotarefas"
    version: str = "1.0"
    format: ReportFormat = ReportFormat.TXT

    # Contexto útil em relatórios (ajuda debug e rastreabilidade).
    app_name: str = field(default_factory=lambda: settings.APP_NAME)
    app_env: str = field(default_factory=lambda: settings.APP_ENV)

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa metadados para dict.

        Returns:
            Dicionário serializável (JSON-friendly)
        """
        return {
            "title": self.title,
            "description": self.description,
            "generated_at": self.generated_at.isoformat(),
            "generated_by": self.generated_by,
            "version": self.version,
            "format": self.format.value,
            "app_name": self.app_name,
            "app_env": self.app_env,
        }


# =============================================================================
# Base Task
# =============================================================================


class ReporterTask(BaseTask):
    """
    Classe base abstrata para tasks de relatório.

    Subclasses devem implementar:
        - report_name: Nome do relatório
        - report_title: Título do relatório
        - generate_data(): Gera os dados do relatório

    Opcionalmente podem sobrescrever:
        - format_txt(): Formatação personalizada para TXT
        - format_html(): Formatação personalizada para HTML
        - format_csv(): Formatação personalizada para CSV
        - format_md(): Formatação personalizada para Markdown

    Exemplo:
        >>> class StatusReport(ReporterTask):
        ...     @property
        ...     def report_name(self) -> str:
        ...         return "status"
        ...
        ...     @property
        ...     def report_title(self) -> str:
        ...         return "Relatório de Status do Sistema"
        ...
        ...     def generate_data(self, **kwargs) -> dict[str, Any]:
        ...         return {"status": "ok", "uptime": "5 days"}
        >>>
        >>> task = StatusReport()
        >>> result = task.run(format="html")
    """

    @property
    def name(self) -> str:
        """
        Nome da task (usado em logs e metadados).

        Returns:
            String única do tipo "reporter-<report_name>"
        """
        return f"reporter-{self.report_name}"

    @property
    def description(self) -> str:
        """
        Descrição curta da task.

        Returns:
            Texto descritivo para UI/logs
        """
        return f"Gera relatório: {self.report_title}"

    @property
    @abstractmethod
    def report_name(self) -> str:
        """Nome curto do relatório (para nome de arquivo)."""
        ...

    @property
    @abstractmethod
    def report_title(self) -> str:
        """Título do relatório."""
        ...

    @abstractmethod
    def generate_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Gera os dados do relatório.

        Este método deve ser implementado por cada tipo de relatório.

        Args:
            **kwargs: Parâmetros específicos do relatório

        Returns:
            Dicionário com os dados do relatório
        """
        ...

    def validate(self, **_kwargs: Any) -> tuple[bool, str]:
        """
        Valida configuração mínima do relatório.

        Returns:
            (ok, mensagem_erro)
        """
        if not (self.report_name or "").strip():
            return False, "report_name não pode ser vazio"
        if not (self.report_title or "").strip():
            return False, "report_title não pode ser vazio"
        return True, ""

    def execute(
        self,
        output_path: str | Path | None = None,
        format: str = "txt",
        save: bool = False,
        include_content: bool = True,
        **kwargs: Any,
    ) -> TaskResult:
        """
        Gera o relatório.

        Args:
            output_path: Caminho do arquivo de saída (opcional). Se for diretório, gera nome automático.
            format: Formato do relatório (txt, html, json, csv, md)
            save: Se True e output_path não for informado, salva no diretório padrão de relatórios
            include_content: Se deve incluir o conteúdo no payload do TaskResult
            **kwargs: Parâmetros para generate_data()

        Returns:
            TaskResult com o relatório gerado
        """
        started_at = _utc_now()  # ✅ padroniza em UTC

        try:
            report_format = ReportFormat.from_string(format)
        except ValueError as e:
            return TaskResult.failure(message=str(e), started_at=started_at)

        logger.info(
            "Gerando relatório '%s' em formato %s",
            self.report_name,
            report_format.value,
        )

        try:
            data = self.generate_data(**kwargs)

            metadata = ReportMetadata(
                title=self.report_title,
                generated_by=self.name,
                format=report_format,
            )

            content = self._format_report(data, metadata, report_format)

            output_file: Path | None = None
            if output_path is not None:
                output_file = self._save_report(content, output_path, report_format)
            elif save:
                # ✅ Se for salvar sem output_path, grava no diretório padrão de relatórios
                output_file = self._save_report(
                    content, settings.REPORTS_PATH, report_format
                )

            payload: dict[str, Any] = {
                "metadata": metadata.to_dict(),
                "output_file": str(output_file) if output_file else None,
                "format": report_format.value,
                "data": data,
            }
            if include_content:
                payload["content"] = content

            return TaskResult.success(
                message=f"Relatório '{self.report_title}' gerado com sucesso",
                data=payload,
                started_at=started_at,
            )

        except Exception as e:
            logger.exception("Erro ao gerar relatório: %s", e)
            return TaskResult.failure(
                message=f"Falha ao gerar relatório: {e}",
                error=e,
                started_at=started_at,
            )

    def _format_report(
        self,
        data: dict[str, Any],
        metadata: ReportMetadata,
        format: ReportFormat,
    ) -> str:
        """
        Formata o relatório no formato especificado.

        Args:
            data: Dados do relatório
            metadata: Metadados do relatório
            format: Formato alvo

        Returns:
            Conteúdo formatado (string)
        """
        formatters: dict[
            ReportFormat, Callable[[dict[str, Any], ReportMetadata], str]
        ] = {
            ReportFormat.TXT: self.format_txt,
            ReportFormat.HTML: self.format_html,
            ReportFormat.JSON: self.format_json,
            ReportFormat.CSV: self.format_csv,
            ReportFormat.MD: self.format_md,
        }

        formatter = formatters.get(format, self.format_txt)
        return formatter(data, metadata)

    # =============================================================================
    # Formatters (overrideables)
    # =============================================================================

    def format_txt(self, data: dict[str, Any], metadata: ReportMetadata) -> str:
        """
        Formata relatório como texto simples.

        Pode ser sobrescrito para formatação personalizada.

        Args:
            data: Dados do relatório
            metadata: Metadados do relatório

        Returns:
            Texto (string)
        """
        header = [
            "=" * 60,
            metadata.title.center(60),
            "=" * 60,
            "",
            f"Gerado em: {metadata.generated_at.strftime('%d/%m/%Y %H:%M:%S')} (UTC)",
            f"Gerado por: {metadata.generated_by}",
            f"App: {metadata.app_name} ({metadata.app_env})",
            "",
            "-" * 60,
            "",
        ]

        body = _flatten_for_txt(data)
        footer = ["", "-" * 60, "Fim do relatório"]
        return "\n".join(header + body + footer)

    def format_html(self, data: dict[str, Any], metadata: ReportMetadata) -> str:
        """
        Formata relatório como HTML.

        Pode ser sobrescrito para formatação personalizada.

        Args:
            data: Dados do relatório
            metadata: Metadados do relatório

        Returns:
            HTML completo (string)
        """
        title = html.escape(metadata.title)
        generated_at = html.escape(metadata.generated_at.strftime("%d/%m/%Y %H:%M:%S"))
        generated_by = html.escape(metadata.generated_by)
        app_line = html.escape(f"{metadata.app_name} ({metadata.app_env})")

        parts: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="pt-BR">',
            "<head>",
            '<meta charset="UTF-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f"<title>{title}</title>",
            """
<style>
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
  background: #f5f5f5;
}
.report {
  background: white;
  border-radius: 10px;
  padding: 24px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.08);
}
h1 { margin: 0 0 10px 0; color: #222; }
.meta { color: #555; font-size: 0.95em; margin-bottom: 18px; }
.section {
  margin: 14px 0;
  padding: 14px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #eee;
}
.section h3 { margin: 0 0 10px 0; color: #333; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; }
td, th { padding: 8px 10px; border-bottom: 1px solid #e6e6e6; vertical-align: top; }
td:first-child { width: 240px; color: #222; }
</style>
""",
            "</head>",
            "<body>",
            '<div class="report">',
            f"<h1>{title}</h1>",
            '<div class="meta">',
            f"Gerado em: {generated_at} (UTC)<br>",
            f"Por: {generated_by}<br>",
            f"App: {app_line}",
            "</div>",
        ]

        for key, value in data.items():
            parts.append('<div class="section">')
            parts.append(f"<h3>{html.escape(str(key))}</h3>")
            parts.append(_render_html_value(value))
            parts.append("</div>")

        parts.extend(["</div>", "</body>", "</html>"])
        return "\n".join(parts)

    def format_json(self, data: dict[str, Any], metadata: ReportMetadata) -> str:
        """
        Formata relatório como JSON.

        Args:
            data: Dados do relatório
            metadata: Metadados do relatório

        Returns:
            JSON (string)
        """
        report = {"metadata": metadata.to_dict(), "data": data}
        return json.dumps(report, indent=2, ensure_ascii=False, default=_json_default)

    def format_csv(self, data: dict[str, Any], metadata: ReportMetadata) -> str:
        """
        Formata relatório como CSV.

        Funciona melhor com dados tabulares (lista de dicts).

        Args:
            data: Dados do relatório
            metadata: Metadados do relatório

        Returns:
            CSV (string)
        """
        output = io.StringIO(newline="")
        writer_simple = csv.writer(output)

        # ✅ Procura a primeira lista tabular (lista de dicts)
        rows: list[dict[str, Any]] | None = None
        for _key, value in data.items():
            if _is_list_of_dicts(value):
                rows = value
                break

        if rows:
            # ✅ União de colunas mantendo ordem de descoberta
            columns: list[str] = []
            seen: set[str] = set()
            for row in rows:
                for col in row:
                    col_s = str(col)
                    if col_s not in seen:
                        seen.add(col_s)
                        columns.append(col_s)

            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()

            for row in rows:
                normalized: dict[str, Any] = {}
                for col in columns:
                    v = row.get(col)
                    if isinstance(v, (dict, list)):
                        v = json.dumps(v, ensure_ascii=False, default=_json_default)
                    normalized[col] = v
                writer.writerow(normalized)

            return output.getvalue()

        # ✅ fallback key/value (quando não houver dados tabulares)
        writer_simple.writerow(["Campo", "Valor"])
        writer_simple.writerow(["__title__", metadata.title])
        writer_simple.writerow(["__generated_at__", metadata.generated_at.isoformat()])
        writer_simple.writerow(["__generated_by__", metadata.generated_by])

        for key, value in data.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, default=_json_default)
            writer_simple.writerow([key, value])

        return output.getvalue()

    def format_md(self, data: dict[str, Any], metadata: ReportMetadata) -> str:
        """
        Formata relatório como Markdown.

        Args:
            data: Dados do relatório
            metadata: Metadados do relatório

        Returns:
            Markdown (string)
        """
        app_md = _escape_md(metadata.app_name)
        env_md = _escape_md(metadata.app_env)

        lines: list[str] = [
            f"# {_escape_md(metadata.title)}",
            "",
            f"**Gerado em:** {metadata.generated_at.strftime('%d/%m/%Y %H:%M:%S')} (UTC)  ",
            f"**Por:** {_escape_md(metadata.generated_by)}  ",
            f"**App:** {app_md} ({env_md})",
            "",
            "---",
            "",
        ]

        for key, value in data.items():
            lines.append(f"## {_escape_md(str(key))}")
            lines.append("")

            if isinstance(value, dict):
                lines.append("| Campo | Valor |")
                lines.append("|-------|-------|")
                for k, v in value.items():
                    lines.append(f"| {_escape_md(str(k))} | {_escape_md(str(v))} |")
                lines.append("")  # ✅ só uma linha em branco no final do bloco
                continue

            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            lines.append(
                                f"- **{_escape_md(str(k))}:** {_escape_md(str(v))}"
                            )
                    else:
                        lines.append(f"- {_escape_md(str(item))}")
                lines.append("")
                continue

            lines.append(_escape_md(str(value)))
            lines.append("")

        return "\n".join(lines)

    # =============================================================================
    # Save / Filename
    # =============================================================================

    def generate_filename(self, fmt: ReportFormat = ReportFormat.TXT) -> str:
        """
        Gera nome de arquivo único para o relatório.

        Args:
            fmt: Formato do relatório

        Returns:
            Nome do arquivo com timestamp e extensão do formato
        """
        timestamp = _utc_now().strftime("%Y%m%d_%H%M%S")
        name = sanitize_filename(self.report_name)
        return f"{name}_{timestamp}{fmt.extension}"

    def _save_report(
        self, content: str, output_path: str | Path, fmt: ReportFormat
    ) -> Path:
        """
        Salva o relatório em arquivo.

        Regras:
            - Se output_path for diretório, gera um filename automático.
            - Se output_path não tiver extensão, adiciona a extensão do formato.

        Args:
            content: Conteúdo do relatório
            output_path: Arquivo ou diretório de destino
            fmt: Formato do relatório

        Returns:
            Path do arquivo salvo
        """
        out = safe_path(output_path)

        # ✅ Se for diretório (ou existir como diretório), cria filename automaticamente
        if out.exists() and out.is_dir():
            out = out / self.generate_filename(fmt)

        # ✅ Se não tem sufixo, adiciona (evita "relatorio" sem extensão)
        if not out.suffix:
            out = out.with_suffix(fmt.extension)

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

        logger.info("Relatório salvo em: %s", out)
        return out


__all__ = [
    "ReportFormat",
    "ReportMetadata",
    "ReporterTask",
]
