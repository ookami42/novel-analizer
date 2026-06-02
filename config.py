"""
config.py — Constantes e caminhos do pipeline de análise.

Todas as decisões de configuração ficam aqui.
Nenhum outro módulo deve ter strings de path, URLs ou parâmetros de API hardcoded.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Pastas
# ---------------------------------------------------------------------------

# Pasta de entrada padrão — sobrescrita por --pasta no CLI
PASTA_ENTRADA_PADRAO = Path("ordered-fragments")

# Pasta de saída — criada automaticamente se não existir
PASTA_SAIDA = Path("knowledge")

# ---------------------------------------------------------------------------
# Nomenclatura de arquivos
# ---------------------------------------------------------------------------

# Padrão dos arquivos de entrada
# Exemplo: text-001.xhtml
PADRAO_XHTML = r"^text-(\d+)\.xhtml$"

# Padrão de saída por fragmento
# Exemplo: analise-fragmento-007.md
PREFIXO_ANALISE = "analise-fragmento"

# Padrão de saída por capítulo consolidado
# Exemplo: capitulo-002.json
PREFIXO_CAPITULO = "capitulo"

# JSON final consolidado do volume inteiro
ARQUIVO_KNOWLEDGE_FINAL = PASTA_SAIDA / "knowledge-final.json"

# ---------------------------------------------------------------------------
# API — Qwen
# ---------------------------------------------------------------------------

QWEN_BASE_URL = "http://localhost:3002/v1"
QWEN_API_KEY = "sk-no-key-required"
QWEN_MODEL = "qwen3.7-max"

# Timeout por chamada em segundos
# Respostas longas com thinking ativado podem demorar
QWEN_TIMEOUT = 600

# Máximo de tokens na resposta
QWEN_MAX_TOKENS = 8192

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

# Caminho para o arquivo de prompt do consolidador
PROMPT_CONSOLIDA_PATH = Path("prompts/chapter-consolidator.md")

# Caminho para o arquivo de prompt do analisador
PROMPT_ANALISE_PATH = Path("prompts/fragment-analizer.md")


# Marcadores do prompt de análise

MARCADOR_REFERENCIAS = "=== 1. Campos de referência e TOC ==="
MARCADOR_JSON_BASE = "=== 2. JSON base ==="
MARCADOR_FRAGMENTO = "=== 3. Fragmento de historia ==="

# ---------------------------------------------------------------------------
# Comportamento do pipeline
# ---------------------------------------------------------------------------

# Se True, loga cada fragmento processado com timestamp
LOG_VERBOSO = True

# Se True, interrompe o pipeline ao primeiro erro de API
# Se False, loga o erro e continua para o próximo fragmento
PARAR_NO_ERRO = False

# Timeout para chamada de API em segundos
QWEN_TIMEOUT = 600

# Máximo de tentativas de retry para chamadas de API
MAX_TENTATIVAS_RETRY = 3

# Espera entre retries em segundos
ESPERA_RETRY = 10

# Delay antes de chamar a API (segundos) - útil para rate limiting
DELAY_API_CHAMADA = 10

# ---------------------------------------------------------------------------
# Nomes de arquivos de saída
# ---------------------------------------------------------------------------

# Nome padrão do arquivo TOC
TOC_FILENAME_DEFAULT = Path(PASTA_SAIDA / "table_of_contents.json")

# Nome padrão do arquivo de plano de processamento
PROCESSING_PLAN_FILENAME = Path(PASTA_SAIDA / "processing_plan.json")

# Caminho para o template JSON de conhecimento
KNOWLEDGE_TEMPLATE_PATH = Path(PASTA_SAIDA / "knowledge-template.json")

# Caminho para valores de referencia
KNOWLEDGE_SCALE_PATH = Path(PASTA_SAIDA / "knowledge-scale.json")
