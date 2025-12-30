# Guía de Integración del Módulo api_service

## 📋 Introducción

El módulo `api_service` proporciona una capa unificada para interactuar con APIs externas como APIMIGO, NubeFact, SUNAT, etc. Ofrece:

1. **Gestión centralizada** de configuraciones API
2. **Rate limiting automático** según límites de cada servicio
3. **Auditoría completa** de todas las llamadas
4. **Procesamiento masivo** optimizado para lotes grandes
5. **Manejo robusto de errores** y reintentos automáticos

## 🚀 Configuración Inicial

### 1. Instalación del Módulo

Agrega `api_service` a tu `INSTALLED_APPS` en `settings.py`:

```python
INSTALLED_APPS = [
    # ... otras apps ...
    'api_service',
]