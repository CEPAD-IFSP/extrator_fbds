# Extração de datas (ANO BASE / SIRGAS) a partir dos MAPAS da FBDS

Este módulo complementa o _scraper_ assíncrono da FBDS fazendo **OCR** nas imagens
(`.jpg`) dentro das pastas `MAPAS` de cada município, para extrair:

- **ANO_BASE** – ano da imagem/satélite (ex.: `2012` em `Imagens Rapideye - Ano 2012`)
- **ANO_SIRGAS** – ano do datum (ex.: `2000` em `Datum SIRGAS 2000`)
- **FULL** – texto completo reconhecido na área de interesse (limpo para caber bem em CSV)

Os resultados são gravados em arquivos CSV (`fbds_mapas_ocr.csv` e
`fbds_mapas_ocr_mp.csv`).

---

## Arquivos principais

### Scraper (download dos dados)

- `scripts/fbds_core.py`
  - Implementa a classe `FBDSAsyncScraper`, responsável por:
    - Listar estados e cidades diretamente do site `geo.fbds.org.br`.
    - Baixar recursivamente os arquivos de `APP`, `HIDROGRAFIA`, `MAPAS`, `USO`, etc.
    - Manter a mesma estrutura de diretórios do site abaixo de uma pasta raiz
      de downloads (por padrão, `downloads/`).
    - Registrar exceções e estruturas “não padrão” em uma lista interna que
      pode ser salva em `exceptions.json`.

- `scripts/fbds_async_scraper.py`
  - _CLI_ (linha de comando) para o `FBDSAsyncScraper` usando `argparse`.
  - Principais parâmetros:

    - `--base-url`  (opcional)
      - URL raiz do repositório FBDS (padrão: `https://geo.fbds.org.br/`).

    - `--output`  (opcional)
      - Pasta onde os arquivos serão salvos (padrão: `downloads`).

    - `--max-concurrency`  (opcional)
      - Número máximo de downloads simultâneos (padrão: `5`).
      - Valores maiores aceleram o download, mas podem sobrecarregar a
        conexão/servidor.

    - `--folders`  (opcional)
      - Lista de pastas de topo a baixar para cada cidade.
      - Exemplo: `--folders APP MAPAS` baixa apenas as pastas `APP` e `MAPAS`.

    - `--exceptions`  (opcional)
      - Caminho do arquivo JSON onde o log de exceções será salvo/lido.
      - Se não informado, usa `downloads/exceptions.json`.

    - `--retry-failures`
      - Em vez de fazer um novo _scrape_, lê o `exceptions.json` e tenta
        novamente apenas os downloads/requisições que falharam.

    - _Comandos de listagem/inspeção_:
      - `--list-states`
        - Lista os códigos de estados disponíveis.
      - `--list-cities UF`
        - Lista as cidades de uma UF, por exemplo:

          ```bash
          python scripts/fbds_async_scraper.py --list-cities SP
          ```

      - `--describe-city UF CIDADE`
        - Mostra a estrutura de pastas/arquivos para uma cidade específica.

    - _Comandos de download_ (usar um de cada vez):

      - `--download-city UF CIDADE1 [CIDADE2 ...]`

        Exemplo: baixar apenas `APP` e `MAPAS` para duas cidades específicas:

        ```bash
        python scripts/fbds_async_scraper.py \
          --download-city SP SAO_PAULO SANTOS \
          --folders APP MAPAS \
          --max-concurrency 5
        ```

      - `--download-state UF`

        Exemplo: baixar todas as cidades de `SP`, somente pasta `MAPAS`:

        ```bash
        python scripts/fbds_async_scraper.py \
          --download-state SP \
          --folders MAPAS \
          --max-concurrency 5
        ```

      - `--download-all`

        Baixa todos os estados disponíveis. Pode ser combinado com `--states`
        para filtrar alguns estados.

        Exemplo: baixar apenas `SP` e `MG`, todas as pastas padrão:

        ```bash
        python scripts/fbds_async_scraper.py \
          --download-all \
          --states SP MG \
          --max-concurrency 5
        ```

    - Exemplo de uso do `--retry-failures` após um erro durante `--download-all`:

      ```bash
      python scripts/fbds_async_scraper.py --retry-failures --exceptions downloads/exceptions.json
      ```

### OCR (extração de datas a partir dos MAPAS)

- `scripts/fbds_ocr.py`
  - Define a função `extract_year_and_datum(image_path)` que:
    - Abre a imagem com **Pillow** (`PIL.Image`)
    - Recorta a região inferior direita (onde ficam as legendas da FBDS)
    - Roda **Tesseract** via `pytesseract` para extrair o texto
    - Usa **regex** para encontrar:
      - `ANO` ou `ANO BASE` seguido de 4 dígitos (qualquer combinação de maiúsculas/minúsculas)
      - `SIRGAS` seguido de 4 dígitos
    - Retorna um dicionário:
      - `{"ano": "2012" | None, "sirgas": "2000" | None, "raw_text": texto_original}`

