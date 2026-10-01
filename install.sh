#!/bin/bash
#
# AI-Connect Installation Script
# Installs either server mode (Bridge + MCP) or client mode (MCP only)
#
# Usage:
#   ./install.sh            # Interactive installation
#   ./install.sh --server   # Server mode (Bridge + MCP)
#   ./install.sh --client   # Client mode (MCP only)
#   ./install.sh --update   # Update without touching the config
#   ./install.sh --status   # Show status
#   ./install.sh --uninstall # Uninstall
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/ai-connect"

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
UPDATE_ONLY=false
STATUS_ONLY=false
UNINSTALL=false
SERVER_MODE=""  # "", "server" or "client"

for arg in "$@"; do
    case $arg in
        --server|-S)
            SERVER_MODE="server"
            ;;
        --client|-C)
            SERVER_MODE="client"
            ;;
        --update|-u)
            UPDATE_ONLY=true
            ;;
        --status|-s)
            STATUS_ONLY=true
            ;;
        --uninstall|--remove)
            UNINSTALL=true
            ;;
        --help|-h)
            echo "AI-Connect Install Script"
            echo ""
            echo "Usage:"
            echo "  ./install.sh            # Interactive installation"
            echo "  ./install.sh --server   # Server mode (Bridge + MCP)"
            echo "  ./install.sh --client   # Client mode (MCP only)"
            echo "  ./install.sh --update   # Update (detects the mode itself)"
            echo "  ./install.sh --status   # Show status"
            echo "  ./install.sh --uninstall # Uninstall"
            echo ""
            echo "Server mode: installs the Bridge Server + MCP HTTP server"
            echo "Client mode: installs only the MCP HTTP server (connects to a Bridge elsewhere)"
            echo ""
            exit 0
            ;;
    esac
done

# Detect whether and in which mode AI-Connect is installed
detect_mode() {
    if [[ -f "/etc/systemd/system/ai-connect.service" ]]; then
        echo "server"
    elif [[ -f "/etc/systemd/system/ai-connect-mcp.service" ]]; then
        echo "client"
    else
        echo ""
    fi
}

# Uninstall
do_uninstall() {
    local CURRENT_MODE=$(detect_mode)

    echo "=========================================="
    if [[ "$CURRENT_MODE" == "server" ]]; then
        echo "  AI-Connect Server Uninstall"
    else
        echo "  AI-Connect Client Uninstall"
    fi
    echo "=========================================="
    echo ""

    read -p "Really uninstall? [y/N]: " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[yY]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    echo ""

    # 1. Stop and disable services
    echo -e "${YELLOW}[1/4]${NC} Stopping services..."
    for SERVICE in ai-connect-mcp.service ai-connect.service; do
        if systemctl is-active --quiet $SERVICE 2>/dev/null; then
            sudo systemctl stop $SERVICE
            echo -e "  ${GREEN}$SERVICE stopped${NC}"
        fi
        if systemctl is-enabled --quiet $SERVICE 2>/dev/null; then
            sudo systemctl disable $SERVICE 2>/dev/null
        fi
    done

    # 2. Remove systemd unit files
    echo -e "${YELLOW}[2/4]${NC} Removing unit files..."
    for SERVICE in ai-connect.service ai-connect-mcp.service; do
        if [[ -f "/etc/systemd/system/$SERVICE" ]]; then
            sudo rm "/etc/systemd/system/$SERVICE"
            echo -e "  ${GREEN}$SERVICE removed${NC}"
        fi
    done
    sudo systemctl daemon-reload

    # 3. Remove PolicyKit rule
    echo -e "${YELLOW}[3/4]${NC} Removing PolicyKit rule..."
    if [[ -f "/etc/polkit-1/rules.d/50-ai-connect.rules" ]]; then
        sudo rm /etc/polkit-1/rules.d/50-ai-connect.rules
        sudo systemctl restart polkit.service
        echo -e "  ${GREEN}PolicyKit rule removed${NC}"
    else
        echo "  No PolicyKit rule present"
    fi

    # 4. Keep or delete the config?
    echo -e "${YELLOW}[4/4]${NC} Configuration..."
    if [[ -f "$CONFIG_DIR/config.yaml" ]]; then
        read -p "  Delete the config file too? [y/N]: " DELETE_CONFIG
        if [[ "$DELETE_CONFIG" =~ ^[yY]$ ]]; then
            rm -rf "$CONFIG_DIR"
            echo -e "  ${GREEN}Config deleted${NC}"
        else
            echo -e "  ${YELLOW}Config kept: $CONFIG_DIR${NC}"
        fi
    fi

    echo ""
    echo "=========================================="
    echo -e "  ${GREEN}Uninstall complete!${NC}"
    echo "=========================================="
    echo ""
    echo "Note: the venv directory was left in place."
    echo "To remove it: rm -rf $SCRIPT_DIR/venv"
    echo ""
    exit 0
}

