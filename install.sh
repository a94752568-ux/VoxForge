#!/usr/bin/env bash
# =============================================================================
# VoxForge Local - Instalador automático
# =============================================================================
# Detecta hardware, instala dependencias del sistema y Python,
# configura el entorno y descarga los modelos necesarios.
# Soporta: Linux (Debian/Ubuntu, Fedora, Arch), macOS, Windows (WSL/Git Bash)
# =============================================================================

set -euo pipefail

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Directorio del proyecto (donde está este script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# -----------------------------------------------------------------------------
# Funciones de utilidad
# -----------------------------------------------------------------------------
log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

header() {
    echo ""
    echo "============================================================"
    echo "  $*"
    echo "============================================================"
}

# -----------------------------------------------------------------------------
# Detección de sistema operativo
# -----------------------------------------------------------------------------
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if command -v apt-get &>/dev/null; then
            DISTRO="debian"
        elif command -v dnf &>/dev/null; then
            DISTRO="fedora"
        elif command -v pacman &>/dev/null; then
            DISTRO="arch"
        else
            DISTRO="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        DISTRO="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
        DISTRO="windows"
    else
        OS="unknown"
        DISTRO="unknown"
    fi
    log_info "Sistema detectado: $OS ($DISTRO)"
}

# -----------------------------------------------------------------------------
# Detección de hardware
# -----------------------------------------------------------------------------
detect_hardware() {
    header "DETECCIÓN DE HARDWARE"

    # CPU
    if [[ -f /proc/cpuinfo ]]; then
        CPU_CORES=$(nproc 2>/dev/null || echo 1)
        CPU_MODEL=$(grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2 | sed 's/^ *//' 2>/dev/null || echo "Desconocida")
    else
        CPU_CORES=$(sysctl -n hw.ncpu 2>/dev/null || echo 1)
        CPU_MODEL=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Desconocida")
    fi

    # RAM
    if [[ -f /proc/meminfo ]]; then
        RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        RAM_GB=$((RAM_KB / 1024 / 1024))
    else
        RAM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1024/1024/1024)}' || echo 8)
    fi

    # GPU
    HAS_GPU=false
    GPU_INFO=""
    if command -v lspci &>/dev/null; then
        if lspci 2>/dev/null | grep -qiE "nvidia|amd|radeon|intel.*graphics"; then
            HAS_GPU=true
            GPU_INFO=$(lspci 2>/dev/null | grep -iE "vga|3d|display" | head -1 | cut -d: -f3 | sed 's/^ *//')
        fi
    fi

    echo "  CPU:    $CPU_MODEL ($CPU_CORES núcleos)"
    echo "  RAM:    ${RAM_GB} GB"
    echo "  GPU:    $([ "$HAS_GPU" = true ] && echo "Sí - $GPU_INFO" || echo "No detectada (CPU-only)")"

    # Recomendaciones basadas en hardware
    if [[ "$RAM_GB" -lt 8 ]]; then
        log_warn "RAM menor a 8 GB detectada. La clonación de voz puede ser lenta."
    fi
    if [[ "$CPU_CORES" -lt 4 ]]; then
        log_warn "Menos de 4 núcleos de CPU. El rendimiento será limitado."
    fi
    if [[ "$HAS_GPU" = false ]]; then
        log_info "Modo CPU-only: XTTS-v2 funcionará en CPU (más lento pero sin GPU)."
    fi

    echo ""
}

# -----------------------------------------------------------------------------
# Verificar Python
# -----------------------------------------------------------------------------
check_python() {
    header "VERIFICANDO PYTHON"

    PYTHON_CMD=""
    for cmd in python3 python python3.11 python3.10 python3.12; do
        if command -v "$cmd" &>/dev/null; then
            PYTHON_VER=$("$cmd" --version 2>&1 | awk '{print $2}')
            PYTHON_MAJOR=$(echo "$PYTHON_VER" | cut -d. -f1)
            PYTHON_MINOR=$(echo "$PYTHON_VER" | cut -d. -f2)
            if [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -ge 10 ]]; then
                PYTHON_CMD="$cmd"
                log_info "Python $PYTHON_VER encontrado en $($cmd -c 'import sys; print(sys.executable)')"
                break
            fi
        fi
    done

    if [[ -z "$PYTHON_CMD" ]]; then
        log_error "Python 3.10+ no encontrado. Instálalo primero e vuelve a ejecutar este script."
        case "$DISTRO" in
            debian) log_info "  sudo apt-get install python3 python3-venv python3-pip" ;;
            fedora) log_info "  sudo dnf install python3 python3-pip" ;;
            arch)   log_info "  sudo pacman -S python python-pip" ;;
            macos)  log_info "  brew install python@3.11" ;;
        esac
        exit 1
    fi

    export PYTHON_CMD
}

