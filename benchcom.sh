#!/bin/bash
# BENCHCOM - Bootstrap installer and runner
# Usage: curl https://benchcom.example.com/benchcom.sh | bash
# Or: ./benchcom.sh [--api-url URL] [--api-token TOKEN] [--api-username USER --api-password PASS] [--no-install-deps]

set -e

BENCHCOM_VERSION="1.1"
BENCHCOM_BASE_URL="${BENCHCOM_BASE_URL:-https://raw.githubusercontent.com/mkoskinen/benchcom/main}"

# Print ASCII logo
cat << 'EOF'

██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗ ██████╗ ██████╗ ███╗   ███╗
██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║██╔════╝██╔═══██╗████╗ ████║
██████╔╝█████╗  ██╔██╗ ██║██║     ███████║██║     ██║   ██║██╔████╔██║
██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║██║     ██║   ██║██║╚██╔╝██║
██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║╚██████╗╚██████╔╝██║ ╚═╝ ██║
╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝     ╚═╝

EOF
echo "v${BENCHCOM_VERSION} - Universal Benchmark Suite"
echo ""

# Parse arguments - install deps by default, --no-install-deps to skip
INSTALL_DEPS=1
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--no-install-deps" ]; then
        INSTALL_DEPS=0
    elif [ "$arg" = "--install-deps" ]; then
        # Keep for backwards compatibility
        INSTALL_DEPS=1
    else
        ARGS+=("$arg")
    fi
done

# Detect package manager
detect_pkg_manager() {
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "brew"
    elif command -v dnf &> /dev/null; then
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
            sudo dnf install -y p7zip p7zip-plugins openssl bc sysbench unzip curl zstd ncurses-compat-libs python3-requests
            ;;
        apt)
            echo "Installing benchmark dependencies via apt..."
            sudo apt-get update
            sudo apt-get install -y p7zip-full openssl bc sysbench unzip curl zstd python3-requests
            ;;
        pacman)
            echo "Installing benchmark dependencies via pacman..."
            sudo pacman -Sy --noconfirm p7zip openssl bc sysbench unzip curl zstd python-requests
            ;;
        zypper)
            echo "Installing benchmark dependencies via zypper..."
            sudo zypper install -y p7zip openssl bc sysbench unzip curl zstd python3-requests
            ;;
        brew)
            echo "Installing benchmark dependencies via Homebrew..."
            brew install p7zip openssl bc sysbench unzip curl zstd python3
            pip3 install --user requests
            ;;
        *)
            echo "Warning: Unknown package manager. Please install manually:"
            echo "  - 7zip (p7zip)"
            echo "  - openssl"
            echo "  - bc"
            echo "  - sysbench"
            echo "  - unzip"
            echo "  - zstd"
            echo "  - python3-requests"
            ;;
    esac
}