# Status
show_status() {
    local CURRENT_MODE=$(detect_mode)

    echo ""
    if [[ "$CURRENT_MODE" == "server" ]]; then
        echo -e "${BLUE}=== AI-Connect Status (server mode) ===${NC}"
    elif [[ "$CURRENT_MODE" == "client" ]]; then
        echo -e "${BLUE}=== AI-Connect Status (client mode) ===${NC}"
    else
        echo -e "${BLUE}=== AI-Connect Status (not installed) ===${NC}"
    fi
    echo ""

    # Services
    if [[ "$CURRENT_MODE" == "server" ]]; then
        if systemctl is-active --quiet ai-connect.service 2>/dev/null; then
            echo -e "  ai-connect.service:     ${GREEN}● running${NC}"
        else
            echo -e "  ai-connect.service:     ${RED}○ stopped${NC}"
        fi
    fi

    if [[ -n "$CURRENT_MODE" ]]; then
        if systemctl is-active --quiet ai-connect-mcp.service 2>/dev/null; then
            echo -e "  ai-connect-mcp.service: ${GREEN}● running${NC}"
        else
            echo -e "  ai-connect-mcp.service: ${RED}○ stopped${NC}"
        fi
    fi

    # Config
    echo ""
    if [[ -f "$CONFIG_DIR/config.yaml" ]]; then
        echo -e "  Config: ${GREEN}$CONFIG_DIR/config.yaml${NC}"
        PEER_NAME=$(grep -E "^\s+name:" "$CONFIG_DIR/config.yaml" | head -1 | sed 's/.*: *"\?\([^"]*\)"\?/\1/')
        BRIDGE_HOST=$(grep -E "^\s+host:" "$CONFIG_DIR/config.yaml" | head -1 | sed 's/.*: *"\?\([^"]*\)"\?/\1/')
        echo -e "  Peer name: ${YELLOW}$PEER_NAME${NC}"
        echo -e "  Bridge Server: ${YELLOW}$BRIDGE_HOST${NC}"
    else
        echo -e "  Config: ${RED}missing${NC}"
    fi

    # PolicyKit
    echo ""
    if [[ -f "/etc/polkit-1/rules.d/50-ai-connect.rules" ]]; then
        echo -e "  PolicyKit: ${GREEN}installed${NC}"
    else
        echo -e "  PolicyKit: ${RED}not installed${NC}"
    fi

    echo ""
}

# Uninstall requested?
if $UNINSTALL; then
    do_uninstall
fi

# Status only?
if $STATUS_ONLY; then
    show_status
    exit 0
fi

# Update: detect the installed mode
if $UPDATE_ONLY; then
    SERVER_MODE=$(detect_mode)
    if [[ -z "$SERVER_MODE" ]]; then
        echo -e "${RED}Error: no installation found. Install first.${NC}"
        exit 1
    fi
fi

# Ask for the mode unless given as argument
if [[ -z "$SERVER_MODE" ]]; then
    echo "=========================================="
    echo "  AI-Connect Installation"
    echo "=========================================="
    echo ""
    echo "Which mode do you want to install?"
    echo ""
    echo -e "  ${YELLOW}1)${NC} Server - Bridge Server + MCP (the machine all others connect to)"
    echo -e "  ${YELLOW}2)${NC} Client - MCP only (connects to a Bridge Server elsewhere)"
    echo ""
    read -p "Choice [1/2]: " MODE_CHOICE

    case $MODE_CHOICE in
        1|s|S|server)
            SERVER_MODE="server"
            ;;
        2|c|C|client)
            SERVER_MODE="client"
            ;;
        *)
            echo -e "${RED}Invalid choice. Aborted.${NC}"
            exit 1
            ;;
    esac
    echo ""
