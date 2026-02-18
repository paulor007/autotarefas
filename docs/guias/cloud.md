# Integrações Cloud

Backup e sincronização com serviços de armazenamento em nuvem.

## Instalação

```bash
# Todas as integrações cloud
pip install autotarefas[cloud]

# Ou individualmente:
pip install google-auth google-auth-oauthlib google-api-python-client  # Google Drive
pip install dropbox                                                       # Dropbox
pip install boto3                                                         # AWS S3
```

## Verificar Disponibilidade

```python
from autotarefas.cloud import check_dependencies, get_available_providers

# Ver quais estão instalados
print(check_dependencies())
# {'google_drive': True, 'dropbox': True, 's3': True}

# Lista de provedores disponíveis
print(get_available_providers())
# ['google_drive', 'dropbox', 's3']
```

---

## Google Drive

### Configuração

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto ou selecione existente
3. Ative a **Google Drive API**
4. Crie credenciais OAuth 2.0 (Desktop App)
5. Baixe o arquivo `credentials.json`

### Uso Básico

```python
from autotarefas.cloud import GoogleDriveClient, GoogleDriveBackupTask

# Cliente direto
client = GoogleDriveClient("credentials.json")
client.authenticate()  # Abre navegador na primeira vez

# Listar arquivos
files = client.list_files()
for f in files:
    print(f"{f['name']} - {f['id']}")

# Upload
result = client.upload_file("backup.zip", folder_id="abc123")

# Download
client.download_file("file_id_xyz", "download.zip")
```

### Tarefa de Backup

```python
from autotarefas.cloud import GoogleDriveBackupTask

task = GoogleDriveBackupTask(
    source="/dados/importantes",
    credentials_file="credentials.json",
    folder_name="MeusBackups",  # Cria pasta automaticamente
    compress=True
)

result = task.run()
if result.success:
    print(f"Backup ID: {result.data['file_id']}")
```

### Restauração

```python
from autotarefas.cloud import GoogleDriveRestoreTask

task = GoogleDriveRestoreTask(
    file_id="abc123xyz",
    destination="/restaurado",
    credentials_file="credentials.json",
    extract=True  # Extrai se for ZIP
)

result = task.run()
```

---

## Dropbox

### Configuração

1. Acesse [Dropbox Developers](https://www.dropbox.com/developers)
2. Crie um app
3. Gere um **Access Token**
4. Configure a variável de ambiente:

```bash
export DROPBOX_ACCESS_TOKEN="seu_token_aqui"
```

### Uso Básico

```python
from autotarefas.cloud import DropboxClient, DropboxBackupTask

# Cliente direto
client = DropboxClient()  # Usa DROPBOX_ACCESS_TOKEN

# Listar arquivos
files = client.list_files("/backups")

# Upload
result = client.upload_file("backup.zip", "/backups/backup.zip")

# Download
client.download_file("/backups/backup.zip", "download.zip")
```

### Tarefa de Backup

```python
from autotarefas.cloud import DropboxBackupTask

task = DropboxBackupTask(
    source="/dados/importantes",
    dropbox_folder="/AutoTarefas_Backups",
    compress=True
)

result = task.run()
if result.success:
    print(f"Backup: {result.data['dropbox_path']}")
```

### Restauração

```python
from autotarefas.cloud import DropboxRestoreTask

task = DropboxRestoreTask(
    dropbox_path="/AutoTarefas_Backups/backup_20250214.zip",
    destination="/restaurado",
    extract=True
)

result = task.run()
```

---

## Amazon S3

### Configuração

1. Crie um usuário IAM na [AWS Console](https://console.aws.amazon.com/iam)
2. Dê permissões de S3 (AmazonS3FullAccess ou política customizada)
3. Gere **Access Key** e **Secret Key**
4. Configure as variáveis:

```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"
```

### Uso Básico

```python
from autotarefas.cloud import S3Client, S3BackupTask

# Cliente direto
client = S3Client("meu-bucket-backups")

# Listar arquivos
files = client.list_files(prefix="backups/")

# Upload
result = client.upload_file("backup.zip", "backups/backup.zip")

# Download
client.download_file("backups/backup.zip", "download.zip")

# URL pré-assinada (para compartilhar)
url = client.get_presigned_url("backups/backup.zip", expiration=3600)
```

### Tarefa de Backup

```python
from autotarefas.cloud import S3BackupTask

task = S3BackupTask(
    source="/dados/importantes",
    bucket_name="meu-bucket-backups",
    s3_prefix="autotarefas/backups/",
    compress=True,
    storage_class="STANDARD"  # ou GLACIER para arquivamento
)

result = task.run()
if result.success:
    print(f"S3 URL: {result.data['s3_url']}")
```

### Restauração

```python
from autotarefas.cloud import S3RestoreTask

task = S3RestoreTask(
    bucket_name="meu-bucket-backups",
    s3_key="autotarefas/backups/backup_20250214.zip",
    destination="/restaurado",
    extract=True
)

result = task.run()
```

### Classes de Armazenamento S3

| Classe | Uso | Custo |
|--------|-----|-------|
| `STANDARD` | Acesso frequente | $$ |
| `STANDARD_IA` | Acesso infrequente | $ |
| `GLACIER` | Arquivamento (minutos) | ¢ |
| `GLACIER_DEEP_ARCHIVE` | Arquivamento longo (horas) | ¢¢ |

```python
# Backup para Glacier (arquivamento barato)
task = S3BackupTask(
    source="/dados/arquivos",
    bucket_name="meu-bucket",
    storage_class="GLACIER"
)
```

---

## Agendamento de Backups Cloud

```python
from autotarefas.core import TaskScheduler
from autotarefas.cloud import S3BackupTask, GoogleDriveBackupTask

scheduler = TaskScheduler()

# Backup S3 diário às 2h
s3_backup = S3BackupTask(
    source="/dados",
    bucket_name="meu-bucket"
)
scheduler.add_cron(s3_backup, "0 2 * * *", name="s3_daily")

# Backup Google Drive semanal
gdrive_backup = GoogleDriveBackupTask(
    source="/documentos",
    credentials_file="credentials.json"
)
scheduler.add_cron(gdrive_backup, "0 3 * * 0", name="gdrive_weekly")

scheduler.run()
```

---

## Tratamento de Erros

```python
from autotarefas.cloud import S3BackupTask

task = S3BackupTask(
    source="/dados",
    bucket_name="meu-bucket",
    max_retries=3,  # Retry em caso de falha
    retry_delay=30  # Espera 30s entre tentativas
)

result = task.run()

if not result.success:
    print(f"Erro: {result.error}")
    # Notificar admin, tentar outro provedor, etc.
```

---

## Boas Práticas

!!! tip "Segurança"
    - Nunca commite credenciais no código
    - Use variáveis de ambiente ou secret managers
    - Configure permissões mínimas necessárias

!!! tip "Performance"
    - Comprima arquivos antes do upload
    - Use classes de armazenamento adequadas
    - Configure retry para conexões instáveis

!!! tip "Organização"
    - Use prefixos/pastas por data ou tipo
    - Implemente rotação de backups antigos
    - Documente a estrutura de pastas
