# tests/integration/nubefact_flow/config.py

"""
Configuración centralizada para pruebas de integración.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class StressTestConfig:
    """Configuración para pruebas de estrés."""
    
    # Configuración de facturas
    start_numero: int = 91500
    count: int = 50
    concurrency: int = 10
    
    # Configuración de logging
    verbose: bool = False
    check_logs: bool = False  # Si debe verificar logs en BD
    
    # Configuración de timeouts
    connect_timeout: float = 5.0
    read_timeout: float = 15.0
    max_retries: int = 1
    
    # Directorios
    output_base: str = "test_output/integration/stress_test"
    
    @property
    def timeout_config(self):
        from api_service.services.base.timeout_config import TimeoutConfig
        return TimeoutConfig(
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
            max_retries=self.max_retries
        )


@dataclass
class DevelopmentConfig(StressTestConfig):
    """Configuración para desarrollo (más verbosa)."""
    verbose: bool = True
    check_logs: bool = True
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    max_retries: int = 3


@dataclass
class ProductionConfig(StressTestConfig):
    """Configuración para producción (optimizada)."""
    verbose: bool = False
    check_logs: bool = False
    connect_timeout: float = 5.0
    read_timeout: float = 15.0
    max_retries: int = 2