fi

echo "=========================================="
if $UPDATE_ONLY; then
    if [[ "$SERVER_MODE" == "server" ]]; then
        echo "  AI-Connect Server Update"
    else
        echo "  AI-Connect Client Update"
    fi
else
    if [[ "$SERVER_MODE" == "server" ]]; then
        echo "  AI-Connect Server Installation"
    else
        echo "  AI-Connect Client Installation"
        echo ""
        echo -e "${YELLOW}Note:${NC} the Bridge Server must run on another machine."
    fi
fi
echo "=========================================="
echo ""

# Make sure we run inside the repository
if [[ "$SERVER_MODE" == "server" ]]; then
    if [[ ! -f "$SCRIPT_DIR/server/main.py" ]]; then
        echo -e "${RED}Error: server/main.py not found${NC}"
        exit 1
    fi
fi
if [[ ! -f "$SCRIPT_DIR/client/http_server.py" ]]; then
    echo -e "${RED}Error: client/http_server.py not found${NC}"
    exit 1
fi

# Number of steps
if [[ "$SERVER_MODE" == "server" ]]; then
    TOTAL_STEPS=6
else
    TOTAL_STEPS=5
fi

# 1. Create or update the Python venv
echo -e "${YELLOW}[1/$TOTAL_STEPS]${NC} Python Virtual Environment..."
if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    echo "  Creating venv..."
    python3 -m venv "$SCRIPT_DIR/venv"
else
    echo "  venv already exists"
fi

# 2. Install or update dependencies
echo -e "${YELLOW}[2/$TOTAL_STEPS]${NC} Python Dependencies..."
"$SCRIPT_DIR/venv/bin/pip" install -q --upgrade pip
"$SCRIPT_DIR/venv/bin/pip" install -q --upgrade -r "$SCRIPT_DIR/requirements.txt"
echo -e "  ${GREEN}Dependencies up to date${NC}"

# 3. Configuration
echo -e "${YELLOW}[3/$TOTAL_STEPS]${NC} Configuration..."
mkdir -p "$CONFIG_DIR"

if [[ -f "$CONFIG_DIR/config.yaml" ]]; then
    echo -e "  ${GREEN}Config already exists - not overwritten${NC}"
    if ! $UPDATE_ONLY; then
        read -p "  Create a new config? [y/N]: " RECREATE_CONFIG
        if [[ "$RECREATE_CONFIG" =~ ^[yY]$ ]]; then
            cp "$CONFIG_DIR/config.yaml" "$CONFIG_DIR/config.yaml.bak"
            echo "  Backup written: config.yaml.bak"
            rm "$CONFIG_DIR/config.yaml"
        fi
    fi
fi

if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
    # Name of the HTTP/SSE server in the network (the STDIO client for
    # Claude Code names itself Host:Project)
    read -p "  Peer name of this machine's HTTP/SSE server [$(hostname)]: " PEER_NAME
    PEER_NAME=${PEER_NAME:-$(hostname)}

    # bridge.host is read twice: the Bridge binds to it, the local MCP
    # clients connect to it. On the Bridge machine 0.0.0.0 serves both:
    # reachable from the network, and Linux routes a connect to 0.0.0.0
    # to the local machine. 127.0.0.1 would lock out every other machine.
    if [[ "$SERVER_MODE" == "server" ]]; then
        read -p "  Bridge listen address [0.0.0.0]: " BRIDGE_HOST
        BRIDGE_HOST=${BRIDGE_HOST:-0.0.0.0}
    else
        read -p "  IP or hostname of the Bridge machine: " BRIDGE_HOST
        if [[ -z "$BRIDGE_HOST" ]]; then
            echo -e "${RED}Without the Bridge address the client cannot connect. Aborted.${NC}"
            exit 1
        fi
    fi

    cat > "$CONFIG_DIR/config.yaml" << EOF
bridge:
  host: "$BRIDGE_HOST"
  port: 9999

peer:
  name: "$PEER_NAME"

mcp:
  host: "127.0.0.1"
  port: 9998
EOF
    echo -e "  ${GREEN}Config written: $CONFIG_DIR/config.yaml${NC}"
