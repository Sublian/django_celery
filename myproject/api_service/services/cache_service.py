# api_service/cache_service.py
from django.core.cache import cache
from django.utils import timezone
import hashlib
import json
from datetime import date, datetime, timedelta


class APICacheService:
    """
    Servicio dedicado para manejo de cache de API
    """

    # Prefijos para diferentes tipos de cache
    CACHE_PREFIXES = {
        "tipo_cambio": "tc_",
        "ruc_individual": "ruc_",
        "ruc_lote": "ruc_lote_",
        "representantes": "rep_",
        "dni": "dni_",
    }

    # TTLs en segundos
    TTL_CONFIG = {
        "tipo_cambio": 900,  # 15 minutos
        "ruc_individual": 86400,  # 24 horas
        "ruc_lote": 3600,  # 1 hora
        "representantes": 7200,  # 2 horas
        "dni": 43200,  # 12 horas
        "short": 300,  # 5 minutos
        "medium": 1800,  # 30 minutos
        "long": 86400,  # 24 horas
    }

    @classmethod
    def get_cache_key(cls, cache_type, identifier):
        """Genera clave de cache consistente"""
        prefix = cls.CACHE_PREFIXES.get(cache_type, "")
        if isinstance(identifier, (list, dict)):
            # Para listas o diccionarios, crear hash
            identifier_str = json.dumps(identifier, sort_keys=True)
            identifier_hash = hashlib.md5(identifier_str.encode()).hexdigest()
            return f"{prefix}{identifier_hash}"
        return f"{prefix}{identifier}"

    @classmethod
    def get_tipo_cambio(cls, fecha=None):
        """Obtiene tipo de cambio del día desde cache"""
        # Si no se pasa fecha, usa hoy
        if fecha is None:
            fecha = datetime.now().date().isoformat()
        elif isinstance(fecha, date):
            fecha = fecha.isoformat()

        # La clave debe usar el prefijo 'tc_' según tu configuración
        cache_key = cls.get_cache_key("tipo_cambio", fecha)

        cached = cache.get(cache_key)
        if cached:
            print(f"DEBUG: Cache hit para {cache_key}")
            cached["cache_hit"] = True
            cached["cache_timestamp"] = datetime.now().isoformat()
            return cached

        print(f"DEBUG: Cache miss para {cache_key}")
        return None

    @classmethod
    def set_tipo_cambio(cls, fecha, data):
        """Guarda tipo de cambio en cache"""
        # Convertir fecha a string si es date
        if isinstance(fecha, date):
            fecha_str = fecha.isoformat()
        else:
            fecha_str = str(fecha)

        cache_key = cls.get_cache_key("tipo_cambio", fecha_str)

        # Preparar datos para cache
        cache_data = {
            **data,
            "cached_at": datetime.now().isoformat(),
            "expires_at": (
                datetime.now() + timedelta(seconds=cls.TTL_CONFIG["tipo_cambio"])
            ).isoformat(),
            "ttl_seconds": cls.TTL_CONFIG["tipo_cambio"],
        }

        print(f"DEBUG: Guardando en cache: {cache_key}")
        success = cache.set(cache_key, cache_data, cls.TTL_CONFIG["tipo_cambio"])
        print(f"DEBUG: Guardado exitoso: {success}")
        return success

    @classmethod
    def get_ruc_individual(cls, ruc):
        """Obtiene datos de un RUC individual desde cache"""
        cache_key = cls.get_cache_key("ruc_individual", ruc)
        return cache.get(cache_key)

    @classmethod
    def set_ruc_individual(cls, ruc, data):
        """Guarda datos de un RUC individual en cache"""
        cache_key = cls.get_cache_key("ruc_individual", ruc)

        # Asegurar que los datos sean serializables
        cache_data = cls._prepare_for_cache(data)
        cache_data.update({"cached_at": datetime.now().isoformat(), "ruc": ruc})

        cache.set(cache_key, cache_data, cls.TTL_CONFIG["ruc_individual"])
        return True

    @classmethod
    def get_ruc_lote(cls, ruc_list):
        """Obtiene datos de un lote de RUCs desde cache"""
        cache_key = cls.get_cache_key("ruc_lote", sorted(ruc_list))
        return cache.get(cache_key)

    @classmethod
    def set_ruc_lote(cls, ruc_list, data):
        """Guarda datos de un lote de RUCs en cache"""
        cache_key = cls.get_cache_key("ruc_lote", sorted(ruc_list))

        # Preparar datos para cache
        cache_data = {
            "results": data,
            "cached_at": datetime.now().isoformat(),
            "ruc_count": len(ruc_list),
            "expires_at": (
                datetime.now() + timedelta(seconds=cls.TTL_CONFIG["ruc_lote"])
            ).isoformat(),
        }

        cache.set(cache_key, cache_data, cls.TTL_CONFIG["ruc_lote"])
        return True

    @classmethod
    def _prepare_for_cache(cls, data):
        """Prepara datos para ser guardados en cache (serializables)"""
        if isinstance(data, dict):
            # Crear copia y asegurar que todos los valores sean serializables
            cache_data = {}
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    cache_data[key] = value
                elif isinstance(value, (list, dict)):
                    cache_data[key] = cls._prepare_for_cache(value)
                elif isinstance(value, datetime):
                    cache_data[key] = value.isoformat()
                else:
                    cache_data[key] = str(value)
            return cache_data
        elif isinstance(data, list):
            return [cls._prepare_for_cache(item) for item in data]
        else:
            return data

    @classmethod
    def clear_cache_type(cls, cache_type=None):
        """Limpia cache específico o todo el cache"""
        if cache_type:
            # Eliminar solo claves con el prefijo específico
            prefix = cls.CACHE_PREFIXES.get(cache_type, "")
            # Nota: Esto requiere un backend de cache que soporte pattern matching
            # Para Redis, podríamos usar: cache.delete_pattern(f"{prefix}*")
            print(
                f"⚠️  Para eliminar por tipo, necesita Redis u otro backend con pattern matching"
            )
            return False
        else:
            cache.clear()
            return True

    @classmethod
    def get_stats(cls):
        """Obtiene estadísticas del cache (solo para algunos backends)"""
        # Esto depende del backend de cache
        return {
            "cache_service": "APICacheService",
            "ttl_config": cls.TTL_CONFIG,
            "prefixes": cls.CACHE_PREFIXES,
        }
