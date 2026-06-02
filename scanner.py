"""
scanner.py — Descobre, ordena e inspeciona os arquivos .xhtml da pasta de entrada.

Responsabilidades:
- Listar arquivos text-NNN.xhtml em ordem numérica
- Detectar presença de <h1> em cada arquivo
- Extrair o título do <h1> quando presente
- Retornar lista de FragmentoInfo para uso pelo pipeline

Não faz extração completa do texto — isso é responsabilidade do loader.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from config import PADRAO_XHTML


# ---------------------------------------------------------------------------
# Estrutura de dados
# ---------------------------------------------------------------------------

@dataclass
class FragmentoInfo:
    indice: int          # Posição na sequência (0-based)
    path: Path           # Caminho absoluto do arquivo
    nome: str            # Nome do arquivo, ex: text-001.xhtml
    tem_h1: bool         # True se o arquivo contém <h1>
    titulo: str | None   # Conteúdo do <h1> se presente, None caso contrário


# ---------------------------------------------------------------------------
# Funções internas
# ---------------------------------------------------------------------------

_PADRAO_NOME = re.compile(PADRAO_XHTML, re.IGNORECASE)


def _extrair_numero(path: Path) -> int:
    """Extrai o número do nome do arquivo para ordenação numérica."""
    match = _PADRAO_NOME.match(path.name)
    if not match:
        raise ValueError(f"Nome de arquivo fora do padrão esperado: {path.name}")
    return int(match.group(1))


def _inspecionar(path: Path) -> tuple[bool, str | None]:
    """
    Lê o arquivo e verifica presença de <h1>.
    Retorna (tem_h1, titulo).
    Usa html.parser — sem dependências externas além de beautifulsoup4.
    """
    texto = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(texto, "html.parser")
    h1 = soup.find("h1")
    if h1:
        return True, h1.get_text(strip=True)
    return False, None


# ---------------------------------------------------------------------------
# Interface pública
# ---------------------------------------------------------------------------

def descobrir_fragmentos(pasta: str | Path) -> list[FragmentoInfo]:
    """
    Varre a pasta informada em busca de arquivos text-NNN.xhtml.

    Parâmetros
    ----------
    pasta : str | Path
        Caminho para a pasta de entrada. Valor padrão no pipeline está no config.py

    Retorna
    -------
    list[FragmentoInfo]
        Lista ordenada numericamente por NNN.

    Levanta
    -------
    FileNotFoundError
        Se a pasta não existir.
    ValueError
        Se não houver nenhum arquivo text-NNN.xhtml na pasta.
    """
    pasta = Path(pasta)

    if not pasta.exists():
        raise FileNotFoundError(f"Pasta de entrada não encontrada: {pasta.resolve()}")

    arquivos = [
        p for p in pasta.iterdir()
        if p.is_file() and _PADRAO_NOME.match(p.name)
    ]

    if not arquivos:
        raise ValueError(f"Nenhum arquivo text-NNN.xhtml encontrado em: {pasta.resolve()}")

    # Ordena numericamente — garante text-002 antes de text-010
    arquivos.sort(key=_extrair_numero)

    fragmentos: list[FragmentoInfo] = []
    for indice, path in enumerate(arquivos):
        tem_h1, titulo = _inspecionar(path)
        fragmentos.append(FragmentoInfo(
            indice=indice,
            path=path.resolve(),
            nome=path.name,
            tem_h1=tem_h1,
            titulo=titulo,
        ))

    return fragmentos


def resumir(fragmentos: list[FragmentoInfo]) -> None:
    """
    Imprime um resumo da lista de fragmentos no stdout.
    Útil para debug e para o --dry-run do main.py.
    """
    total = len(fragmentos)
    capitulos = [f for f in fragmentos if f.tem_h1]

    print(f"Fragmentos encontrados : {total}")
    print(f"Capítulos detectados   : {len(capitulos)}")
    print()

    capitulo_atual = 0
    for f in fragmentos:
        if f.tem_h1:
            capitulo_atual += 1
            marcador = f"[CAP {capitulo_atual:02d}] {f.titulo or '(sem título)'}"
        else:
            marcador = "        (continuação)"
        print(f"  {f.indice:03d}  {f.nome}  {marcador}")
