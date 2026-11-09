#!/usr/bin/env python3
"""NOVA CLI Theme Demo - Ejemplo de uso del tema NOVA en la línea de comandos.

Este script demuestra cómo usar los colores NOVA en aplicaciones de consola.
Puedes integrar este estilo en el CLI de VoxForge Local.

Uso:
    python examples/nova_cli_demo.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voxforge.themes import NOVA_CLI_Theme


def print_separator(char: str = "─", width: int = 60) -> None:
    """Imprimir un separador temático."""
    print(NOVA_CLI_Theme.accent(char * width))


def print_header(text: str, width: int = 60) -> None:
    """Imprimir un encabezado con estilo NOVA."""
    padding = (width - len(text)) // 2
    separator = " " * padding
    print(f"\n{NOVA_CLI_Theme.title(separator + text + separator)}")


def print_progress_bar(iteration: int, total: int, prefix: str = "", suffix: str = "") -> None:
    """Imprimir una barra de progreso con estilo NOVA."""
    percent = (iteration / total) * 100
    filled_length = int(40 * iteration // total)
    bar = "█" * filled_length + "░" * (40 - filled_length)
    
    sys.stdout.write(f"\r{prefix} {NOVA_CLI_Theme.accent('│')}{bar}{NOVA_CLI_Theme.accent('│')} {percent:6.2f}%{suffix}")
    sys.stdout.flush()


def clear_progress() -> None:
    """Limpiar la línea de progreso."""
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()


def typewriter_effect(text: str, delay: float = 0.03, color_func=None) -> None:
    """Efecto de máquina de escribir."""
    if color_func:
        text = color_func(text)
    
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def demo_basic_output():
    """Demo de salida básica."""
    print_header("SALIDA BÁSICA")
    print_separator()
    
    print(f"\n{NOVA_CLI_Theme.accent('Mensaje normal:')} Este es un texto con color normal")
    print(f"{NOVA_CLI_Theme.success('✓ Éxito:')} Operación completada con éxito")
    print(f"{NOVA_CLI_Theme.warning('⚠ Advertencia:')} El modelo no está precargado")
    print(f"{NOVA_CLI_Theme.error('✗ Error:')} Archivo no encontrado")
    print(f"{NOVA_CLI_Theme.info('ℹ Información:')} Procesando capítulo 1 de 12...")
    print(f"{NOVA_CLI_Theme.muted('Texto secundario:')} Detalles adicionales")
    print(f"{NOVA_CLI_Theme.bold('Texto en negrita:')} Esto es importante")
    print(f"{NOVA_CLI_Theme.dim('Texto tenue:')} Esto es menos importante")


def demo_header():
    """Demo de encabezado NOVA."""
    print_header("VOXFORGE LOCAL")
    print(f"{NOVA_CLI_Theme.muted('v0.6.0 | Tema NOVA | Inteligencia Local')}")
    print_separator("═")


def demo_voice_profiles():
    """Demo de lista de perfiles de voz."""
    print_header("PERFILES DE VOZ")
    print_separator()
    
    profiles = [
        ("María Clara", "2h 34m", "1500", "Activo"),
        ("Carlos Profundo", "3h 12m", "2300", "Activo"),
        ("Ana Natural", "1h 45m", "980", "Inactivo"),
        ("Jorge Robusto", "4h 20m", "3100", "Activo"),
    ]
    
    print(f"\n{NOVA_CLI_Theme.accent('Nombre')} {'Duración':<12} {'Muestras':<10} {'Estado':<10}")
    print_separator("─")
    
    for name, duration, samples, status in profiles:
        status_color = NOVA_CLI_Theme.success if status == "Activo" else NOVA_CLI_Theme.muted
        print(f"{name:<15} {duration:<12} {samples:<10} {status_color(status):<10}")
    
    print()


def demo_projects():
    """Demo de lista de proyectos."""
    print_header("PROYECTOS")
    print_separator()
    
    projects = [
        ("El Gran Libro", 12, 85, "En progreso"),
        ("Aventuras en Python", 8, 60, "En progreso"),
        ("Guía de IA", 15, 100, "Completado"),
        ("Narrativa Digital", 6, 30, "Pausado"),
    ]
    
    print(f"\n{NOVA_CLI_Theme.accent('Título'):<25} {'Caps':<6} {'Progreso':<10} {'Estado':<12}")
    print_separator("─")
    
    for title, chapters, progress, status in projects:
        if progress == 100:
            status_color = NOVA_CLI_Theme.success
        elif status == "Pausado":
            status_color = NOVA_CLI_Theme.warning
        else:
            status_color = NOVA_CLI_Theme.info
        
        progress_color = NOVA_CLI_Theme.success if progress == 100 else NOVA_CLI_Theme.info
        print(f"{title:<25} {chapters:<6} {progress_color(f'{progress}%'):<10} {status_color(status):<12}")
    
    print()


def demo_cache_stats():
    """Demo de estadísticas de caché."""
    print_header("ESTADÍSTICAS DE CACHÉ")
    print_separator()
    
    print(f"\n{NOVA_CLI_Theme.accent('Tipo')} {'Cantidad':<12} {'Tamaño':<12}")
    print_separator("─")
    
    stats = [
        ("Fragmentos", 1137, "327.34 MB"),
        ("Voces", 4, "156.20 MB"),
        ("Modelos", 2, "2.10 GB"),
    ]
    
    for item_type, count, size in stats:
        print(f"{NOVA_CLI_Theme.accent(item_type):<12} {count:<12} {size:<12}")
    
    print(f"\n{NOVA_CLI_Theme.bold('Total:')} 1143 elementos | 2.58 GB")
    print()


def demo_narration_process():
    """Demo de proceso de narración."""
    print_header("NARRACIÓN EN PROGRESO")
    print_separator()
    
    print(f"\n{NOVA_CLI_Theme.info('ℹ')} Iniciando narración...")
    time.sleep(0.5)
    
    print(f"{NOVA_CLI_Theme.success('✓')} Perfil de voz: María Clara")
    time.sleep(0.3)
    
    print(f"{NOVA_CLI_Theme.success('✓')} Modelo: XTTS-v2")
    time.sleep(0.3)
    
    print(f"{NOVA_CLI_Theme.success('✓')} proyecto: El Gran Libro")
    time.sleep(0.3)
    
    print(f"\n{NOVA_CLI_Theme.accent('Procesando capítulos:')}")
    
    chapters = ["Introducción", "Capítulo 1", "Capítulo 2", "Capítulo 3", "Epílogo"]
    total = len(chapters)
    
    for i, chapter in enumerate(chapters, 1):
        # Simular procesamiento
        for j in range(1, 101):
            print_progress_bar(j, 100, prefix=f"[{i}/{total}] {chapter}")
            time.sleep(0.02)
        clear_progress()
        print(f"  {NOVA_CLI_Theme.success('✓')} {chapter} - Completado")
        time.sleep(0.2)
    
    print(f"\n{NOVA_CLI_Theme.success('✓ Narración completada!')}")
    print(f"{NOVA_CLI_Theme.info('ℹ')} Tiempo total: 12m 34s")
    print(f"{NOVA_CLI_Theme.info('ℹ')} Fragmentos generados: 45")
    print()


def demo_thermal_monitoring():
    """Demo de monitoreo térmico."""
    print_header("MONITOREO TÉRMICO")
    print_separator()
    
    temps = [68, 70, 72, 75, 78, 80, 79, 77, 75, 73]
    
    for temp in temps:
        if temp < 75:
            color = NOVA_CLI_Theme.success
            status = "Normal"
        elif temp < 85:
            color = NOVA_CLI_Theme.warning
            status = "Precaución"
        else:
            color = NOVA_CLI_Theme.error
            status = "Peligro"
        
        print(f"  {color('●')} CPU: {temp}°C | {status}")
        time.sleep(0.15)
    
    print()


def demo_error_handling():
    """Demo de manejo de errores."""
    print_header("MANEJO DE ERRORES")
    print_separator()
    
    print(f"\n{NOVA_CLI_Theme.warning('⚠ Intentando cargar modelo...')}")
    time.sleep(0.5)
    
    print(f"{NOVA_CLI_Theme.error('✗ Error:')} El modelo 'xtts-v2' no se encontró en la caché")
    time.sleep(0.3)
    
    print(f"{NOVA_CLI_Theme.info('ℹ Sugerencia:')} Ejecuta '{NOVA_CLI_Theme.accent('voxforge model download xtts-v2')}' para descargar")
    time.sleep(0.5)
    
    print(f"\n{NOVA_CLI_Theme.warning('⚠ Intentando crear perfil...')}")
    time.sleep(0.5)
    
    print(f"{NOVA_CLI_Theme.error('✗ Error:')} El nombre 'María Clara' ya existe")
    time.sleep(0.3)
    
    print(f"{NOVA_CLI_Theme.info('ℹ Sugerencia:')} Usa un nombre único para el perfil")
    time.sleep(0.5)
    
    print(f"\n{NOVA_CLI_Theme.warning('⚠ Intentando narrar...')}")
    time.sleep(0.5)
    
    print(f"{NOVA_CLI_Theme.error('✗ Error:')} Espacio en disco insuficiente (necesitas 500MB más)")
    time.sleep(0.3)
    
    print(f"{NOVA_CLI_Theme.info('ℹ Sugerencia:')} Libera espacio o cambia la ubicación de la caché")
    print()


def demo_help_command():
    """Demo de comando de ayuda."""
    print_header("COMANDOS DISPONIBLES")
    print_separator()
    
    commands = {
        "Narración": [
            ("project-narrate", "Narrar un proyecto completo"),
            ("chapter narrate", "Narrar un capítulo específico"),
            ("speak", "Narrar texto directamente"),
        ],
        "Gestión": [
            ("voice list", "Listar perfiles de voz"),
            ("voice create", "Crear nuevo perfil de voz"),
            ("project list", "Listar proyectos"),
            ("cache stats", "Mostrar estadísticas de caché"),
            ("cache cleanup", "Limpiar caché"),
        ],
        "Información": [
            ("status", "Mostrar estado del sistema"),
            ("job list", "Listar trabajos en segundo plano"),
        ],
    }
    
    for category, cmds in commands.items():
        print(f"\n{NOVA_CLI_Theme.title(category)}")
        print_separator("─", 30)
        for cmd, desc in cmds:
            print(f"  {NOVA_CLI_Theme.accent(cmd):<20} {desc}")
    
    print()


def demo_ascii_art():
    """Demo de arte ASCII con estilo NOVA."""
    print_header("VOXFORGE LOCAL")
    
    ascii_art = r"""
     _____       _   _____ _____ ____  
    |_   _|___  (_) |_   _|_   _|  _ \
      | | / _ \| |    | |   | | | |_) |
      | |/ ___ \| |    | |   | | |  _ <
      |_/_/   \_\_|    |_|   |_| |_| \_\ 
    """
    
    for line in ascii_art.strip().split('\n'):
        print(f"{NOVA_CLI_Theme.title(line)}")
    
    print(f"\n{NOVA_CLI_Theme.muted('Clonación de voz 100% local')}")
    print(f"{NOVA_CLI_Theme.muted('Inteligencia Local - Infinitas Posibilidades')}")
    print()


def main():
    """Función principal del demo."""
    # Encabezado inicial
    demo_ascii_art()
    
    # Mostrar menú
    print(NOVA_CLI_Theme.title("MENÚ DE DEMOS"))
    print_separator()
    
    demos = [
        ("1", "Salida básica", demo_basic_output),
        ("2", "Encabezados y separadores", demo_header),
        ("3", "Perfiles de voz", demo_voice_profiles),
        ("4", "Proyectos", demo_projects),
        ("5", "Estadísticas de caché", demo_cache_stats),
        ("6", "Proceso de narración", demo_narration_process),
        ("7", "Monitoreo térmico", demo_thermal_monitoring),
        ("8", "Manejo de errores", demo_error_handling),
        ("9", "Comandos de ayuda", demo_help_command),
        ("0", "Salir", None),
    ]
    
    for num, name, _ in demos:
        print(f"  {NOVA_CLI_Theme.accent(num)}. {name}")
    
    print(f"\n{NOVA_CLI_Theme.accent('Selecciona una opción (0-9): ')}", end="")
    
    # Ejecutar demo basado en la selección
    try:
        choice = input("").strip()
        
        if choice == "0":
            print(f"\n{NOVA_CLI_Theme.success('✓ Hasta luego!')}")
            return 0
        
        for num, name, func in demos:
            if choice == num:
                print(f"\n{NOVA_CLI_Theme.info('ℹ Ejecutando:')} {name}")
                print_separator("─")
                func()
                
                # Preguntar si continuar
                print(f"{NOVA_CLI_Theme.accent('¿Otra demo? (s/n): ')}", end="")
                again = input("").strip().lower()
                
                if again == "s":
                    return main()  # Reiniciar el menú
                else:
                    print(f"\n{NOVA_CLI_Theme.success('✓ Demo completado!')}")
                    return 0
        
        print(f"\n{NOVA_CLI_Theme.error('✗ Opción no válida')}")
        return 1
        
    except KeyboardInterrupt:
        print(f"\n\n{NOVA_CLI_Theme.warning('⚠ Demo interrumpido por el usuario')}")
        return 0


if __name__ == "__main__":
    # Verificar que la terminal soporte colores
    try:
        # Intentar imprimir colores de prueba
        print("\033[36mTest\033[0m", end="", flush=True)
    except:
        print("⚠ Advertencia: La terminal no soporta colores ANSI")
        print("El demo puede no verse correctamente")
        print()
    
    sys.exit(main())
