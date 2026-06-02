"""
writer.py — Salva a resposta do Qwen para cada fragmento analisado.

Responsabilidades:
- Sanitizar a resposta bruta removendo cercas de markdown (```json ... ```)
- Validar que o conteúdo é JSON parseável antes de salvar
- Salvar o arquivo analise-fragmento-NNN.md na pasta de saída
- Criar a pasta de saída se não existir

Não faz nenhuma chamada de API nem interpreta o conteúdo do JSON.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from config import PASTA_SAIDA, PREFIXO_ANALISE


# ---------------------------------------------------------------------------
# Padrão para remover cercas de markdown
# ---------------------------------------------------------------------------

# Captura conteúdo entre ```json ... ``` ou ``` ... ```
_CERCA_MARKDOWN = re.compile(
    r"^```(?:json)?\s*\n(.*?)\n```\s*$",
    re.DOTALL | re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Exceções próprias
# ---------------------------------------------------------------------------

class ErroJSON(Exception):
    """Resposta do modelo não é JSON válido após sanitização."""


# ---------------------------------------------------------------------------
# Funções internas
# ---------------------------------------------------------------------------

def _sanitizar(conteudo: str) -> str:
    """
    Remove cercas de markdown se presentes.
    Retorna o conteúdo limpo para parsing.
    """
    match = _CERCA_MARKDOWN.search(conteudo.strip())
    if match:
        return match.group(1).strip()
    return conteudo.strip()


def _validar_json(conteudo: str, nome_arquivo: str) -> None:
    """
    Verifica se o conteúdo é JSON válido.

    Levanta
    -------
    ErroJSON
        Se o conteúdo não for parseável como JSON.
    """
    try:
        json.loads(conteudo)
    except json.JSONDecodeError as e:
        raise ErroJSON(
            f"Resposta para {nome_arquivo} não é JSON válido: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Interface pública
# ---------------------------------------------------------------------------

def salvar_analise(indice: int, conteudo: str, pasta: str | Path = PASTA_SAIDA) -> Path:
    """
    Sanitiza, valida e salva a resposta do Qwen como analise-fragmento-NNN.md.

    Parâmetros
    ----------
    indice : int
        Índice do fragmento (0-based), usado para nomear o arquivo.
    conteudo : str
        Resposta bruta do modelo retornada pelo api_client.py.
    pasta : str | Path
        Pasta de saída. Padrão: PASTA_SAIDA do config.py.

    Retorna
    -------
    Path
        Caminho do arquivo salvo.

    Levanta
    -------
    ErroJSON
        Se o conteúdo não for JSON válido após sanitização.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)

    nome = f"{PREFIXO_ANALISE}-{indice:03d}.md"
    path = pasta / nome

    conteudo_limpo = _sanitizar(conteudo)
    _validar_json(conteudo_limpo, nome)

    path.write_text(conteudo_limpo, encoding="utf-8")
    return path


def ler_analise(indice: int, pasta: str | Path = PASTA_SAIDA) -> str:
    """
    Lê o conteúdo de um analise-fragmento-NNN.md salvo.

    Usado pelo consolidador.py para coletar os JSONs de um capítulo.

    Parâmetros
    ----------
    indice : int
        Índice do fragmento (0-based).
    pasta : str | Path
        Pasta onde o arquivo está salvo.

    Retorna
    -------
    str
        Conteúdo do arquivo como string.

    Levanta
    -------
    FileNotFoundError
        Se o arquivo não existir.
    """
    pasta = Path(pasta)
    nome = f"{PREFIXO_ANALISE}-{indice:03d}.md"
    path = pasta / nome

    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo de análise não encontrado: {path.resolve()}"
        )

    return path.read_text(encoding="utf-8")