# Install PassMark PerformanceTest
install_passmark() {
    local arch=$(uname -m)
    local os=$(uname)
    local url=""
    local pt_dir="/opt/passmark"
    local pt_binary=""

    if [[ "$os" == "Darwin" ]]; then
        # macOS - download CLI tool from PassMark
        local pt_mac_dir="$HOME/.cache/benchcom"
        local pt_mac_bin="$pt_mac_dir/pt_mac"

        # Check if already installed
        if [ -f "$pt_mac_bin" ]; then
            echo "PassMark CLI already installed at $pt_mac_bin"
            return 0
        fi

        # Single universal download for macOS
        url="https://www.passmark.com/downloads/PerformanceTest_Mac_CMD.zip"

        echo "Downloading PassMark CLI for macOS ($arch)..."
        mkdir -p "$pt_mac_dir"
        local tmpzip=$(mktemp)
        local tmpdir=$(mktemp -d)

        if curl -fsSL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)" "$url" -o "$tmpzip"; then
            unzip -o "$tmpzip" -d "$tmpdir" 2>/dev/null
            # Find pt_mac binary in extracted files
            local found_binary=$(find "$tmpdir" -name "pt_mac" -type f 2>/dev/null | head -1)
            if [ -n "$found_binary" ]; then
                cp "$found_binary" "$pt_mac_bin"
                chmod +x "$pt_mac_bin"
                echo "PassMark CLI installed to $pt_mac_bin"
                # Remove quarantine attribute if present
                xattr -d com.apple.quarantine "$pt_mac_bin" 2>/dev/null || true
            else
                echo "Warning: pt_mac binary not found in download"
            fi
            rm -rf "$tmpdir" "$tmpzip"
        else
            echo "Warning: Failed to download PassMark CLI"
            rm -f "$tmpzip"
            rm -rf "$tmpdir"
            return 1
        fi
        return 0
    fi

    # Linux
    case $arch in
        x86_64)
            url="https://www.passmark.com/downloads/PerformanceTest_Linux_x86-64.zip"
            pt_binary="PerformanceTest_Linux_x86-64"
            ;;
        aarch64)
            url="https://www.passmark.com/downloads/PerformanceTest_Linux_ARM64.zip"
            pt_binary="PerformanceTest_Linux_ARM64"
            ;;
        armv7l|armhf)
            url="https://www.passmark.com/downloads/PerformanceTest_Linux_ARM32.zip"
            pt_binary="PerformanceTest_Linux_ARM32"
            ;;
        *)
            echo "Warning: PassMark not available for architecture: $arch"
            return 1
            ;;
    esac

    echo "Downloading PassMark PerformanceTest for $arch..."

    # Create ncurses5 symlinks if needed (for systems with only ncurses6)
    # Do this regardless of whether PassMark is already installed
    create_ncurses_symlinks() {
        local lib_dir=""
        if [ "$arch" = "aarch64" ]; then
            lib_dir="/usr/lib/aarch64-linux-gnu"
        elif [ "$arch" = "x86_64" ]; then
            lib_dir="/usr/lib/x86_64-linux-gnu"
        fi

        if [ -n "$lib_dir" ] && [ -d "$lib_dir" ]; then
            if [ -f "$lib_dir/libncurses.so.6" ] && [ ! -f "$lib_dir/libncurses.so.5" ]; then
                echo "Creating libncurses.so.5 symlink..."
                sudo ln -sf "$lib_dir/libncurses.so.6" "$lib_dir/libncurses.so.5"
            fi
            if [ -f "$lib_dir/libtinfo.so.6" ] && [ ! -f "$lib_dir/libtinfo.so.5" ]; then
                echo "Creating libtinfo.so.5 symlink..."
                sudo ln -sf "$lib_dir/libtinfo.so.6" "$lib_dir/libtinfo.so.5"
            fi
        fi
    }

    # Check if already installed (may be in subdirectory from zip)
    if [ -f "$pt_dir/pt_linux/pt_linux" ] || [ -f "$pt_dir/$pt_binary" ] || [ -f "$pt_dir/PerformanceTest/$pt_binary" ]; then
        echo "PassMark already installed at $pt_dir"
        # Still create symlinks in case they're missing
        create_ncurses_symlinks
        return 0
    fi

    sudo mkdir -p "$pt_dir"
    local tmpzip=$(mktemp)

    if curl -fsSL -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" "$url" -o "$tmpzip"; then
        sudo unzip -o "$tmpzip" -d "$pt_dir"
        # Find and make executable the binary (may be in subdirectory)
        local found_binary=""
        for binary_path in "$pt_dir/$pt_binary" "$pt_dir/PerformanceTest/$pt_binary"; do
            if [ -f "$binary_path" ]; then
                found_binary="$binary_path"
                sudo chmod +x "$binary_path"
                break
            fi
        done
        if [ -n "$found_binary" ]; then
            echo "PassMark binary found at $found_binary"
        fi

        # Create ncurses symlinks
        create_ncurses_symlinks

        rm -f "$tmpzip"
        echo "PassMark installed to $pt_dir/"
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
    install_passmark || true  # PassMark is optional, continue if unavailable
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
cd "$CLIENT_DIR"
$PYTHON_CMD benchcom.py "${ARGS[@]}"
