"""
Task de Relatório de Vendas do AutoTarefas.

Gera relatórios de vendas a partir de dados estruturados:
    - SalesReportTask: Relatório completo de vendas
    - SalesData: Estrutura de dados de vendas

Uso:
    from autotarefas.tasks.sales_report import SalesReportTask, SalesData

    data = SalesData(
        period="Janeiro 2024",
        total_sales=150000.00,
        transactions=1250,
        products_sold={"Produto A": 500, "Produto B": 300}
    )

    task = SalesReportTask()
    result = task.run(sales_data=data, format="html")
"""

from __future__ import annotations

import csv
import html
import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from autotarefas.core.logger import logger
from autotarefas.tasks.reporter import ReporterTask, ReportMetadata
from autotarefas.utils.format_utils import brl, parse_iso_dt, safe_float, safe_int
from autotarefas.utils.helpers import safe_path

# =============================================================================
# Helpers internos (somente o que é realmente específico desta task)
# =============================================================================


def _top_n(mapping: dict[str, int], n: int = 10) -> list[tuple[str, int]]:
    """
    Retorna o top N itens de um dict por valor (desc).

    Args:
        mapping: Dicionário base (ex: produto -> quantidade)
        n: Quantidade de itens a retornar

    Returns:
        Lista de tuplas (chave, valor), ordenada desc
    """
    return sorted(mapping.items(), key=lambda x: x[1], reverse=True)[:n]


# =============================================================================
# Models
# =============================================================================


