#!/bin/bash
# BENCHCOM - Bootstrap installer and runner
# Usage: curl https://benchcom.example.com/benchcom.sh | bash
# Or: ./benchcom.sh [--api-url URL] [--api-token TOKEN] [--install-deps]

set -e

BENCHCOM_VERSION="1.1"
BENCHCOM_BASE_URL="${BENCHCOM_BASE_URL:-https://raw.githubusercontent.com/mkoskinen/benchcom/main}"

echo "================================"
echo "BENCHCOM v${BENCHCOM_VERSION}"
echo "================================"
echo ""

# Parse arguments for --install-deps flag
INSTALL_DEPS=0
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--install-deps" ]; then
        INSTALL_DEPS=1
    else
        ARGS+=("$arg")
    fi
done

# Detect package manager
detect_pkg_manager() {
    if command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v apt-get &> /dev/null; then
        echo "apt"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    elif command -v zypper &> /dev/null; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

# Install packages based on distro
install_packages() {
    local pkg_manager=$(detect_pkg_manager)
    echo "Detected package manager: $pkg_manager"

    case $pkg_manager in
        dnf)
            echo "Installing benchmark dependencies via dnf..."
            sudo dnf install -y p7zip p7zip-plugins openssl bc sysbench unzip curl ncurses-compat-libs
            ;;
        apt)
            echo "Installing benchmark dependencies via apt..."
            sudo apt-get update
            sudo apt-get install -y p7zip-full openssl bc sysbench unzip curl
            ;;
        pacman)
            echo "Installing benchmark dependencies via pacman..."
            sudo pacman -Sy --noconfirm p7zip openssl bc sysbench unzip curl
            ;;
        zypper)
            echo "Installing benchmark dependencies via zypper..."
            sudo zypper install -y p7zip openssl bc sysbench unzip curl
            ;;
        *)
            echo "Warning: Unknown package manager. Please install manually:"
            echo "  - 7zip (p7zip)"
            echo "  - openssl"
            echo "  - bc"
            echo "  - sysbench"
            echo "  - unzip"
            ;;
    esac
}

# Install PassMark PerformanceTest Linux
install_passmark() {
    local arch=$(uname -m)
    local url=""

    case $arch in
        x86_64)
            url="https://www.passmark.com/downloads/PerformanceTest_Linux_x86-64.zip"
            ;;
        aarch64)
            url="https://www.passmark.com/downloads/PerformanceTest_Linux_ARM64.zip"
            ;;
        armv7l|armhf)
            url="https://www.passmark.com/downloads/PerformanceTest_Linux_ARM32.zip"
            ;;
        *)
            echo "Warning: PassMark not available for architecture: $arch"
            return 1
            ;;
    esac

    echo "Downloading PassMark PerformanceTest for $arch..."
    local pt_dir="/opt/passmark"

    if [ -f "$pt_dir/pt_linux/pt_linux" ]; then
        echo "PassMark already installed at $pt_dir"
        return 0
    fi

    sudo mkdir -p "$pt_dir"
    local tmpzip=$(mktemp)

    if curl -fsSL "$url" -o "$tmpzip"; then
        sudo unzip -o "$tmpzip" -d "$pt_dir"
        sudo chmod +x "$pt_dir/pt_linux/pt_linux" 2>/dev/null || true
        rm -f "$tmpzip"
        echo "PassMark installed to $pt_dir/pt_linux/"
    else
        echo "Warning: Failed to download PassMark"
        rm -f "$tmpzip"
        return 1
    fi
}

# Install dependencies if requested
if [ "$INSTALL_DEPS" -eq 1 ]; then
    echo "Installing benchmark dependencies..."
    echo ""
    install_packages
    echo ""
    install_passmark
    echo ""
    echo "Dependencies installed."
    echo ""
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed"
    echo "Install with: dnf install python3  (or apt-get install python3)"
    exit 1
fi

PYTHON_CMD="python3"

# Check Python version (need 3.7+)
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info[1])')

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 7 ]; }; then
    echo "Error: Python 3.7+ required, found $PYTHON_VERSION"
    exit 1
fi

echo "Using Python $PYTHON_VERSION"

# Determine if we're running from a git repo (development mode)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/client/benchcom.py" ]; then
    echo "Development mode: using local client"
    CLIENT_DIR="$SCRIPT_DIR/client"
    CLEANUP_DIR=""
else
    # Create temp directory for remote mode
    TEMP_DIR=$(mktemp -d -t benchcom.XXXXXX)
    CLIENT_DIR="$TEMP_DIR"
    CLEANUP_DIR="$TEMP_DIR"

    echo "Downloading to temp directory: $TEMP_DIR"

    # Cleanup on exit
    trap "rm -rf '$TEMP_DIR'" EXIT

    # Download client files
    if command -v curl &> /dev/null; then
        curl -fsSL "${BENCHCOM_BASE_URL}/client/benchcom.py" -o "$CLIENT_DIR/benchcom.py"
    elif command -v wget &> /dev/null; then
        wget -q "${BENCHCOM_BASE_URL}/client/benchcom.py" -O "$CLIENT_DIR/benchcom.py"
    else
        echo "Error: curl or wget required"
        exit 1
    fi

    chmod +x "$CLIENT_DIR/benchcom.py"
fi

# Check if requests library is available (needed for API submission)
if ! $PYTHON_CMD -c "import requests" 2>/dev/null; then
    echo ""
    echo "Note: 'requests' library not found."
    echo "Benchmarks will run but API submission requires: pip install requests"
    echo ""
fi

# Run the benchmark
echo ""
echo "================================"
echo "Running Benchmark"
echo "================================"
echo ""

cd "$CLIENT_DIR"
$PYTHON_CMD benchcom.py "$@"
