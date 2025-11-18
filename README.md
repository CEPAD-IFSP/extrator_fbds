# Extração de datas (ANO BASE / SIRGAS) a partir dos MAPAS da FBDS

Este pacote Python fornece ferramentas para:

1. **Download assíncrono** de geodados do site [geo.fbds.org.br](https://geo.fbds.org.br/)
2. **OCR (reconhecimento óptico de caracteres)** em imagens de mapas para extrair metadados
3. **Integração com Airflow** para execuções periódicas e automatizadas

Dados extraídos por OCR das imagens em `MAPAS`:

- **ANO_BASE** – ano da imagem/satélite (ex.: `2012` em `Imagens Rapideye - Ano 2012`)
- **ANO_SIRGAS** – ano do datum (ex.: `2000` em `Datum SIRGAS 2000`)
- **FULL** – texto completo reconhecido na área de interesse (limpo para caber bem em CSV)

Os resultados são gravados em arquivos CSV (`fbds_mapas_ocr.csv` e
`fbds_mapas_ocr_mp.csv`).

---

## Instalação

### Como pacote Python (recomendado para Airflow)

```bash
# Instalação direta do repositório
pip install git+https://github.com/CEPAD-IFSP/extrator_fbds.git

# Ou em modo editável para desenvolvimento
git clone https://github.com/CEPAD-IFSP/extrator_fbds.git
cd extrator_fbds
pip install -e .
```

### Dependências do sistema

É necessário ter o **Tesseract OCR** instalado:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-por

# Outras distribuições: consulte a documentação do Tesseract
```

---

## Uso

### 1. Linha de comando (CLI)

Após a instalação, três comandos ficam disponíveis:

```bash
# Scraper assíncrono
fbds-scraper --help

# OCR sequencial
fbds-ocr --help

# OCR paralelo (multiprocessing)
fbds-ocr-mp --help
```

### 2. Uso programático (Python/Airflow)

```python
import asyncio
from pathlib import Path
from extrator_fbds import FBDSAsyncScraper
from extrator_fbds.run_fbds_ocr_batch_mp import run_batch_mp

# Download de dados
async def download_example():
    scraper = FBDSAsyncScraper(
        download_root=Path("/data/fbds"),
        max_concurrency=8,
        city_concurrency=3,
    )
    results = await scraper.download_all(
        state_filter=["SP", "MG"],
        folder_filter=["MAPAS"],
    )
    scraper.save_exceptions()
    return results

# Executar
results = asyncio.run(download_example())

# OCR batch
run_batch_mp(
    download_root=Path("/data/fbds"),
    output_csv=Path("/data/results/ocr_output.csv"),
    max_workers=4,
)
```

### 3. Integração com Airflow

Veja o exemplo completo em [`examples/airflow_dag_example.py`](examples/airflow_dag_example.py).

**Instalação no ambiente Airflow:**

```bash
# No ambiente Python do Airflow
pip install git+https://github.com/CEPAD-IFSP/extrator_fbds.git
```

**Exemplo simplificado de DAG:**

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from extrator_fbds import FBDSAsyncScraper
from extrator_fbds.run_fbds_ocr_batch_mp import run_batch_mp
import asyncio

def download_task():
    scraper = FBDSAsyncScraper(download_root="/data/fbds")
    asyncio.run(scraper.download_state("SP", folder_filter=["MAPAS"]))
    scraper.save_exceptions()

def ocr_task():
    run_batch_mp(download_root="/data/fbds", output_csv="/data/results.csv")

with DAG("fbds_monthly", schedule_interval="@monthly") as dag:
    download = PythonOperator(task_id="download", python_callable=download_task)
    ocr = PythonOperator(task_id="ocr", python_callable=ocr_task)
    download >> ocr
```

---

## Componentes do pacote

### Módulos principais

- `extrator_fbds.fbds_core`
  - **`FBDSAsyncScraper`**: classe principal para download assíncrono
    - Lista estados e cidades diretamente do site `geo.fbds.org.br`
    - Baixa recursivamente arquivos de `APP`, `HIDROGRAFIA`, `MAPAS`, `USO`, etc.
    - Mantém a estrutura de diretórios do site
    - Registra exceções em `exceptions.json`

- `extrator_fbds.fbds_async_scraper`
  - Interface de linha de comando (CLI) para o scraper
  - Comando: `fbds-scraper`

- `extrator_fbds.fbds_ocr`
  - **`extract_year_and_datum(image_path)`**: função OCR para extrair metadados de uma imagem

- `extrator_fbds.run_fbds_ocr_batch`
  - **`run_batch()`**: processamento OCR sequencial
  - Comando: `fbds-ocr`

- `extrator_fbds.run_fbds_ocr_batch_mp`
  - **`run_batch_mp()`**: processamento OCR paralelo (multiprocessing)
  - Comando: `fbds-ocr-mp`

### Parâmetros do scraper CLI

- `--base-url` (opcional)
  - URL raiz do repositório FBDS (padrão: `https://geo.fbds.org.br/`)

- `--output` (opcional)
  - Pasta onde os arquivos serão salvos (padrão: `downloads`)

- `--max-concurrency` (opcional)
  - Número máximo de downloads simultâneos por arquivo (padrão: `5`)
  - Valores maiores aceleram o download, mas podem sobrecarregar a conexão/servidor

- `--city-concurrency` (opcional)
  - Número de cidades processadas em paralelo (padrão: `1`)
  - Permite processar múltiplas cidades simultaneamente

- `--folders` (opcional)
  - Lista de pastas de topo a baixar para cada cidade
  - Exemplo: `--folders APP MAPAS` baixa apenas as pastas `APP` e `MAPAS`

- `--exceptions` (opcional)
  - Caminho do arquivo JSON onde o log de exceções será salvo/lido
  - Se não informado, usa `downloads/exceptions.json`

- `--retry-failures`
  - Em vez de fazer um novo scrape, lê o `exceptions.json` e tenta
    novamente apenas os downloads/requisições que falharam

**Comandos de listagem/inspeção:**

- `--list-states`
  - Lista os códigos de estados disponíveis

- `--list-cities UF`
  - Lista as cidades de uma UF, por exemplo:

    ```bash
    fbds-scraper --list-cities SP
    ```

- `--describe-city UF CIDADE`
  - Mostra a estrutura de pastas/arquivos para uma cidade específica

**Comandos de download** (usar um de cada vez):

- `--download-city UF CIDADE1 [CIDADE2 ...]`

  Exemplo: baixar apenas `APP` e `MAPAS` para duas cidades específicas:

  ```bash
  fbds-scraper \
    --download-city SP SAO_PAULO SANTOS \
    --folders APP MAPAS \
    --max-concurrency 5
  ```

- `--download-state UF`

  Exemplo: baixar todas as cidades de `SP`, somente pasta `MAPAS`:

  ```bash
  fbds-scraper \
    --download-state SP \
    --folders MAPAS \
    --max-concurrency 8 \
    --city-concurrency 3
  ```

- `--download-all`

  Baixa todos os estados disponíveis. Pode ser combinado com `--states`
  para filtrar alguns estados.

  Exemplo: baixar apenas `SP` e `MG`, todas as pastas padrão:

  ```bash
  fbds-scraper \
    --download-all \
    --states SP MG \
    --max-concurrency 8 \
    --city-concurrency 3
  ```

Exemplo de uso do `--retry-failures` após falhas:

```bash
fbds-scraper --retry-failures --exceptions downloads/exceptions.json
```

---

## Exemplos de uso detalhados

### Download via CLI

**Listar estados disponíveis:**

```bash
fbds-scraper --list-states
```

**Listar cidades de um estado:**

```bash
fbds-scraper --list-cities SP
```

**Ver estrutura de uma cidade:**

```bash
fbds-scraper --describe-city SP SAO_PAULO
```

**Baixar apenas MAPAS para todas as cidades de SP:**

```bash
fbds-scraper \
  --download-state SP \
  --folders MAPAS \
  --max-concurrency 8 \
  --city-concurrency 3
```

**Baixar APP + MAPAS para SP, MG, RJ:**

```bash
fbds-scraper \
  --download-all \
  --states SP MG RJ \
  --folders APP MAPAS \
  --max-concurrency 10 \
  --city-concurrency 4
```

### OCR via CLI

**Processamento sequencial:**

```bash
fbds-ocr
# Usa defaults: downloads/ como entrada, fbds_mapas_ocr.csv como saída
```

**Processamento paralelo (recomendado):**

```bash
fbds-ocr-mp
# Usa defaults: downloads/ como entrada, fbds_mapas_ocr_mp.csv como saída
```

**Com variável de ambiente:**

```bash
export DOWNLOAD_ROOT=/data/fbds/downloads
fbds-ocr-mp
```

---

### Detalhes técnicos do OCR

A função `extract_year_and_datum(image_path)`:

- Abre a imagem com **Pillow** (`PIL.Image`)
- Recorta a região inferior direita (onde ficam as legendas da FBDS)
- Roda **Tesseract** via `pytesseract` para extrair o texto
- Usa **regex** para encontrar:
  - `ANO` ou `ANO BASE` seguido de 4 dígitos (qualquer combinação de maiúsculas/minúsculas)
  - `SIRGAS` seguido de 4 dígitos
- Retorna um dicionário:
  - `{"ano": "2012" | None, "sirgas": "2000" | None, "raw_text": texto_original}`

Os scripts `run_batch()` e `run_batch_mp()`:

- Percorrem a árvore de downloads procurando imagens `.jpg`/`.jpeg` em `MAPAS`:
  - `downloads/UF/CIDADE/MAPAS/*.jpg`
- Para cada imagem, chamam `extract_year_and_datum` e gravam uma linha no CSV
  - Colunas: `ESTADO, CIDADE, ANO_BASE, ANO_SIRGAS, FULL`
- Versão `_mp` usa `ProcessPoolExecutor` para paralelizar

---
português. Em distribuições baseadas em Debian/Ubuntu, por exemplo:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-por
```

Em outras distribuições, procure pelos pacotes equivalentes ou instale a partir
do site oficial do Tesseract.
---

## Estrutura de diretórios

Após o download, os dados seguem a estrutura:

```text
downloads/
  SP/
    ADAMANTINA/
      MAPAS/
        SP_3500105_APP.jpg
        SP_3500105_HIDROGRAFIA.jpg
        SP_3500105_RGB532.jpg
        SP_3500105_USO_DO_SOLO.jpg
    ...
  MG/
    ...
```

---

## Ajustando paralelismo/concorrência

Você pode acelerar os downloads ajustando dois parâmetros:

- `--max-concurrency`: número de requisições/arquivos em paralelo (nível por arquivo)
- `--city-concurrency`: número de cidades processadas em paralelo (nível por cidade)

Recomendações gerais:

- Comece com valores moderados e aumente aos poucos.
- Se notar muitos timeouts ou instabilidade, reduza um pouco.
- Combine com `--folders MAPAS` quando o objetivo for apenas o OCR dos mapas (reduz o volume total).

Exemplos para um estado (SP):

- Mais conservador (máquina/rede modestas):

  ```bash
  python scripts/fbds_async_scraper.py \
    --download-state SP \
    --folders MAPAS \
    --max-concurrency 3 \
    --city-concurrency 1
  ```

- Intermediário (bom equilíbrio):

  ```bash
  python scripts/fbds_async_scraper.py \
    --download-state SP \
    --folders MAPAS \
    --max-concurrency 8 \
    --city-concurrency 3
  ```

- Mais agressivo (use com cautela):

  ```bash
  python scripts/fbds_async_scraper.py \
    --download-state SP \
    --max-concurrency 12 \
    --city-concurrency 6
  ```

Exemplos para Brasil (todos os estados ou um conjunto grande):

- Intermediário, filtrando alguns estados:

  ```bash
  python scripts/fbds_async_scraper.py \
    --download-all \
    --states SP MG RJ ES \
    --folders MAPAS \
    --max-concurrency 8 \
    --city-concurrency 3
  ```

- Todos os estados, foco completo (sem filtrar pastas):

  ```bash
  python scripts/fbds_async_scraper.py \
    --download-all \
    --max-concurrency 10 \
    --city-concurrency 4
  ```

Se a execução for interrompida ou ocorrerem falhas pontuais (timeouts etc.),
é possível retomar apenas o que falhou usando o log de exceções:

```bash
python scripts/fbds_async_scraper.py --retry-failures --exceptions downloads/exceptions.json
```

### 2. Versão sequencial (single process) do OCR

Roda em um único processo; é mais simples de depurar e mais leve em termos de
uso de CPU.

**Comando:**

```bash
python scripts/run_fbds_ocr_batch.py
```

- Pasta padrão de entrada: `downloads/` no diretório do repositório.
- Saída: `fbds_mapas_ocr.csv` na raiz do repositório.

Durante a execução, o script imprime algo como:

- `Scanning MAPAS JPEGs under: /caminho/para/downloads`
- `Processed 50 images so far...`
- `Done. Wrote 1234 rows to /caminho/para/fbds_mapas_ocr.csv`

### 3. Versão multiprocessada (usa todos os cores)

Roda várias instâncias do Tesseract em paralelo, usando até `os.cpu_count()`
processos. Ideal quando há muitas imagens e você quer reduzir o tempo total.

**Comando:**

```bash
python scripts/run_fbds_ocr_batch_mp.py
```

---

## Formato de saída (CSV)

Os scripts de OCR escrevem CSVs com as colunas:

- `ESTADO` – código da UF (ex.: `SP`, `MG`)
- `CIDADE` – nome da cidade (como aparece na estrutura de diretórios)
- `ANO_BASE` – ano extraído da legenda (`ANO` ou `ANO BASE` seguido de 4 dígitos)
- `ANO_SIRGAS` – ano do datum extraído de `SIRGAS XXXX`
- `FULL` – texto completo da legenda usado para o OCR, mas **normalizado**:
  - quebras de linha substituídas por espaços
  - múltiplos espaços colapsados em um só
  - vírgulas removidas
  - aspas duplas (`"`) trocadas por aspas simples (`'`)

---