@dataclass(slots=True)
class SalesItem:
    """
    Item de venda individual.

    Attributes:
        product: Nome do produto
        quantity: Quantidade vendida
        unit_price: Preço unitário
        total: Valor total (quantity * unit_price)
        category: Categoria do produto
        date: Data da venda
    """

    product: str
    quantity: int
    unit_price: float
    total: float = 0.0
    category: str = ""
    date: datetime | None = None

    def __post_init__(self) -> None:
        """Garante cálculo do total quando não informado."""
        if self.total <= 0:
            self.total = float(self.quantity) * float(self.unit_price)

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa o item.

        Returns:
            Dicionário serializável (JSON-friendly)
        """
        return {
            "product": self.product,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total": self.total,
            "category": self.category,
            "date": self.date.isoformat() if self.date else None,
        }


@dataclass(slots=True)
class SalesData:
    """
    Dados consolidados de vendas.

    Attributes:
        period: Período do relatório (ex: "Janeiro 2024")
        total_sales: Valor total de vendas
        transactions: Número de transações
        items: Lista de itens vendidos
        products_sold: Resumo por produto
        categories: Resumo por categoria (valor total)
        best_seller: Produto mais vendido
        average_ticket: Ticket médio
    """

    period: str
    total_sales: float = 0.0
    transactions: int = 0
    items: list[SalesItem] = field(default_factory=list)
    products_sold: dict[str, int] = field(default_factory=dict)
    categories: dict[str, float] = field(default_factory=dict)
    best_seller: str = ""
    average_ticket: float = 0.0

    def __post_init__(self) -> None:
        """Calcula métricas derivadas após inicialização."""
        self.recompute()

    def recompute(self) -> None:
        """
        Recalcula métricas derivadas a partir de items/products_sold/categories.

        Observação:
            - Mantém consistência quando total_sales/transactions não vierem preenchidos
            - Evita duplicação de cálculos (ticket médio, best_seller)
        """
        # Se tiver items, completa dados faltantes
        if self.items:
            if self.transactions <= 0:
                self.transactions = len(self.items)

            if self.total_sales <= 0:
                self.total_sales = sum(i.total for i in self.items)

            if not self.products_sold:
                agg: dict[str, int] = {}
                for it in self.items:
                    agg[it.product] = agg.get(it.product, 0) + it.quantity
                self.products_sold = agg

            if not self.categories:
                cat: dict[str, float] = {}
                for it in self.items:
                    if it.category:
                        cat[it.category] = cat.get(it.category, 0.0) + it.total
                self.categories = cat

        # best_seller
        if self.products_sold:
            self.best_seller = max(self.products_sold.items(), key=lambda kv: kv[1])[0]
        else:
            self.best_seller = ""

        # ticket médio
        self.average_ticket = (
            (self.total_sales / self.transactions) if self.transactions > 0 else 0.0
        )

    @classmethod
    def from_csv(cls, file_path: str | Path, period: str = "") -> SalesData:
        """
        Cria SalesData a partir de arquivo CSV.

        Espera colunas: product, quantity, unit_price, category (opcional), date (opcional)

        Args:
            file_path: Caminho do arquivo CSV
            period: Período do relatório

        Returns:
            SalesData com os dados do CSV

        Raises:
            FileNotFoundError: Se o arquivo não existir
            ValueError: Se o CSV não contiver as colunas obrigatórias
        """
        path = safe_path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"CSV não encontrado: {path}")

        items: list[SalesItem] = []

        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)

            required = {"product", "quantity", "unit_price"}
            if reader.fieldnames is None or not required.issubset(
                set(reader.fieldnames)
            ):
                raise ValueError(
                    f"CSV inválido. Colunas obrigatórias: {sorted(required)}. Encontradas: {reader.fieldnames}"
                )

            for idx, row in enumerate(reader, start=2):  # 1 = header
                try:
                    product = (row.get("product") or "").strip() or "Unknown"
                    quantity = safe_int(row.get("quantity"))
                    unit_price = safe_float(row.get("unit_price"))
                    category = (row.get("category") or "").strip()
                    date = parse_iso_dt(row.get("date"))

                    if quantity <= 0 or unit_price < 0:
                        logger.warning(
                            "[sales_report] Linha %s ignorada (quantity/unit_price inválidos)",
                            idx,
                        )
                        continue

                    items.append(
                        SalesItem(
                            product=product,
                            quantity=quantity,
                            unit_price=unit_price,
                            category=category,
                            date=date,
                        )
                    )
                except Exception as e:
                    logger.warning("[sales_report] Erro na linha %s: %s", idx, e)

        return cls(
            period=period or "Período não especificado",
            transactions=len(items),
            items=items,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa dados consolidados para uso em relatórios.

        Returns:
            Dicionário com campos e valores formatados
        """
        return {
            "period": self.period,
            "total_sales": self.total_sales,
            "total_sales_formatted": brl(self.total_sales),
            "transactions": self.transactions,
            "average_ticket": self.average_ticket,
            "average_ticket_formatted": brl(self.average_ticket),
            "best_seller": self.best_seller,
            "products_sold": self.products_sold,
            "categories": self.categories,
            "items_count": len(self.items),
        }


# =============================================================================
# Task
# =============================================================================


