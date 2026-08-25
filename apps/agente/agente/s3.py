"""Destino S3 compativel: envia o pacote para fora da empresa.

E o terceiro nivel da regra 3-2-1: uma copia **fora do predio**. Disco externo
protege contra o disco morrer; nao protege contra incendio, roubo do escritorio
ou ransomware que alcanca a midia conectada.

"S3 compativel", e nao "AWS": o mesmo protocolo atende Amazon S3, Backblaze B2,
Wasabi, Cloudflare R2, MinIO e o storage do provedor nacional. Amarrar num
fornecedor daria menos codigo hoje e uma migracao amanha.

Tres decisoes que valem a pena registrar:

1. **Envio em partes (multipart), sempre que o pacote for grande.** Um upload
   de 40 GB numa tacada morre no primeiro soluco de rede e recomeca do zero. Em
   partes, so a parte falha.
2. **Conferencia depois do envio.** O objeto e lido de volta e o SHA-256 e
   recalculado. O ETag do S3 nao serve: em envio multipart ele e o hash dos
   hashes das partes, e nao o hash do arquivo — comparar com ele daria falso
   negativo sempre.
3. **Credencial nunca fica gravada aqui.** Ela chega pelo canal autenticado,
   e usada, e some com o processo. O Agente nao grava chave de nuvem em disco.

Limite que precisa estar dito: validado contra servidor S3 compativel **local**
na suite. Isso prova o protocolo, nao a nuvem de ninguem. Nao ha homologacao
em nuvem real ate alguem apontar para um endpoint de verdade.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: O cliente do `boto3` nao tem tipo publicado sem os stubs do
#: `mypy_boto3_s3`, que sao um pacote a mais so para tipagem. `Any` aqui e
#: honesto: a checagem de verdade deste modulo esta nos testes, que falam com
#: um servidor S3 de verdade.
S3Client = Any

#: Tamanho de cada parte no envio multipart. 8 MB e o meio-termo comum: parte
#: pequena demais multiplica requisicoes; grande demais desperdica o reenvio.
PARTE = 8 * 1024 * 1024

#: A partir daqui vale a pena partir o envio.
LIMITE_MULTIPART = 16 * 1024 * 1024

#: Buffer da leitura na conferencia.
LEITURA = 1024 * 1024


class EnvioRecusado(Exception):
    """Nao deu para enviar, e a mensagem diz por que."""


@dataclass(frozen=True)
class Credencial:
    """
    O que e preciso para falar com o servico.

    Nunca gravada em disco pelo Agente: chega pelo canal autenticado, e usada,
    e some com o processo.
    """

    endpoint: str
    """Endereco do servico. Vazio = Amazon S3."""
    regiao: str
    balde: str
    chave: str
    segredo: str
    prefixo: str = ""

    @property
    def descricao(self) -> str:
        """Frase para a tela e para o historico. **Sem** a credencial."""
        onde = self.endpoint or "Amazon S3"
        return f"{onde} · balde {self.balde}"

    def __repr__(self) -> str:
        """
        Representacao sem o segredo.

        Um `Pedido` impresso num log de erro levaria a chave de nuvem do
        cliente junto — e log e o lugar em que segredo mais vaza sem ninguem
        querer. O `dataclass` gera um `repr` com todos os campos; este
        substitui.
        """
        return f"Credencial({self.descricao}, chave=***, segredo=***)"


def _cliente(credencial: Credencial) -> S3Client:
    """Monta o cliente. Import tardio: boto3 e pesado para carregar sempre."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=credencial.endpoint or None,
        region_name=credencial.regiao or "us-east-1",
        aws_access_key_id=credencial.chave,
        aws_secret_access_key=credencial.segredo,
        config=Config(
            retries={"max_attempts": 3, "mode": "standard"},
            # Assinatura v4: o que Backblaze, Wasabi e R2 esperam. A v2
            # ainda funciona na Amazon e e recusada pelos demais.
            signature_version="s3v4",
        ),
    )


def _chave_do_objeto(credencial: Credencial, nome: str) -> str:
    prefixo = credencial.prefixo.strip("/")
    return f"{prefixo}/{nome}" if prefixo else nome


def _sha_do_arquivo(caminho: Path) -> str:
    digestor = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        while pedaco := arquivo.read(LEITURA):
            digestor.update(pedaco)
    return digestor.hexdigest()


