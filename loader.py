"""
loader.py — Lê arquivos .xhtml e extrai o texto limpo para o pipeline.

Responsabilidades:
- Localizar o conteúdo relevante dentro do body (com ou sem div)
- Extrair elementos em ordem: h1, h2, p
- Retornar texto limpo concatenado, preservando estrutura de parágrafos

Não faz nenhuma chamada de API nem acessa o sistema de arquivos além do path recebido.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup, Tag


# ---------------------------------------------------------------------------
# Constantes internas
# ---------------------------------------------------------------------------

# Tags consideradas conteúdo narrativo, em ordem de prioridade
_TAGS_CONTEUDO = ["h1", "h2", "p"]


# ---------------------------------------------------------------------------
# Funções internas
# ---------------------------------------------------------------------------

def _localizar_conteiner(soup: BeautifulSoup) -> Tag:
    """
    Retorna o elemento que contém o conteúdo narrativo.

    Tenta body > div primeiro.
    Se não encontrar div direta do body, usa o body diretamente.
    """
    body = soup.find("body")
    if not body:
        # Documento sem body — usa o root
        return soup

    div = body.find("div", recursive=False)
    if div:
        return div

    return body


def _extrair_elementos(conteiner: Tag) -> list[str]:
    """
    Extrai o texto de cada elemento de conteúdo em ordem de documento.
    Preserva quebras entre elementos para manter estrutura de parágrafos.
    """
    linhas: list[str] = []

    for elemento in conteiner.find_all(_TAGS_CONTEUDO):
        texto = elemento.get_text(strip=True)
        if texto:
            linhas.append(texto)

    return linhas


# ---------------------------------------------------------------------------
# Interface pública
# ---------------------------------------------------------------------------

def carregar_fragmento(path: str | Path) -> str:
    """
    Lê um arquivo .xhtml e retorna o texto limpo do conteúdo narrativo.

    Parâmetros
    ----------
    path : str | Path
        Caminho para o arquivo .xhtml.

    Retorna
    -------
    str
        Texto extraído, com cada elemento separado por linha dupla.
        Pronto para ser inserido no prompt.

    Levanta
    -------
    FileNotFoundError
        Se o arquivo não existir.
    ValueError
        Se o arquivo não tiver conteúdo extraível.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.resolve()}")

    texto_bruto = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(texto_bruto, "html.parser")

    conteiner = _localizar_conteiner(soup)
    elementos = _extrair_elementos(conteiner)

    if not elementos:
        raise ValueError(f"Nenhum conteúdo extraível encontrado em: {path.name}")

    return "\n\n".join(elementos)
