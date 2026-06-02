"""
logger.py — Módulo centralizado de logging para todo o pipeline.

Responsabilidades:
- Fornecer funções de log padronizadas com timestamp e módulo
- Substituir todos os prints diretos no código
- Permitir controle de verbosidade centralizado
- Logar mensagens normais e erros em streams apropriados

Uso
---
    from logger import log, log_erro
    
    log("Mensagem informativa", modulo="main")
    log_erro("Erro ocorrido", modulo="api_client")
"""

from __future__ import annotations

import sys
from datetime import datetime

from config import LOG_VERBOSO


def log(mensagem: str, modulo: str = "unknown", verboso: bool = True) -> None:
    """
    Loga mensagem com timestamp e módulo se verbose estiver habilitado.
    
    Parâmetros
    ----------
    mensagem : str
        Conteúdo da mensagem a ser logada.
    modulo : str
        Nome do módulo que está gerando o log (ex: "main", "api_client").
    verboso : bool
        Se True, respeita a configuração LOG_VERBOSO do config.
        Se False, sempre loga independentemente da configuração.
    """
    if verboso or LOG_VERBOSO:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{modulo}] {mensagem}", flush=True)


def log_erro(mensagem: str, modulo: str = "unknown") -> None:
    """
    Loga mensagem de erro com timestamp e módulo em stderr.
    
    Parâmetros
    ----------
    mensagem : str
        Conteúdo da mensagem de erro.
    modulo : str
        Nome do módulo que está gerando o log de erro.
    """
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{modulo}] ❌ {mensagem}", file=sys.stderr, flush=True)
