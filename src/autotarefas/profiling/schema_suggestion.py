"""
Schema sugerido: transforma o que foi OBSERVADO num ponto de partida.

O `analisar` descobre a estrutura de uma planilha. Este modulo pega essa
descoberta e escreve um `schema_sugerido.yaml` que o cliente pode ajustar
e usar direto no `validate` — fechando o ciclo:

    analisar planilha.xlsx --schema-sugerido schema.yaml
    # o cliente edita duas linhas
    validate planilha.xlsx --schema schema.yaml

A FRONTEIRA desta subetapa, e a razao de ela existir com cuidado:

    o schema sugerido contem apenas o que foi OBSERVADO.
    Ele NUNCA inventa uma regra de negocio.

Concretamente, o gerador JAMAIS emite:

  - required     -> o leitor nao sabe se um campo e obrigatorio. Uma coluna
                    100% preenchida na amostra pode aceitar vazios amanha.
  - unique       -> repeticao pode ser 100% legitima (o caso multi-item:
                    um codigo de venda que se repete por linha de produto).
                    Sugerir unique produziria uma regra que marca dados
                    validos como erro.
  - min_value /  -> o MENOR e o MAIOR valor observados sao um retrato da
    max_value       amostra, nao um limite. Se a planilha de hoje vai de 30
                    a 750, isso nao quer dizer que 800 e invalido amanha.
  - enum_values  -> "so apareceram 3 categorias" nao e "so podem existir 3".
  - validator_br -> exige saber que a coluna e CPF/CNPJ. O leitor nao sabe
                    dominio — ele ve "identificador com mascara", nao "CPF".
  - format       -> idem: "parece e-mail" e dominio, nao estrutura.

Tudo o que o gerador NAO pode afirmar vira COMENTARIO no YAML — visivel,
explicado, pronto para o cliente descomentar se ele (que conhece o
negocio) decidir que a regra vale. A decisao e sempre dele.

Este modulo e agnostico de dominio: ha um teste que percorre a AST e falha
o build se um termo como cpf/sku/venda aparecer no codigo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from autotarefas.profiling.result import ColumnProfile, ProfileResult

#: Nome do artefato. Fixo — o usuario escolhe a PASTA, nunca o nome
#: (nome controlado pelo usuario e vetor de path traversal).
SCHEMA_SUGGESTION_NAME = "schema_sugerido.yaml"

#: Mapeamento leitor -> tipo do schema. Isto e o UNICO julgamento que o
#: gerador faz, e e um julgamento sobre ESTRUTURA (que tipo o dado tem),
#: nunca sobre regra (o que o dado deveria ser).
_TYPE_MAP: dict[str, str] = {
    "inteiro": "int",
    "decimal": "float",
    "moeda": "float",
    "percentual": "float",
    "data": "date",
    "data_hora": "date",
    "booleano": "bool",
    "identificador": "str",
    "texto": "str",
    "misto": "str",
    "erro": "str",
    "vazio": "str",
}


def _schema_type(col: ColumnProfile) -> str:
    """
    Tipo do schema correspondente ao tipo observado pelo leitor.

    Ate a 1.5.1 havia aqui uma excecao: uma data brasileira era rebaixada
    para `str`, porque o validador so entendia ISO e o schema gerado
    quebraria no `validate`. Com a interpretacao de datas unificada em
    `core.dates`, a excecao deixou de existir — e manter a nota antiga
    seria pior que nao ter nota, porque ela hoje seria falsa.
    """
    return _TYPE_MAP.get(col.inferred_type, "str")


def _yaml_key(name: str) -> str:
    """
    Escreve o nome da coluna com seguranca no YAML.

    Nomes com acento, espaco ou dois-pontos ("Valor Unitário", "Data: dia")
    precisam de aspas para o YAML nao quebrar. Aspas simples, com escape das
    proprias aspas simples (a convencao YAML: '' dentro de '...').
    """
    if name and all(c.isalnum() or c in "_-" for c in name) and not name[0].isdigit():
        return name
    escapado = name.replace("'", "''")
    return f"'{escapado}'"


def _column_block(col: ColumnProfile) -> list[str]:
    """
    O bloco YAML de uma coluna: o que se AFIRMA + o que se SUGERE em comentario.

    As linhas ativas (sem '#') sao so tipo e nome — o unico compromisso que
    o leitor pode assumir. Todo o resto e comentario com a razao ao lado.
    """
    linhas = [
        f"  - name: {_yaml_key(col.name)}",
        f"    type: {_schema_type(col)}",
    ]

    # required: SUGESTAO em comentario, com o dado observado ao lado.
    if col.fill_rate >= 1.0:
        linhas.append(
            "    # required: true       "
            "# 100% preenchida na amostra — descomente se o campo for obrigatorio"
        )
    else:
        linhas.append(
            f"    # required: true       "
            f"# atencao: {col.fill_rate:.0%} preenchida na amostra "
            f"({col.empty_count} vazios)"
        )

    # unique: so LEMBRA a possibilidade quando a amostra e toda distinta —
    # e mesmo assim deixa claro que repeticao pode ser legitima.
    if col.uniqueness_rate >= 1.0 and col.filled_count > 1:
        linhas.append(
            "    # unique: true         "
            "# todos os valores da amostra sao distintos — confirme que repeticao seria erro"
        )

    # min_length: so para texto, e so como lembrete.
    if col.inferred_type in ("texto", "identificador"):
        linhas.append("    # min_length: 1        # descomente para exigir texto nao vazio")

    # intervalo observado: vai como INFORMACAO comentada, nunca como regra.
    if col.minimum is not None and col.maximum is not None:
        linhas.append(
            f"    # observado na amostra: de {col.minimum} ate {col.maximum} "
            f"(NAO e um limite — adicione min_value/max_value so se for uma regra)"
        )

    # deixa registrado o que o leitor achou, para o cliente decidir.
    for obs in col.observations:
        linhas.append(f"    # nota: {obs}")

    return linhas


def build_schema_suggestion(perfil: ProfileResult) -> str:
    """
    Monta o texto do `schema_sugerido.yaml` a partir do perfil.

    O YAML resultante e valido para o `validate` como esta: ele contem
    apenas `columns` com `name` e `type`. Todas as regras de negocio sao
    comentarios que o cliente pode ativar.
    """
    cabecalho = [
        "# Schema SUGERIDO pelo AutoTarefas a partir da analise da planilha.",
        "#",
        "# As linhas ativas contem apenas o que foi OBSERVADO: o nome e o tipo",
        "# de cada coluna. Nenhuma regra de negocio foi inventada.",
        "#",
        "# As linhas comentadas (#) sao SUGESTOES, com o dado observado ao lado.",
        "# Voce, que conhece o negocio, decide quais fazem sentido e descomenta.",
        "#",
        "# Como usar depois de ajustar:",
        "#   autotarefas validate SUA_PLANILHA --schema este_arquivo.yaml",
        "",
        "columns:",
    ]

    blocos: list[str] = []
    for col in perfil.columns:
        blocos.extend(_column_block(col))

    rodape: list[str] = []
    if perfil.duplicate_row_count > 0:
        rodape.extend(
            [
                "",
                "# Foram observadas linhas completamente identicas na amostra"
                f" ({perfil.duplicate_row_count}).",
                "# Se linhas 100% duplicadas nunca deveriam existir, descomente:",
                "# detect_duplicate_rows: true",
            ]
        )

    return "\n".join([*cabecalho, *blocos, *rodape]) + "\n"


def write_schema_suggestion(perfil: ProfileResult, destino: Path) -> Path:
    """Escreve o schema sugerido. Cria o diretorio se preciso."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(build_schema_suggestion(perfil), encoding="utf-8")
    return destino


__all__ = [
    "SCHEMA_SUGGESTION_NAME",
    "build_schema_suggestion",
    "write_schema_suggestion",
]