# -----------------------------------------------------------------------------
# Instalar dependencias del sistema
# -----------------------------------------------------------------------------
install_system_deps() {
    header "INSTALANDO DEPENDENCIAS DEL SISTEMA"

    case "$DISTRO" in
        debian)
            log_info "Instalando dependencias para Debian/Ubuntu..."
            sudo apt-get update -qq
            sudo apt-get install -y \
                python3-venv python3-pip python3-dev \
                ffmpeg libsndfile1 \
                tesseract-ocr libtesseract-dev \
                libgl1-mesa-glx libglib2.0-0 \
                libsm6 libxext6 libxrender-dev \
                libfontconfig1 libfreetype6 \
                git curl wget
            ;;
        fedora)
            log_info "Instalando dependencias para Fedora..."
            sudo dnf install -y \
                python3 python3-pip python3-devel \
                ffmpeg libsndfile \
                tesseract tesseract-devel \
                mesa-libGL glib2 \
                libSM libXext libXrender \
                fontconfig freetype \
                git curl wget
            ;;
        arch)
            log_info "Instalando dependencias para Arch Linux..."
            sudo pacman -S --needed --noconfirm \
                python python-pip python-venv \
                ffmpeg libsndfile \
                tesseract \
                mesa libgl libxext libxrender \
                fontconfig freetype2 \
                git curl wget
            ;;
        macos)
            log_info "Instalando dependencias para macOS..."
            if ! command -v brew &>/dev/null; then
                log_error "Homebrew no encontrado. Instálalo desde https://brew.sh"
                exit 1
            fi
            brew install python@3.11 ffmpeg libsndfile tesseract pkg-config
            ;;
        windows)
            log_warn "En Windows, asegúrate de tener instalado:"
            log_warn "  - Python 3.10+ (https://python.org)"
            log_warn "  - FFmpeg (https://ffmpeg.org)"
            log_warn "  - Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki)"
            ;;
        *)
            log_warn "Distribución no reconocida. Instala manualmente:"
            log_warn "  Python 3.10+, ffmpeg, libsndfile, tesseract-ocr"
            ;;
    esac

    log_ok "Dependencias del sistema instaladas"
}

# -----------------------------------------------------------------------------
# Crear entorno virtual
# -----------------------------------------------------------------------------
create_venv() {
    header "CREANDO ENTORNO VIRTUAL"

    local venv_dir="$SCRIPT_DIR/.venv"

    if [[ -d "$venv_dir" ]]; then
        log_info "Entorno virtual ya existe en .venv"
    else
        log_info "Creando entorno virtual en .venv..."
        "$PYTHON_CMD" -m venv "$venv_dir"
        log_ok "Entorno virtual creado"
    fi

    # Activar el entorno
    if [[ "$OS" == "windows" ]]; then
        source "$venv_dir/Scripts/activate"
    else
        source "$venv_dir/bin/activate"
    fi

    # Actualizar pip
    log_info "Actualizando pip..."
    python -m pip install --upgrade pip setuptools wheel --quiet

    export VENV_DIR="$venv_dir"
}

# -----------------------------------------------------------------------------
# Instalar dependencias de Python
# -----------------------------------------------------------------------------
install_python_deps() {
    header "INSTALANDO DEPENDENCIAS DE PYTHON"

    if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
        log_info "Instalando desde requirements.txt..."
        pip install -r "$SCRIPT_DIR/requirements.txt"
    else
        log_warn "requirements.txt no encontrado, instalando desde pyproject.toml..."
        pip install "$SCRIPT_DIR[dev]"
    fi

    log_ok "Dependencias de Python instaladas"
}

# -----------------------------------------------------------------------------
# Instalar el paquete VoxForge
# -----------------------------------------------------------------------------
install_voxforge() {
    header "INSTALANDO VOXFORGE"

    log_info "Instalando VoxForge en modo editable..."
    pip install -e "$SCRIPT_DIR"

    log_ok "VoxForge instalado"
}

# -----------------------------------------------------------------------------
# Descargar modelos XTTS-v2
# -----------------------------------------------------------------------------
download_models() {
    header "DESCARGANDO MODELOS XTTS-V2"

    log_info "Los modelos de XTTS-v2 se descargan automáticamente al usar el programa."
    log_info "Para precargar los modelos ahora, ejecuta:"
    echo "  voxforge model download"
    echo ""
    log_info "¿Deseas descargar los modelos ahora? (recomendado, ~2-3 GB) [y/N]"
    read -r response || true
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Descargando modelos XTTS-v2..."
        voxforge model download || log_warn "La descarga de modelos falló. Se reintentará al primer uso."
    else
        log_info "Los modelos se descargarán en el primer uso del programa."
    fi
}

# -----------------------------------------------------------------------------
# Verificación final
# -----------------------------------------------------------------------------
verify_install() {
    header "VERIFICACIÓN FINAL"

    log_info "Probando comandos de VoxForge..."
    voxforge --help &>/dev/null && log_ok "Comando 'voxforge' disponible" || log_warn "Comando 'voxforge' no encontrado en PATH"
    voxforge-gui --help &>/dev/null && log_ok "Comando 'voxforge-gui' disponible" || log_warn "Comando 'voxforge-gui' no encontrado en PATH"

    echo ""
    echo "============================================================"
    echo "  INSTALACIÓN COMPLETADA"
    echo "============================================================"
    echo ""
    echo "Para usar VoxForge:"
    echo "  - CLI:      voxforge --help"
    echo "  - GUI:      voxforge-gui  (o python gui.py)"
    echo "  - Modelos:  voxforge model download"
    echo ""
    echo "Para activar el entorno virtual manualmente:"
    echo "  source .venv/bin/activate"
    echo ""
    log_ok "¡VoxForge está listo para usar!"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
main() {
    header "VOXFORGE LOCAL - INSTALADOR AUTOMÁTICO"
    echo "Estudio de clonación de voz y narración 100% local/offline"
    echo ""

    detect_os
    detect_hardware
    check_python
    install_system_deps
    create_venv
    install_python_deps
    install_voxforge
    download_models
    verify_install
}

main "$@"