class SalesReportTask(ReporterTask):
    """
    Task para geração de relatório de vendas.

    Gera relatórios detalhados de vendas com:
        - Resumo do período
        - Métricas principais (total, ticket médio, transações)
        - Top produtos
        - Vendas por categoria
    """

    @property
    def report_name(self) -> str:
        """Nome interno do relatório (usado em caminhos/ids)."""
        return "sales"

    @property
    def report_title(self) -> str:
        """Título exibido do relatório."""
        return "Relatório de Vendas"

    def generate_data(
        self,
        sales_data: SalesData | None = None,
        csv_file: str | Path | None = None,
        period: str = "",
        top_n: int = 10,
        include_items: bool = True,
        items_limit: int = 50,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """
        Gera dados do relatório de vendas.

        Args:
            sales_data: Dados de vendas (SalesData)
            csv_file: Arquivo CSV com dados de vendas
            period: Período do relatório
            top_n: Quantidade de produtos para ranking
            include_items: Se inclui itens detalhados
            items_limit: Limite de itens detalhados
            **_kwargs: Parâmetros adicionais ignorados

        Returns:
            Dicionário com dados formatados para o relatório
        """
        if sales_data is not None:
            data = sales_data
        elif csv_file is not None:
            data = SalesData.from_csv(csv_file, period=period)
        else:
            data = SalesData(
                period=period or datetime.now().strftime("%B %Y"),
                total_sales=0.0,
                transactions=0,
            )

        # ✅ Não chama método “privado”; usa recompute() público
        data.recompute()

        report_data: dict[str, Any] = {
            "resumo": {
                "Período": data.period,
                "Total de Vendas": brl(data.total_sales),
                "Transações": data.transactions,
                "Ticket Médio": brl(data.average_ticket),
            },
            "metricas": {
                "total_sales": data.total_sales,
                "transactions": data.transactions,
                "average_ticket": data.average_ticket,
                "items_count": len(data.items),
                "products_count": len(data.products_sold),
                "categories_count": len(data.categories),
            },
            "analise": {
                "Produto Mais Vendido": data.best_seller or "N/A",
                "Total de Produtos Diferentes": len(data.products_sold),
                "Total de Categorias": len(data.categories),
            },
        }

        if data.products_sold:
            ranked = _top_n(data.products_sold, n=max(1, int(top_n)))
            report_data["top_produtos"] = [
                {"produto": p, "quantidade": q} for p, q in ranked
            ]

        if data.categories:
            cats_sorted = sorted(
                data.categories.items(), key=lambda x: x[1], reverse=True
            )
            report_data["categorias"] = [
                {"categoria": c, "valor": v, "valor_formatado": brl(v)}
                for c, v in cats_sorted
            ]

        if include_items and data.items:
            limit = max(0, int(items_limit))
            report_data["itens"] = [item.to_dict() for item in data.items[:limit]]

        return report_data

    def format_html(self, data: dict[str, Any], metadata: ReportMetadata) -> str:
        """
        Formatação HTML personalizada para relatório de vendas.

        Args:
            data: Dados do relatório (generate_data)
            metadata: Metadados do relatório

        Returns:
            HTML completo (string)
        """
        resumo = data.get("resumo", {})
        metricas = data.get("metricas", {})
        top_produtos = data.get("top_produtos", [])
        categorias = data.get("categorias", [])
        analise = data.get("analise", {})

        title = html.escape(metadata.title)
        period = html.escape(str(resumo.get("Período", "N/A")))
        generated_at = html.escape(metadata.generated_at.strftime("%d/%m/%Y às %H:%M"))

        total_vendas = html.escape(str(resumo.get("Total de Vendas", brl(0.0))))
        ticket_medio = html.escape(str(resumo.get("Ticket Médio", brl(0.0))))
        transactions = int(metricas.get("transactions", 0) or 0)
        items_count = int(metricas.get("items_count", 0) or 0)

        # Mantive o teu HTML (bem caprichado). Se quiser, dá para extrair o CSS para template.
        html_out = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      padding: 20px;
    }}
    .container {{ max-width: 1000px; margin: 0 auto; }}
    .header {{
      background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    .header h1 {{ color: #333; margin-bottom: 8px; }}
    .header .meta {{ color: #666; font-size: 0.9em; }}
    .cards {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px; margin-bottom: 20px;
    }}
    .card {{
      background: white; border-radius: 12px; padding: 20px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    .card .label {{ color: #666; font-size: 0.85em; margin-bottom: 4px; }}
    .card .value {{ font-size: 1.5em; font-weight: bold; color: #333; }}
    .card.highlight {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
    .card.highlight .label, .card.highlight .value {{ color: white; }}
    .section {{
      background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    .section h2 {{
      color: #333; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #667eea;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
    th {{ background: #f8f9fa; font-weight: 600; color: #333; }}
    tr:hover {{ background: #f8f9fa; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📊 {title}</h1>
      <p class="meta">
        Período: <strong>{period}</strong> |
        Gerado em: {generated_at}
      </p>
    </div>

    <div class="cards">
      <div class="card highlight">
        <div class="label">Total de Vendas</div>
        <div class="value">{total_vendas}</div>
      </div>
      <div class="card">
        <div class="label">Transações</div>
        <div class="value">{transactions:,}</div>
      </div>
      <div class="card">
        <div class="label">Ticket Médio</div>
        <div class="value">{ticket_medio}</div>
      </div>
      <div class="card">
        <div class="label">Itens</div>
        <div class="value">{items_count:,}</div>
      </div>
    </div>
"""

        if top_produtos:
            html_out += """
    <div class="section">
      <h2>🏆 Top Produtos</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Produto</th>
            <th>Quantidade</th>
          </tr>
        </thead>
        <tbody>
"""
            for i, row in enumerate(top_produtos, 1):
                produto = html.escape(str(row.get("produto", "")))
                qtd = html.escape(str(row.get("quantidade", "")))
                html_out += f"""
          <tr>
            <td>{i}</td>
            <td>{produto}</td>
            <td>{qtd}</td>
          </tr>
"""
            html_out += """
        </tbody>
      </table>
    </div>
"""

        if categorias:
            html_out += """
    <div class="section">
      <h2>🧩 Vendas por Categoria</h2>
      <table>
        <thead>
          <tr>
            <th>Categoria</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
"""
            for row in categorias:
                cat = html.escape(str(row.get("categoria", "")))
                val = html.escape(str(row.get("valor_formatado", "")))
                html_out += f"""
          <tr>
            <td>{cat}</td>
            <td>{val}</td>
          </tr>
"""
            html_out += """
        </tbody>
      </table>
    </div>
"""

        if analise:
            html_out += """
    <div class="section">
      <h2>📈 Análise</h2>
      <table>
        <tbody>
"""
            for key, value in analise.items():
                k = html.escape(str(key))
                v = html.escape(str(value))
                html_out += f"""
          <tr>
            <td><strong>{k}</strong></td>
            <td>{v}</td>
          </tr>
"""
            html_out += """
        </tbody>
      </table>
    </div>
"""

        html_out += """
  </div>
</body>
</html>"""

        return html_out

    def format_csv(self, data: dict[str, Any], metadata: ReportMetadata) -> str:
        """
        Formatação CSV para relatório de vendas.

        Args:
            data: Dados do relatório (generate_data)
            metadata: Metadados do relatório

        Returns:
            Conteúdo CSV (string)
        """
        output = io.StringIO(newline="")
        writer = csv.writer(output)

        writer.writerow(["Relatório de Vendas"])
        writer.writerow(["Gerado em", metadata.generated_at.isoformat()])
        writer.writerow([])

        writer.writerow(["=== RESUMO ==="])
        resumo = data.get("resumo", {})
        for key, value in resumo.items():
            writer.writerow([key, value])
        writer.writerow([])

        top_produtos = data.get("top_produtos", [])
        if top_produtos:
            writer.writerow(["=== TOP PRODUTOS ==="])
            writer.writerow(["Produto", "Quantidade"])
            for row in top_produtos:
                writer.writerow([row.get("produto", ""), row.get("quantidade", "")])
            writer.writerow([])

        categorias = data.get("categorias", [])
        if categorias:
            writer.writerow(["=== VENDAS POR CATEGORIA ==="])
            writer.writerow(["Categoria", "Valor"])
            for row in categorias:
                writer.writerow(
                    [row.get("categoria", ""), row.get("valor_formatado", "")]
                )
            writer.writerow([])

        itens = data.get("itens", [])
        if itens:
            writer.writerow(["=== ITENS DETALHADOS ==="])
            writer.writerow(
                ["Produto", "Quantidade", "Preço Unit.", "Total", "Categoria", "Data"]
            )
            for item in itens:
                writer.writerow(
                    [
                        item.get("product", ""),
                        item.get("quantity", 0),
                        item.get("unit_price", 0),
                        item.get("total", 0),
                        item.get("category", ""),
                        item.get("date", ""),
                    ]
                )

        return output.getvalue()


__all__ = [
    "SalesItem",
    "SalesData",
    "SalesReportTask",
]
