"""
check_point.py — Detecta o estado atual do pipeline e determina o ponto de retomada.

Responsabilidades:
- Encontrar o último analise-fragmento-NNN.md salvo
- Encontrar o último capitulo-NNN.json salvo
- Determinar o próximo fragmento a processar
- Fornecer o JSON de estado atual para injeção no próximo prompt
- Reportar o estado para o operador antes do pipeline iniciar
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from config import PADRAO_XHTML, PASTA_SAIDA, PREFIXO_ANALISE, PREFIXO_CAPITULO


# ---------------------------------------------------------------------------
# Padrões de nome de arquivo
# ---------------------------------------------------------------------------

_PADRAO_ANALISE  = re.compile(rf"^{PREFIXO_ANALISE}-(\d+)\.md$",   re.IGNORECASE)
_PADRAO_CAPITULO = re.compile(rf"^{PREFIXO_CAPITULO}-(\d+)\.json$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Estrutura de dados
# ---------------------------------------------------------------------------

@dataclass
class EstadoPipeline:
    """Representa o estado atual do pipeline ao iniciar ou retomar."""

    # Índice do próximo fragmento a processar (0-based, igual ao FragmentoInfo.indice)
    proximo_indice: int = 0

    # Fragmentos já processados (índices)
    processados: list[int] = field(default_factory=list)

    # Último capítulo consolidado salvo (número do arquivo, ex: 2 para capitulo-002.json)
    ultimo_capitulo: int | None = None

    # Path do último capitulo-NNN.json salvo — usado como JSON base para o próximo prompt
    path_json_atual: Path | None = None

    @property
    def retomando(self) -> bool:
        """True se o pipeline está retomando de um run anterior."""
        return len(self.processados) > 0

    @property
    def total_processados(self) -> int:
        return len(self.processados)


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class Check_Point:
    """
    Inspeciona a pasta de saída e determina o estado atual do pipeline.

    Uso
    ---
        resumo = Creck_Point()
        estado = resumo.carregar()
        print(resumo)  # exibe relatório legível
    """

    def __init__(self, pasta_saida: str | Path = PASTA_SAIDA) -> None:
        self._pasta = pasta_saida
        self._estado: EstadoPipeline | None = None

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def carregar(self) -> EstadoPipeline:
        """
        Lê a pasta de saída e constrói o EstadoPipeline.

        Cria a pasta de saída se não existir.
        Pode ser chamado múltiplas vezes — sempre relê o disco.

        Retorna
        -------
        EstadoPipeline
            Estado atual pronto para uso pelo main.py.
        """
        self._pasta.mkdir(parents=True, exist_ok=True)

        processados  = self._listar_processados()
        ultimo_cap, path_json = self._ultimo_capitulo()

        proximo = max(processados) + 1 if processados else 0

        self._estado = EstadoPipeline(
            proximo,
            processados,
            ultimo_cap,
            path_json,
        )
        return self._estado

    def json_base(self) -> str | None:
        """
        Retorna o conteúdo do último capitulo-NNN.json como string.

        Retorna None se nenhum capítulo foi consolidado ainda —
        nesse caso o prompt_builder usará o template vazio do prompt-analise.md.
        """
        if self._estado is None:
            raise RuntimeError("Chame carregar() antes de json_base().")

        path = self._estado.path_json_atual
        if path is None:
            return None

        return path.read_text(encoding="utf-8")

    def reportar(self) -> None:
        """Imprime um relatório legível do estado atual no stdout."""
        print(str(self))

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _listar_processados(self) -> list[int]:
        """Retorna lista ordenada dos índices já processados."""
        indices: list[int] = []
        for path in self._pasta.iterdir():
            match = _PADRAO_ANALISE.match(path.name)
            if match:
                indices.append(int(match.group(1)))
        return sorted(indices)

    def _ultimo_capitulo(self) -> tuple[int | None, Path | None]:
        """
        Encontra o capitulo-NNN.json com maior N.
        Retorna (numero, path) ou (None, None) se nenhum existir.
        """
        candidatos: list[tuple[int, Path]] = []
        for path in self._pasta.iterdir():
            match = _PADRAO_CAPITULO.match(path.name)
            if match:
                candidatos.append((int(match.group(1)), path))

        if not candidatos:
            return None, None

        candidatos.sort(key=lambda t: t[0])
        numero, path = candidatos[-1]
        return numero, path

    # ------------------------------------------------------------------
    # Representação
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        if self._estado is None:
            return "Creck_Point — ainda não carregado. Chame carregar() primeiro."

        e = self._estado
        linhas: list[str] = ["=== Estado do Pipeline ==="]

        if e.retomando:
            linhas.append(f"Retomando a partir do fragmento : {e.proximo_indice:03d}")
            linhas.append(f"Fragmentos já processados       : {e.total_processados}")
        else:
            linhas.append("Nenhum progresso anterior encontrado — iniciando do zero.")

        if e.ultimo_capitulo is not None:
            linhas.append(f"Último capítulo consolidado     : {e.ultimo_capitulo:03d}")
            linhas.append(f"JSON base                       : {e.path_json_atual}")
        else:
            linhas.append("JSON base                       : template vazio (nenhum capítulo consolidado)")

        return "\n".join(linhas)

    def __repr__(self) -> str:
        return (
            f"Creck_Point(pasta={self._pasta!r}, "
            f"carregado={self._estado is not None})"
        )