- `scripts/run_fbds_ocr_batch.py`
  - Versão **sequencial** (single process).
  - Percorre a árvore de downloads gerada pelo `fbds_async_scraper.py`,
    procurando imagens `.jpg`/`.jpeg` em `MAPAS`:
    - `downloads/UF/CIDADE/MAPAS/*.jpg`
  - Para cada imagem, chama `extract_year_and_datum` e grava uma linha no CSV
    `fbds_mapas_ocr.csv` com colunas:
    - `ESTADO, CIDADE, ANO_BASE, ANO_SIRGAS, FULL`.

- `scripts/run_fbds_ocr_batch_mp.py`
  - Versão **multiprocessada**, usando todos os _cores_ da máquina.
  - Mesmo comportamento da versão sequencial, mas usando `ProcessPoolExecutor`
    para processar várias imagens em paralelo.
  - Salva o resultado em `fbds_mapas_ocr_mp.csv`.

---

## Pré-requisitos

### 1. Dependências de sistema

É necessário ter o **Tesseract OCR** instalado no sistema, com o idioma
português. Em distribuições baseadas em Debian/Ubuntu, por exemplo:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-por
```

Em outras distribuições, procure pelos pacotes equivalentes ou instale a partir
do site oficial do Tesseract.

### 2. Dependências Python

As bibliotecas Python utilizadas nesta parte do projeto são:

- `httpx` – cliente HTTP assíncrono para o _scraper_ (`fbds_core.py`)
- `beautifulsoup4` – parsing de HTML para listar diretórios/arquivos
- `pytesseract` – _binding_ Python para o Tesseract (OCR)
- `Pillow` – manipulação de imagens (PIL)

Todas elas estão listadas em `requirements.txt`. Para instalar no ambiente
ativo (virtualenv, conda, etc.), use:

```bash
pip install -r requirements.txt
```

> Importante: `pytesseract` precisa encontrar o executável `tesseract` no
> `PATH`. Se o Tesseract estiver instalado em um caminho não padrão, configure
> `pytesseract.pytesseract.tesseract_cmd` em `fbds_ocr.py` ou no seu código
> antes de chamar a função.

### 3. Estrutura de diretórios de entrada

Assume-se que o _scraper_ assíncrono já foi executado e que os dados da FBDS
foram baixados para uma estrutura semelhante a:

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

Se seus downloads estiverem em outro diretório, você pode usar a variável de
ambiente `DOWNLOAD_ROOT` (ver abaixo).

---

## Como usar

### 1. Rodar o scraper assíncrono (download dos dados)

Antes de rodar o OCR, é preciso garantir que os dados da FBDS foram baixados.
Alguns exemplos de uso do _scraper_:

- Listar estados disponíveis:

  ```bash
  python scripts/fbds_async_scraper.py --list-states
  ```

- Listar cidades de um estado (ex.: `SP`):

  ```bash
  python scripts/fbds_async_scraper.py --list-cities SP
  ```

- Ver estrutura de uma cidade específica:

  ```bash
  python scripts/fbds_async_scraper.py --describe-city SP SAO_PAULO
  ```

- Baixar apenas a pasta `MAPAS` para todas as cidades de `SP`:

  ```bash
  python scripts/fbds_async_scraper.py \
    --download-state SP \
    --folders MAPAS \
    --max-concurrency 5
  ```

- Baixar `APP` + `MAPAS` para todos os estados, filtrando por alguns estados:

  ```bash
  python scripts/fbds_async_scraper.py \
    --download-all \
    --states SP MG RJ \
    --folders APP MAPAS \
    --max-concurrency 5
  ```

  Se algo falhar no meio, você pode usar `--retry-failures` para focar só nas
  falhas registradas em `exceptions.json`.

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

- Pasta padrão de entrada: `downloads/`.
- Saída: `fbds_mapas_ocr_mp.csv`.

Saída típica:

- `[MP] Scanning MAPAS JPEGs under: /caminho/para/downloads`
- `Found 1234 images. Using 8 processes for OCR.`
- `Processed 50/1234 images...`
- `Processed 100/1234 images...`
- ...
- `Done. Wrote 1234 rows to /caminho/para/fbds_mapas_ocr_mp.csv`

> Dica: se quiser limitar o uso de CPU, podemos facilmente adicionar um
> parâmetro `--workers N` à versão multiprocessada. Hoje o número de processos é
> automaticamente definido por `os.cpu_count()`.

### 4. Usando outra pasta de downloads

Se os dados baixados estiverem em outro lugar, defina a variável de ambiente
`DOWNLOAD_ROOT` antes de chamar o script:

```bash
export DOWNLOAD_ROOT=/caminho/para/minha_pasta_de_downloads
python scripts/run_fbds_ocr_batch_mp.py
```

ou para a versão sequencial:

```bash
export DOWNLOAD_ROOT=/caminho/para/minha_pasta_de_downloads
python scripts/run_fbds_ocr_batch.py
```

---

## Formato de saída (CSV)

Ambos os scripts escrevem CSVs com as colunas:

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