fi

# 4. Install systemd services
STEP=4
echo -e "${YELLOW}[$STEP/$TOTAL_STEPS]${NC} Systemd Services..."
echo "  (needs sudo)"

# Bridge Server service (server mode only)
if [[ "$SERVER_MODE" == "server" ]]; then
    sudo tee /etc/systemd/system/ai-connect.service > /dev/null << EOF
[Unit]
Description=AI-Connect Bridge Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python -m server.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    echo -e "  ${GREEN}ai-connect.service installed${NC}"
fi

# MCP HTTP server service (always)
sudo tee /etc/systemd/system/ai-connect-mcp.service > /dev/null << EOF
[Unit]
Description=AI-Connect MCP HTTP Server
After=network.target$(if [[ "$SERVER_MODE" == "server" ]]; then echo " ai-connect.service"; fi)

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python -m client.http_server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
echo -e "  ${GREEN}ai-connect-mcp.service installed${NC}"

# 5. Install PolicyKit rule
echo -e "${YELLOW}[5/$TOTAL_STEPS]${NC} PolicyKit rule..."

if [[ "$SERVER_MODE" == "server" ]]; then
    sudo tee /etc/polkit-1/rules.d/50-ai-connect.rules > /dev/null << EOF
// PolicyKit rule for the AI-Connect services
// Lets user '$USER' control them without sudo

polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "$USER" &&
        (action.lookup("unit") == "ai-connect.service" ||
         action.lookup("unit") == "ai-connect-mcp.service")) {
        return polkit.Result.YES;
    }
});
EOF
else
    sudo tee /etc/polkit-1/rules.d/50-ai-connect.rules > /dev/null << EOF
// PolicyKit rule for the AI-Connect MCP service
// Lets user '$USER' control them without sudo

polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "$USER" &&
        action.lookup("unit") == "ai-connect-mcp.service") {
        return polkit.Result.YES;
    }
});
EOF
fi

sudo chmod 644 /etc/polkit-1/rules.d/50-ai-connect.rules
sudo systemctl restart polkit.service
echo -e "  ${GREEN}PolicyKit rule installed${NC}"

# 6. Enable and (re)start services (step 6 in server mode, 5 in client mode)
if [[ "$SERVER_MODE" == "server" ]]; then
    echo -e "${YELLOW}[6/$TOTAL_STEPS]${NC} Enabling and starting services..."
else
    echo -e "${YELLOW}[5/$TOTAL_STEPS]${NC} Enabling and starting services..."
fi
sudo systemctl daemon-reload

if [[ "$SERVER_MODE" == "server" ]]; then
    sudo systemctl enable ai-connect.service ai-connect-mcp.service 2>/dev/null
    sudo systemctl restart ai-connect.service
    sleep 2
    sudo systemctl restart ai-connect-mcp.service
else
    sudo systemctl enable ai-connect-mcp.service 2>/dev/null
    sudo systemctl restart ai-connect-mcp.service
fi

echo ""
echo "=========================================="
if $UPDATE_ONLY; then
    echo -e "  ${GREEN}Update complete!${NC}"
else
    echo -e "  ${GREEN}Installation complete!${NC}"
fi
echo "=========================================="

show_status

echo "Commands:"
echo "  ./install.sh --status    # Show status"
echo "  ./install.sh --update    # Update"
echo "  ./install.sh --uninstall # Uninstall"
echo ""
echo "Logs:"
if [[ "$SERVER_MODE" == "server" ]]; then
    echo "  journalctl -u ai-connect.service -f"
fi
echo "  journalctl -u ai-connect-mcp.service -f"
echo ""
echo "Claude Code (one peer per session, named Host:Project):"
echo "  claude mcp add -s user ai-connect -- \"$SCRIPT_DIR/venv/bin/python\" \"$SCRIPT_DIR/client/server.py\""
echo ""
echo "Other MCP clients, e.g. VS Code (~/.config/Code/User/mcp.json, remote: ~/.vscode-server/data/User/mcp.json):"
echo '{'
echo '  "servers": {'
echo '    "ai-connect": {'
echo '      "type": "sse",'
echo '      "url": "http://127.0.0.1:9998/sse"'
echo '    }'
echo '  }'
echo '}'
echo ""
