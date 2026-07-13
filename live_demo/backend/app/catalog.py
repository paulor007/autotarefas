"""Catalogo curado das automacoes expostas na demo ao vivo.

So as automacoes listadas aqui podem ser executadas, e sempre com parametros
controlados pelo servidor (allowlist). O visitante nunca informa caminho de disco
nem comando: no maximo envia arquivos (upload). O mapeamento para o comando real
fica fora deste payload publico (entra na Live-2) e nunca e exposto pela API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

UploadKind = Literal["none", "csv", "spreadsheet", "folder"]
OutputKind = Literal["report", "file", "zip", "html"]

# (key, titulo, resumo) — espelha as categorias do runs.json
CATEGORIES: tuple[tuple[str, str, str], ...] = (
    (
        "validacao",
        "Validação & Qualidade",
        "Confere planilhas contra um schema antes de qualquer processamento.",
    ),
    ("arquivos", "Backup & Organizacao", "Compacta com hash e organiza arquivos por tipo."),
    ("integracao", "Integração de API", "Envia, coleta e sincroniza dados com APIs REST."),
    ("notificacoes", "Notificações", "Dispara e-mails e mensagens a partir de uma planilha."),
    (
        "scraping",
        "Web Scraping",
        "Extrai dados de páginas, inclusive renderizadas por JavaScript.",
    ),
    ("rpa", "RPA (Navegador)", "Automatiza um navegador real para preencher formulários."),
    ("auditoria", "Auditoria", "Relatórios e painel da trilha append-only."),
)


@dataclass(frozen=True)
class Automation:
    """Metadados publicos de uma automacao curada (seguros para a API)."""

    id: str
    category: str
    title: str
    subtitle: str
    description: str
    requires_browser: bool
    upload: UploadKind
    upload_hint: str
    output: OutputKind
    #: Automacoes sem upload rodam contra um servico de demonstracao interno.
    #: Estes dois campos descrevem ESSA origem para o visitante (o front
    #: renderiza o bloco "Origem da demonstracao" sempre que preenchidos).
    #: Vazios = sem bloco de origem (o front cai na mensagem generica).
    source_label: str = ""
    source_detail: str = ""


AUTOMATIONS: tuple[Automation, ...] = (
    Automation(
        "validate",
        "validacao",
        "Auditoria de planilha",
        "Valida, limpa e separa antes de importar",
        "Confere uma planilha de clientes, leads ou contatos, aponta os erros, "
        "normaliza o que é seguro (nada de dado inventado) e separa registros "
        "válidos dos inválidos - o pré-voo antes de qualquer importação.",
        False,
        "spreadsheet",
        "Envie um arquivo .csv ou .xlsx (ou use o de exemplo).",
        "report",
    ),
    Automation(
        "backup",
        "arquivos",
        "Backup compactado",
        "ZIP com hash SHA-256",
        "Compacta os arquivos enviados num .zip e calcula o hash SHA-256 do pacote.",
        False,
        "folder",
        "Envie uma pasta ou vários arquivos (ou use os de exemplo).",
        "zip",
    ),
    Automation(
        "organize",
        "arquivos",
        "Organizar por tipo",
        "Separa em subpastas",
        "Classifica os arquivos enviados em subpastas por tipo (imagens, vídeos, documentos...).",
        False,
        "folder",
        "Envie a pasta bagunçada (ou use a de exemplo).",
        "zip",
    ),
    Automation(
        "send_api",
        "integracao",
        "Cadastro automático via planilha",
        "Envia dados validados para um sistema com relatório de envio",
        "Cadastre clientes, leads ou contatos a partir de uma planilha validada. "
        "O AutoTarefas envia cada registro para um sistema via API, mostra o que "
        "foi cadastrado, o que falhou e por que - evitando digitação manual, "
        "duplicidade e retrabalho.",
        False,
        "spreadsheet",
        "Envie .csv ou .xlsx - ideal: o registros_validos.csv da Auditoria de planilha.",
        "report",
    ),
    Automation(
        "extract_api",
        "integracao",
        "Exportação automática de dados",
        "De um sistema via API para uma planilha pronta para uso",
        "Puxe dados que estão em um sistema - clientes, pedidos ou produtos - "
        "direto pela API e receba uma planilha organizada, pronta para análise, "
        "conferência, backup ou para alimentar a Auditoria de planilha.",
        False,
        "none",
        # Sem upload: a "entrada" e a origem dos dados. O texto abaixo explica
        # de onde eles vem na demo — e o que seria diferente num uso real.
        "O AutoTarefas consulta a API página por página e transforma os registros "
        "que ela devolve em CSV e Excel. Não existe planilha pronta para baixar: "
        "a planilha é montada na hora. Em uma integração real, a origem seria a "
        "API autorizada do sistema da empresa.",
        "report",
        source_label="Catálogo empresarial simulado",
        source_detail="47 produtos · 5 páginas · API interna segura",
    ),
    Automation(
        "sync_api",
        "integracao",
        "Sincronizar API",
        "Origem -> destino",
        "Sincroniza registros de uma API de origem para uma de destino (mocks internos).",
        False,
        "none",
        "",
        "report",
    ),
    Automation(
        "send_email",
        "notificacoes",
        "Disparar e-mails",
        "SMTP de demonstração",
        "Gera um e-mail por linha do CSV e entrega num servidor SMTP de teste "
        "(nada sai para fora).",
        False,
        "csv",
        "Envie um .csv (ou use o de exemplo).",
        "report",
    ),
    Automation(
        "send_telegram",
        "notificacoes",
        "Mensagens no Telegram",
        "Bot de demonstração",
        "Monta uma mensagem por contato e envia para um bot mock (nada sai para fora).",
        False,
        "none",
        "",
        "report",
    ),
    Automation(
        "extract_web",
        "scraping",
        "Scraping de catálogo",
        "HTML paginado",
        "Percorre um catálogo HTML paginado (mock interno) e extrai os produtos para CSV.",
        False,
        "none",
        "",
        "file",
    ),
    Automation(
        "extract_web_js",
        "scraping",
        "Scraping com JavaScript",
        "Via navegador",
        "Extrai um catálogo renderizado por JavaScript usando um navegador real (Chromium).",
        True,
        "none",
        "",
        "file",
    ),
    Automation(
        "rpa_cadastro",
        "rpa",
        "RPA de cadastro",
        "Preenche formulário",
        "Abre um navegador real e preenche um formulário de cadastro a partir do CSV.",
        True,
        "none",
        "",
        "report",
    ),
    Automation(
        "report",
        "auditoria",
        "Relatório de auditoria",
        "Resumo do trilho",
        "Resume as execuções registradas na trilha de auditoria append-only.",
        False,
        "none",
        "",
        "report",
    ),
    Automation(
        "dashboard",
        "auditoria",
        "Painel de auditoria",
        "HTML autocontido",
        "Gera um painel HTML com as execuções registradas na trilha.",
        False,
        "none",
        "",
        "html",
    ),
)

_BY_ID: dict[str, Automation] = {a.id: a for a in AUTOMATIONS}


def get(automation_id: str) -> Automation | None:
    """Retorna a automacao pelo id, ou None se nao estiver na allowlist."""
    return _BY_ID.get(automation_id)


def public_catalog() -> dict[str, Any]:
    """Payload seguro para a API publica (sem comandos nem caminhos)."""
    categories = [
        {"key": key, "title": title, "summary": summary} for (key, title, summary) in CATEGORIES
    ]
    automations = [
        {
            "id": a.id,
            "category": a.category,
            "title": a.title,
            "subtitle": a.subtitle,
            "description": a.description,
            "requires_browser": a.requires_browser,
            "upload": a.upload,
            "upload_hint": a.upload_hint,
            "output": a.output,
            "source_label": a.source_label,
            "source_detail": a.source_detail,
        }
        for a in AUTOMATIONS
    ]
    return {"categories": categories, "automations": automations}