def _sha_do_objeto(cliente: S3Client, credencial: Credencial, chave: str) -> str:
    """
    Le o objeto de volta e recalcula o hash.

    Ler de volta custa banda e e o unico jeito honesto de dizer "chegou
    inteiro": o ETag nao serve em envio multipart, porque la ele e o hash dos
    hashes das partes.
    """
    digestor = hashlib.sha256()
    corpo = cliente.get_object(Bucket=credencial.balde, Key=chave)["Body"]
    try:
        while pedaco := corpo.read(LEITURA):
            digestor.update(pedaco)
    finally:
        corpo.close()
    return digestor.hexdigest()


def enviar(pacote: Path, credencial: Credencial) -> dict[str, Any]:
    """
    Envia o pacote e confere o que chegou.

    Falha em qualquer ponto vira `EnvioRecusado` com o motivo — inclusive a
    conferencia. Objeto que nao confere e **apagado**: deixa-lo no balde
    criaria um backup com aparencia de completo.
    """
    from botocore.exceptions import BotoCoreError, ClientError

    if not pacote.is_file():
        msg = f"o pacote nao existe: {pacote.name}"
        raise EnvioRecusado(msg)

    chave = _chave_do_objeto(credencial, pacote.name)
    tamanho = pacote.stat().st_size
    esperado = _sha_do_arquivo(pacote)
    cliente = _cliente(credencial)

    try:
        _subir(cliente, pacote, credencial, chave, tamanho)
    except (ClientError, BotoCoreError, OSError) as erro:
        msg = f"o envio para {credencial.descricao} falhou: {_motivo(erro)}"
        raise EnvioRecusado(msg) from erro

    try:
        recebido = _sha_do_objeto(cliente, credencial, chave)
    except (ClientError, BotoCoreError) as erro:
        msg = f"o objeto subiu mas nao pode ser lido de volta: {_motivo(erro)}"
        raise EnvioRecusado(msg) from erro

    if recebido != esperado:
        _apagar(cliente, credencial, chave)
        msg = (
            f"o objeto chegou a {credencial.descricao} com conteudo diferente "
            "do enviado. O objeto foi removido."
        )
        raise EnvioRecusado(msg)

    return {
        "destino": credencial.descricao,
        "tipo": "s3",
        "objeto": chave,
        "tamanho_bytes": tamanho,
        "conferido_no_destino": True,
    }


def _subir(
    cliente: S3Client, pacote: Path, credencial: Credencial, chave: str, tamanho: int
) -> None:
    """Envia inteiro ou em partes, conforme o tamanho."""
    if tamanho < LIMITE_MULTIPART:
        with pacote.open("rb") as arquivo:
            cliente.put_object(Bucket=credencial.balde, Key=chave, Body=arquivo)
        return

    envio = cliente.create_multipart_upload(Bucket=credencial.balde, Key=chave)
    identificador = envio["UploadId"]
    partes: list[dict[str, Any]] = []
    try:
        with pacote.open("rb") as arquivo:
            numero = 1
            while pedaco := arquivo.read(PARTE):
                resposta = cliente.upload_part(
                    Bucket=credencial.balde,
                    Key=chave,
                    PartNumber=numero,
                    UploadId=identificador,
                    Body=pedaco,
                )
                partes.append({"ETag": resposta["ETag"], "PartNumber": numero})
                numero += 1
        cliente.complete_multipart_upload(
            Bucket=credencial.balde,
            Key=chave,
            UploadId=identificador,
            MultipartUpload={"Parts": partes},
        )
    except Exception:
        # Envio abandonado consome espaco no balde e gera cobranca ate alguem
        # notar. Ninguem nota: partes incompletas nao aparecem na listagem.
        _abortar(cliente, credencial, chave, identificador)
        raise


def _abortar(cliente: S3Client, credencial: Credencial, chave: str, identificador: str) -> None:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        cliente.abort_multipart_upload(Bucket=credencial.balde, Key=chave, UploadId=identificador)
    except (ClientError, BotoCoreError):
        # Limpeza que levanta esconderia a causa real da falha.
        return


def _apagar(cliente: S3Client, credencial: Credencial, chave: str) -> None:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        cliente.delete_object(Bucket=credencial.balde, Key=chave)
    except (ClientError, BotoCoreError):
        return


def _motivo(erro: Exception) -> str:
    """
    Mensagem curta e util, sem despejar a credencial no log.

    Erros do botocore trazem o endereco assinado; ele carrega a chave de
    acesso na consulta.
    """
    codigo = getattr(erro, "response", {}).get("Error", {}).get("Code", "")
    if codigo:
        return str(codigo)
    return type(erro).__name__


__all__ = [
    "LIMITE_MULTIPART",
    "PARTE",
    "Credencial",
    "EnvioRecusado",
    "enviar",
]
