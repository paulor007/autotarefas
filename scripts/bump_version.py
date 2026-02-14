#!/usr/bin/env python3
"""
Script para atualização de versão do AutoTarefas.

Este script atualiza a versão em todos os arquivos relevantes do projeto,
seguindo o padrão Semantic Versioning (SemVer).

Uso:
    python scripts/bump_version.py [major|minor|patch|prerelease|build]
    python scripts/bump_version.py --set 1.2.3
    python scripts/bump_version.py --set 1.2.3-beta.1

Exemplos:
    # Incrementar patch: 1.0.0 -> 1.0.1
    python scripts/bump_version.py patch

    # Incrementar minor: 1.0.1 -> 1.1.0
    python scripts/bump_version.py minor

    # Incrementar major: 1.1.0 -> 2.0.0
    python scripts/bump_version.py major

    # Definir versão específica
    python scripts/bump_version.py --set 2.0.0-alpha.1

    # Adicionar prerelease: 1.0.0 -> 1.0.0-alpha.1
    python scripts/bump_version.py prerelease --pre alpha

    # Incrementar prerelease: 1.0.0-alpha.1 -> 1.0.0-alpha.2
    python scripts/bump_version.py prerelease
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# Diretório raiz do projeto
ROOT_DIR = Path(__file__).parent.parent


class Version(NamedTuple):
    """Representação de uma versão SemVer."""

    major: int
    minor: int
    patch: int
    prerelease: str = ""
    build: str = ""

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """Parse uma string de versão para um objeto Version."""
        # Regex para SemVer completo
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$"
        match = re.match(pattern, version_str.strip())
        if not match:
            raise ValueError(f"Versão inválida: {version_str}")

        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4) or "",
            build=match.group(5) or "",
        )

    def bump_major(self) -> "Version":
        """Incrementa a versão major."""
        return Version(self.major + 1, 0, 0)

    def bump_minor(self) -> "Version":
        """Incrementa a versão minor."""
        return Version(self.major, self.minor + 1, 0)

    def bump_patch(self) -> "Version":
        """Incrementa a versão patch."""
        return Version(self.major, self.minor, self.patch + 1)

    def bump_prerelease(self, pre_type: str = "") -> "Version":
        """Incrementa ou define a versão prerelease."""
        if not self.prerelease:
            # Se não tem prerelease, inicia com tipo.1
            pre_type = pre_type or "alpha"
            return Version(self.major, self.minor, self.patch, f"{pre_type}.1")

        # Se já tem prerelease, incrementa o número
        parts = self.prerelease.rsplit(".", 1)
        if len(parts) == 2 and parts[1].isdigit():
            new_pre = f"{parts[0]}.{int(parts[1]) + 1}"
        else:
            new_pre = f"{self.prerelease}.1"

        return Version(self.major, self.minor, self.patch, new_pre)

    def set_build(self, build: str = "") -> "Version":
        """Define os metadados de build."""
        build = build or datetime.now().strftime("%Y%m%d")
        return Version(self.major, self.minor, self.patch, self.prerelease, build)

    def release(self) -> "Version":
        """Remove prerelease e build para versão de release."""
        return Version(self.major, self.minor, self.patch)


def get_current_version() -> Version:
    """Lê a versão atual do arquivo _version.py."""
    version_file = ROOT_DIR / "src" / "autotarefas" / "_version.py"

    if not version_file.exists():
        raise FileNotFoundError(f"Arquivo de versão não encontrado: {version_file}")

    content = version_file.read_text()

    # Extrai os valores de VersionInfo com validação
    major_match = re.search(r"major=(\d+)", content)
    minor_match = re.search(r"minor=(\d+)", content)
    patch_match = re.search(r"patch=(\d+)", content)

    if not major_match or not minor_match or not patch_match:
        raise ValueError(f"Formato de versão inválido em {version_file}")

    major = int(major_match.group(1))
    minor = int(minor_match.group(1))
    patch = int(patch_match.group(1))

    pre_match = re.search(r'prerelease="([^"]*)"', content)
    prerelease = pre_match.group(1) if pre_match else ""

    build_match = re.search(r'build="([^"]*)"', content)
    build = build_match.group(1) if build_match else ""

    return Version(major, minor, patch, prerelease, build)


def update_version_file(version: Version) -> None:
    """Atualiza o arquivo _version.py com a nova versão."""
    version_file = ROOT_DIR / "src" / "autotarefas" / "_version.py"
    content = version_file.read_text()

    # Atualiza os valores no VersionInfo
    content = re.sub(r"major=\d+", f"major={version.major}", content)
    content = re.sub(r"minor=\d+", f"minor={version.minor}", content)
    content = re.sub(r"patch=\d+", f"patch={version.patch}", content)
    content = re.sub(
        r'prerelease="[^"]*"', f'prerelease="{version.prerelease}"', content
    )
    content = re.sub(r'build="[^"]*"', f'build="{version.build}"', content)

    # Atualiza a data de release
    today = datetime.now().strftime("%Y-%m-%d")
    content = re.sub(r'RELEASE_DATE = "[^"]*"', f'RELEASE_DATE = "{today}"', content)

    version_file.write_text(content)
    print(f"✓ Atualizado: {version_file}")


def update_pyproject_toml(version: Version) -> None:
    """Atualiza o pyproject.toml com a nova versão."""
    pyproject_file = ROOT_DIR / "pyproject.toml"
    content = pyproject_file.read_text()

    # Atualiza a linha de versão (apenas major.minor.patch para pyproject)
    version_str = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        # PEP 440 usa formato diferente para prereleases
        # alpha -> a, beta -> b, rc -> rc
        pre = version.prerelease.replace("alpha", "a").replace("beta", "b")
        pre = re.sub(r"\.(\d+)$", r"\1", pre)  # Remove ponto antes do número
        version_str += pre

    content = re.sub(
        r'version = "[^"]*"',
        f'version = "{version_str}"',
        content,
        count=1,  # Apenas a primeira ocorrência
    )

    pyproject_file.write_text(content)
    print(f"✓ Atualizado: {pyproject_file}")


def update_changelog(version: Version) -> None:
    """Atualiza o CHANGELOG.md com a nova versão."""
    changelog_file = ROOT_DIR / "CHANGELOG.md"
    if not changelog_file.exists():
        print("⚠ CHANGELOG.md não encontrado, pulando...")
        return

    content = changelog_file.read_text()
    today = datetime.now().strftime("%Y-%m-%d")

    # Se há uma seção [Não Lançado], adiciona a nova versão abaixo dela
    if "[Não Lançado]" in content:
        new_section = f"\n## [{version}] - {today}\n"
        content = content.replace(
            "[Não Lançado]",
            f"[Não Lançado]\n\n---{new_section}",
            1,
        )
        changelog_file.write_text(content)
        print(f"✓ Atualizado: {changelog_file}")


def create_git_tag(version: Version, push: bool = False) -> None:
    """Cria uma tag git para a versão."""
    tag_name = f"v{version}"

    try:
        # Verifica se a tag já existe
        result = subprocess.run(
            ["git", "tag", "-l", tag_name],
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
        )
        if tag_name in result.stdout:
            print(f"⚠ Tag {tag_name} já existe")
            return

        # Cria a tag
        subprocess.run(
            ["git", "tag", "-a", tag_name, "-m", f"Release {version}"],
            check=True,
            cwd=ROOT_DIR,
        )
        print(f"✓ Tag criada: {tag_name}")

        if push:
            subprocess.run(
                ["git", "push", "origin", tag_name],
                check=True,
                cwd=ROOT_DIR,
            )
            print(f"✓ Tag enviada para origin: {tag_name}")

    except subprocess.CalledProcessError as e:
        print(f"⚠ Erro ao criar tag: {e}")
    except FileNotFoundError:
        print("⚠ Git não encontrado, pulando criação de tag...")


def main() -> int:
    """Função principal do script."""
    parser = argparse.ArgumentParser(
        description="Atualiza a versão do AutoTarefas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "bump",
        nargs="?",
        choices=["major", "minor", "patch", "prerelease", "build", "release"],
        help="Tipo de incremento de versão",
    )
    parser.add_argument(
        "--set",
        dest="set_version",
        metavar="VERSION",
        help="Define uma versão específica (ex: 1.2.3 ou 1.2.3-beta.1)",
    )
    parser.add_argument(
        "--pre",
        default="alpha",
        help="Tipo de prerelease (alpha, beta, rc). Padrão: alpha",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Cria uma tag git para a versão",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Envia a tag para o repositório remoto",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem modificar arquivos",
    )

    args = parser.parse_args()

    # Obtém a versão atual
    try:
        current = get_current_version()
    except FileNotFoundError as e:
        print(f"✗ Erro: {e}")
        return 1

    print(f"Versão atual: {current}")

    # Determina a nova versão
    if args.set_version:
        try:
            new_version = Version.parse(args.set_version)
        except ValueError as e:
            print(f"✗ Erro: {e}")
            return 1
    elif args.bump:
        if args.bump == "major":
            new_version = current.bump_major()
        elif args.bump == "minor":
            new_version = current.bump_minor()
        elif args.bump == "patch":
            new_version = current.bump_patch()
        elif args.bump == "prerelease":
            new_version = current.bump_prerelease(args.pre)
        elif args.bump == "build":
            new_version = current.set_build()
        elif args.bump == "release":
            new_version = current.release()
        else:
            parser.print_help()
            return 1
    else:
        parser.print_help()
        return 1

    print(f"Nova versão:  {new_version}")

    if args.dry_run:
        print("\n[dry-run] Nenhum arquivo foi modificado")
        return 0

    # Atualiza os arquivos
    print("\nAtualizando arquivos...")
    update_version_file(new_version)
    update_pyproject_toml(new_version)

    # Atualiza changelog apenas para releases (sem prerelease)
    if not new_version.prerelease:
        update_changelog(new_version)

    # Cria tag se solicitado
    if args.tag:
        create_git_tag(new_version, push=args.push)

    print(f"\n✓ Versão atualizada para {new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
