"""Gestión de caché para VoxForge Local.

Proporciona funcionalidades para:
- Limpieza de caché por antigüedad
- Limpieza de caché por tamaño (LRU)
- Limpieza de fragmentos específicos
- Limpieza de voces
- Estadísticas de caché
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .db import Store

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


# =============================================================================
# DTOs
# =============================================================================

@dataclass
class CacheStats:
    """Estadísticas de la caché."""
    fragments_count: int = 0
    fragments_size_bytes: int = 0
    voices_count: int = 0
    voices_size_bytes: int = 0
    models_count: int = 0
    models_size_bytes: int = 0
    total_size_bytes: int = 0
    
    def __str__(self) -> str:
        return (
            f"Fragmentos: {self.fragments_count} ({self._format_bytes(self.fragments_size_bytes)}) | "
            f"Voces: {self.voices_count} ({self._format_bytes(self.voices_size_bytes)}) | "
            f"Modelos: {self.models_count} ({self._format_bytes(self.models_size_bytes)}) | "
            f"Total: {self._format_bytes(self.total_size_bytes)}"
        )
    
    @staticmethod
    def _format_bytes(size: int) -> str:
        """Formatea bytes en formato legible."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


@dataclass
class CacheCleanupResult:
    """Resultado de una operación de limpieza de caché."""
    fragments_removed: int = 0
    fragments_size_freed: int = 0
    voices_removed: int = 0
    voices_size_freed: int = 0
    models_removed: int = 0
    models_size_freed: int = 0
    total_size_freed: int = 0
    errors: list[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def __str__(self) -> str:
        parts = []
        if self.fragments_removed > 0:
            parts.append(f"fragmentos: {self.fragments_removed} ({CacheStats._format_bytes(self.fragments_size_freed)})")
        if self.voices_removed > 0:
            parts.append(f"voces: {self.voices_removed} ({CacheStats._format_bytes(self.voices_size_freed)})")
        if self.models_removed > 0:
            parts.append(f"modelos: {self.models_removed} ({CacheStats._format_bytes(self.models_size_freed)})")
        
        result = f"Eliminados: {', '.join(parts) if parts else 'nada'}"
        result += f" | Total liberado: {CacheStats._format_bytes(self.total_size_freed)}"
        
        if self.errors:
            result += f" | Errores: {len(self.errors)}"
        
        return result


# =============================================================================
# Cache Manager
# =============================================================================

class CacheManager:
    """Gestor de caché para VoxForge.
    
    Proporciona métodos para limpiar y gestionar la caché de:
    - Fragmentos de audio sintetizados
    - Archivos de referencia de voces
    - Modelos descargados
    """
    
    def __init__(
        self,
        cache_dir: Path,
        store: Store | None = None,
        voices_dir: Path | None = None,
        models_dir: Path | None = None,
    ):
        """Inicializa el gestor de caché.
        
        Args:
            cache_dir: Directorio de caché de fragmentos.
            store: Store de SQLite para la base de datos de fragmentos.
            voices_dir: Directorio de voces (referencias).
            models_dir: Directorio de modelos descargados.
        """
        self.cache_dir = Path(cache_dir)
        self.store = store
        self.voices_dir = Path(voices_dir) if voices_dir else None
        self.models_dir = Path(models_dir) if models_dir else None
        
        logger.debug(f"CacheManager inicializado: cache_dir={self.cache_dir}")
        if self.voices_dir:
            logger.debug(f"  voices_dir={self.voices_dir}")
        if self.models_dir:
            logger.debug(f"  models_dir={self.models_dir}")
    
    # ---------------------------------------------------------------------------
    # Estadísticas
    # ---------------------------------------------------------------------------
    
    def get_stats(self) -> CacheStats:
        """Obtiene estadísticas de la caché."""
        stats = CacheStats()
        
        # Fragmentos
        if self.cache_dir.exists():
            for wav_file in self.cache_dir.glob("*.wav"):
                stats.fragments_count += 1
                stats.fragments_size_bytes += wav_file.stat().st_size
        
        # Voces
        if self.voices_dir and self.voices_dir.exists():
            for voice_file in self.voices_dir.glob("*.wav"):
                stats.voices_count += 1
                stats.voices_size_bytes += voice_file.stat().st_size
        
        # Modelos
        if self.models_dir and self.models_dir.exists():
            for model_file in self.models_dir.rglob("*"):
                if model_file.is_file():
                    stats.models_count += 1
                    stats.models_size_bytes += model_file.stat().st_size
        
        stats.total_size_bytes = (
            stats.fragments_size_bytes + 
            stats.voices_size_bytes + 
            stats.models_size_bytes
        )
        
        return stats
    
    # ---------------------------------------------------------------------------
    # Limpieza por antigüedad
    # ---------------------------------------------------------------------------
    
    def cleanup_by_age(
        self,
        days: int | None = None,
        hours: int | None = None,
        fragments: bool = True,
        voices: bool = False,
        models: bool = False,
        dry_run: bool = False,
    ) -> CacheCleanupResult:
        """Elimina archivos de caché más antiguos que el tiempo especificado.
        
        Args:
            days: Número de días (opcional).
            hours: Número de horas (opcional).
            fragments: Si True, limpia caché de fragmentos.
            voices: Si True, limpia caché de voces.
            models: Si True, limpia caché de modelos.
            dry_run: Si True, no elimina nada, solo reporta.
        
        Returns:
            CacheCleanupResult con los detalles de la limpieza.
        """
        if days is None and hours is None:
            raise ValueError("Debes especificar al menos days o hours")
        
        total_seconds = (days or 0) * 24 * 3600 + (hours or 0) * 3600
        cutoff_time = time.time() - total_seconds
        
        result = CacheCleanupResult()
        
        # Limpiar fragmentos
        if fragments and self.cache_dir.exists():
            result = self._cleanup_directory_by_time(
                self.cache_dir,
                "*.wav",
                cutoff_time,
                dry_run,
                result,
                is_fragment=True
            )
        
        # Limpiar voces
        if voices and self.voices_dir and self.voices_dir.exists():
            result = self._cleanup_directory_by_time(
                self.voices_dir,
                "*.wav",
                cutoff_time,
                dry_run,
                result,
                is_fragment=False
            )
        
        # Limpiar modelos
        if models and self.models_dir and self.models_dir.exists():
            result = self._cleanup_directory_by_time(
                self.models_dir,
                "*",
                cutoff_time,
                dry_run,
                result,
                is_fragment=False,
                recursive=True
            )
        
        return result
    
    def _cleanup_directory_by_time(
        self,
        directory: Path,
        pattern: str,
        cutoff_time: float,
        dry_run: bool,
        result: CacheCleanupResult,
        is_fragment: bool = False,
        recursive: bool = False,
    ) -> CacheCleanupResult:
        """Limpia un directorio eliminando archivos más antiguos que cutoff_time."""
        files_to_check = directory.rglob(pattern) if recursive else directory.glob(pattern)
        
        for file_path in files_to_check:
            if not file_path.is_file():
                continue
            
            mtime = file_path.stat().st_mtime
            if mtime < cutoff_time:
                size = file_path.stat().st_size
                
                if dry_run:
                    if is_fragment:
                        result.fragments_removed += 1
                        result.fragments_size_freed += size
                    else:
                        result.voices_removed += 1
                        result.voices_size_freed += size
                else:
                    try:
                        file_path.unlink()
                        if is_fragment:
                            result.fragments_removed += 1
                            result.fragments_size_freed += size
                        else:
                            result.voices_removed += 1
                            result.voices_size_freed += size
                        
                        # Si es fragmento, también eliminar de la base de datos
                        if is_fragment and self.store:
                            # Extraer el hash del nombre del archivo (sin extensión)
                            digest = file_path.stem
                            self.store.delete_fragment(digest)
                        
                        logger.debug(f"Eliminado: {file_path}")
                    except Exception as e:
                        result.errors.append(f"Error al eliminar {file_path}: {e}")
                        logger.error(f"Error al eliminar {file_path}: {e}")
        
        return result
    
    # ---------------------------------------------------------------------------
    # Limpieza por tamaño (LRU)
    # ---------------------------------------------------------------------------
    
    def cleanup_by_size(
        self,
        max_size_bytes: int,
        fragments: bool = True,
        voices: bool = False,
        models: bool = False,
        dry_run: bool = False,
    ) -> CacheCleanupResult:
        """Elimina archivos de caché hasta que el tamaño total sea menor que max_size_bytes.
        
        Usa política LRU (Least Recently Used) - elimina primero los archivos más antiguos.
        
        Args:
            max_size_bytes: Tamaño máximo deseado en bytes.
            fragments: Si True, incluye fragmentos en la limpieza.
            voices: Si True, incluye voces en la limpieza.
            models: Si True, incluye modelos en la limpieza.
            dry_run: Si True, no elimina nada, solo reporta.
        
        Returns:
            CacheCleanupResult con los detalles de la limpieza.
        """
        result = CacheCleanupResult()
        current_size = self.get_stats().total_size_bytes
        
        if current_size <= max_size_bytes:
            return result
        
        size_to_free = current_size - max_size_bytes
        
        # Recolectar todos los archivos con sus tamaños y fechas de modificación
        files_to_consider = []
        
        if fragments and self.cache_dir.exists():
            for wav_file in self.cache_dir.glob("*.wav"):
                files_to_consider.append({
                    'path': wav_file,
                    'size': wav_file.stat().st_size,
                    'mtime': wav_file.stat().st_mtime,
                    'type': 'fragment'
                })
        
        if voices and self.voices_dir and self.voices_dir.exists():
            for voice_file in self.voices_dir.glob("*.wav"):
                files_to_consider.append({
                    'path': voice_file,
                    'size': voice_file.stat().st_size,
                    'mtime': voice_file.stat().st_mtime,
                    'type': 'voice'
                })
        
        if models and self.models_dir and self.models_dir.exists():
            for model_file in self.models_dir.rglob("*"):
                if model_file.is_file():
                    files_to_consider.append({
                        'path': model_file,
                        'size': model_file.stat().st_size,
                        'mtime': model_file.stat().st_mtime,
                        'type': 'model'
                    })
        
        # Ordenar por fecha de modificación (más antiguo primero) - LRU
        files_to_consider.sort(key=lambda x: x['mtime'])
        
        # Eliminar archivos hasta alcanzar el tamaño deseado
        freed_size = 0
        for file_info in files_to_consider:
            if freed_size >= size_to_free:
                break
            
            if dry_run:
                if file_info['type'] == 'fragment':
                    result.fragments_removed += 1
                    result.fragments_size_freed += file_info['size']
                elif file_info['type'] == 'voice':
                    result.voices_removed += 1
                    result.voices_size_freed += file_info['size']
                else:
                    result.models_removed += 1
                    result.models_size_freed += file_info['size']
                freed_size += file_info['size']
            else:
                try:
                    file_info['path'].unlink()
                    if file_info['type'] == 'fragment':
                        result.fragments_removed += 1
                        result.fragments_size_freed += file_info['size']
                        # Eliminar de la base de datos
                        if self.store:
                            self.store.delete_fragment(file_info['path'].stem)
                    elif file_info['type'] == 'voice':
                        result.voices_removed += 1
                        result.voices_size_freed += file_info['size']
                    else:
                        result.models_removed += 1
                        result.models_size_freed += file_info['size']
                    
                    freed_size += file_info['size']
                    logger.debug(f"Eliminado por LRU: {file_info['path']}")
                except Exception as e:
                    result.errors.append(f"Error al eliminar {file_info['path']}: {e}")
                    logger.error(f"Error al eliminar {file_info['path']}: {e}")
        
        result.total_size_freed = freed_size
        return result
    
    # ---------------------------------------------------------------------------
    # Limpieza específica
    # ---------------------------------------------------------------------------
    
    def cleanup_fragments(
        self,
        all: bool = False,
        older_than_days: int | None = None,
        older_than_hours: int | None = None,
        dry_run: bool = False,
    ) -> CacheCleanupResult:
        """Limpia la caché de fragmentos.
        
        Args:
            all: Si True, elimina todos los fragmentos.
            older_than_days: Elimina fragmentos más antiguos que X días.
            older_than_hours: Elimina fragmentos más antiguos que X horas.
            dry_run: Si True, no elimina nada, solo reporta.
        
        Returns:
            CacheCleanupResult con los detalles de la limpieza.
        """
        if all:
            return self._cleanup_all_fragments(dry_run)
        elif older_than_days or older_than_hours:
            return self.cleanup_by_age(
                days=older_than_days,
                hours=older_than_hours,
                fragments=True,
                voices=False,
                models=False,
                dry_run=dry_run
            )
        else:
            raise ValueError("Debes especificar all=True o older_than_days/older_than_hours")
    
    def _cleanup_all_fragments(self, dry_run: bool) -> CacheCleanupResult:
        """Elimina todos los fragmentos de caché."""
        result = CacheCleanupResult()
        
        if not self.cache_dir.exists():
            return result
        
        for wav_file in self.cache_dir.glob("*.wav"):
            size = wav_file.stat().st_size
            
            if dry_run:
                result.fragments_removed += 1
                result.fragments_size_freed += size
            else:
                try:
                    wav_file.unlink()
                    result.fragments_removed += 1
                    result.fragments_size_freed += size
                    
                    # Eliminar de la base de datos
                    if self.store:
                        self.store.delete_fragment(wav_file.stem)
                    
                    logger.debug(f"Eliminado: {wav_file}")
                except Exception as e:
                    result.errors.append(f"Error al eliminar {wav_file}: {e}")
                    logger.error(f"Error al eliminar {wav_file}: {e}")
        
        result.total_size_freed = result.fragments_size_freed
        return result
    
    def cleanup_voices(
        self,
        all: bool = False,
        older_than_days: int | None = None,
        dry_run: bool = False,
    ) -> CacheCleanupResult:
        """Limpia las voces de referencia.
        
        Args:
            all: Si True, elimina todas las voces.
            older_than_days: Elimina voces más antiguas que X días.
            dry_run: Si True, no elimina nada, solo reporta.
        
        Returns:
            CacheCleanupResult con los detalles de la limpieza.
        """
        if not self.voices_dir or not self.voices_dir.exists():
            return CacheCleanupResult()
        
        if all:
            return self._cleanup_all_voices(dry_run)
        elif older_than_days:
            return self.cleanup_by_age(
                days=older_than_days,
                fragments=False,
                voices=True,
                models=False,
                dry_run=dry_run
            )
        else:
            raise ValueError("Debes especificar all=True o older_than_days")
    
    def _cleanup_all_voices(self, dry_run: bool) -> CacheCleanupResult:
        """Elimina todas las voces de referencia."""
        result = CacheCleanupResult()
        
        if not self.voices_dir or not self.voices_dir.exists():
            return result
        
        for voice_file in self.voices_dir.glob("*.wav"):
            size = voice_file.stat().st_size
            
            if dry_run:
                result.voices_removed += 1
                result.voices_size_freed += size
            else:
                try:
                    voice_file.unlink()
                    result.voices_removed += 1
                    result.voices_size_freed += size
                    logger.debug(f"Eliminada voz: {voice_file}")
                except Exception as e:
                    result.errors.append(f"Error al eliminar {voice_file}: {e}")
                    logger.error(f"Error al eliminar {voice_file}: {e}")
        
        result.total_size_freed = result.voices_size_freed
        return result
    
    def cleanup_all(self, dry_run: bool = False) -> CacheCleanupResult:
        """Limpia toda la caché (fragmentos, voces y modelos).
        
        Args:
            dry_run: Si True, no elimina nada, solo reporta.
        
        Returns:
            CacheCleanupResult con los detalles de la limpieza.
        """
        result = CacheCleanupResult()
        
        # Limpiar fragmentos
        fragments_result = self._cleanup_all_fragments(dry_run)
        result.fragments_removed = fragments_result.fragments_removed
        result.fragments_size_freed = fragments_result.fragments_size_freed
        result.errors.extend(fragments_result.errors)
        
        # Limpiar voces
        voices_result = self._cleanup_all_voices(dry_run)
        result.voices_removed = voices_result.voices_removed
        result.voices_size_freed = voices_result.voices_size_freed
        result.errors.extend(voices_result.errors)
        
        # Limpiar modelos (si el directorio existe)
        if self.models_dir and self.models_dir.exists():
            models_result = self._cleanup_all_models(dry_run)
            result.models_removed = models_result.models_removed
            result.models_size_freed = models_result.models_size_freed
            result.errors.extend(models_result.errors)
        
        result.total_size_freed = (
            result.fragments_size_freed + 
            result.voices_size_freed + 
            result.models_size_freed
        )
        
        return result
    
    def _cleanup_all_models(self, dry_run: bool) -> CacheCleanupResult:
        """Elimina todos los modelos descargados."""
        result = CacheCleanupResult()
        
        if not self.models_dir or not self.models_dir.exists():
            return result
        
        for model_file in self.models_dir.rglob("*"):
            if not model_file.is_file():
                continue
            
            size = model_file.stat().st_size
            
            if dry_run:
                result.models_removed += 1
                result.models_size_freed += size
            else:
                try:
                    model_file.unlink()
                    result.models_removed += 1
                    result.models_size_freed += size
                    logger.debug(f"Eliminado modelo: {model_file}")
                except Exception as e:
                    result.errors.append(f"Error al eliminar {model_file}: {e}")
                    logger.error(f"Error al eliminar {model_file}: {e}")
        
        result.total_size_freed = result.models_size_freed
        return result
