#!/bin/bash
#
# AI-Connect Installation Script
# Installiert entweder Server (Bridge + MCP) oder Client (nur MCP)
#
# Verwendung:
#   ./install.sh            # Interaktive Installation
#   ./install.sh --server   # Server-Modus (Bridge + MCP)
#   ./install.sh --client   # Client-Modus (nur MCP)
#   ./install.sh --update   # Update ohne Config-Änderung
#   ./install.sh --status   # Status anzeigen
#   ./install.sh --uninstall # Deinstallation
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/ai-connect"

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Argumente parsen
UPDATE_ONLY=false
STATUS_ONLY=false
UNINSTALL=false
SERVER_MODE=""  # "", "server", oder "client"

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
            echo "Verwendung:"
            echo "  ./install.sh            # Interaktive Installation"
            echo "  ./install.sh --server   # Server-Modus (Bridge + MCP)"
            echo "  ./install.sh --client   # Client-Modus (nur MCP)"
            echo "  ./install.sh --update   # Update (erkennt Modus automatisch)"
            echo "  ./install.sh --status   # Status anzeigen"
            echo "  ./install.sh --uninstall # Deinstallation"
            echo ""
            echo "Server-Modus: Installiert Bridge Server + MCP HTTP Server"
            echo "Client-Modus: Installiert nur MCP HTTP Server (verbindet zu externem Bridge)"
            echo ""
            exit 0
            ;;
    esac
done

# Erkennen ob bereits installiert und welcher Modus
detect_mode() {
    if [[ -f "/etc/systemd/system/ai-connect.service" ]]; then
        echo "server"
    elif [[ -f "/etc/systemd/system/ai-connect-mcp.service" ]]; then
        echo "client"
    else
        echo ""
    fi
}

# Uninstall-Funktion
do_uninstall() {
    local CURRENT_MODE=$(detect_mode)

    echo "=========================================="
    if [[ "$CURRENT_MODE" == "server" ]]; then
        echo "  AI-Connect Server Deinstallation"
    else
        echo "  AI-Connect Client Deinstallation"
    fi
    echo "=========================================="
    echo ""

    read -p "Wirklich deinstallieren? [j/N]: " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[jJyY]$ ]]; then
        echo "Abgebrochen."
        exit 0
    fi
    echo ""

    # 1. Services stoppen und deaktivieren
    echo -e "${YELLOW}[1/4]${NC} Services stoppen..."
    for SERVICE in ai-connect-mcp.service ai-connect.service; do
        if systemctl is-active --quiet $SERVICE 2>/dev/null; then
            sudo systemctl stop $SERVICE
            echo -e "  ${GREEN}$SERVICE gestoppt${NC}"
        fi
        if systemctl is-enabled --quiet $SERVICE 2>/dev/null; then
            sudo systemctl disable $SERVICE 2>/dev/null
        fi
    done

    # 2. Systemd Service-Dateien entfernen
    echo -e "${YELLOW}[2/4]${NC} Service-Dateien entfernen..."
    for SERVICE in ai-connect.service ai-connect-mcp.service; do
        if [[ -f "/etc/systemd/system/$SERVICE" ]]; then
            sudo rm "/etc/systemd/system/$SERVICE"
            echo -e "  ${GREEN}$SERVICE entfernt${NC}"
        fi
    done
    sudo systemctl daemon-reload

    # 3. PolicyKit Regel entfernen
    echo -e "${YELLOW}[3/4]${NC} PolicyKit Regel entfernen..."
    if [[ -f "/etc/polkit-1/rules.d/50-ai-connect.rules" ]]; then
        sudo rm /etc/polkit-1/rules.d/50-ai-connect.rules
        sudo systemctl restart polkit.service
        echo -e "  ${GREEN}PolicyKit Regel entfernt${NC}"
    else
        echo "  PolicyKit Regel existiert nicht"
    fi

    # 4. Config behalten oder löschen?
    echo -e "${YELLOW}[4/4]${NC} Konfiguration..."
    if [[ -f "$CONFIG_DIR/config.yaml" ]]; then
        read -p "  Config-Datei auch löschen? [j/N]: " DELETE_CONFIG
        if [[ "$DELETE_CONFIG" =~ ^[jJyY]$ ]]; then
            rm -rf "$CONFIG_DIR"
            echo -e "  ${GREEN}Config gelöscht${NC}"
        else
            echo -e "  ${YELLOW}Config behalten: $CONFIG_DIR${NC}"
        fi
    fi

    echo ""
    echo "=========================================="
    echo -e "  ${GREEN}Deinstallation abgeschlossen!${NC}"
    echo "=========================================="
    echo ""
    echo "Hinweis: Das venv-Verzeichnis wurde nicht gelöscht."
    echo "Falls gewünscht: rm -rf $SCRIPT_DIR/venv"
    echo ""
    exit 0
}

# Status-Funktion
show_status() {
    local CURRENT_MODE=$(detect_mode)

    echo ""
    if [[ "$CURRENT_MODE" == "server" ]]; then
        echo -e "${BLUE}=== AI-Connect Status (Server-Modus) ===${NC}"
    elif [[ "$CURRENT_MODE" == "client" ]]; then
        echo -e "${BLUE}=== AI-Connect Status (Client-Modus) ===${NC}"
    else
        echo -e "${BLUE}=== AI-Connect Status (nicht installiert) ===${NC}"
    fi
    echo ""

    # Services
    if [[ "$CURRENT_MODE" == "server" ]]; then
        if systemctl is-active --quiet ai-connect.service 2>/dev/null; then
            echo -e "  ai-connect.service:     ${GREEN}● läuft${NC}"
        else
            echo -e "  ai-connect.service:     ${RED}○ gestoppt${NC}"
        fi
    fi

    if [[ -n "$CURRENT_MODE" ]]; then
        if systemctl is-active --quiet ai-connect-mcp.service 2>/dev/null; then
            echo -e "  ai-connect-mcp.service: ${GREEN}● läuft${NC}"
        else
            echo -e "  ai-connect-mcp.service: ${RED}○ gestoppt${NC}"
        fi
    fi

    # Config
    echo ""
    if [[ -f "$CONFIG_DIR/config.yaml" ]]; then
        echo -e "  Config: ${GREEN}$CONFIG_DIR/config.yaml${NC}"
        PEER_NAME=$(grep -E "^\s+name:" "$CONFIG_DIR/config.yaml" | head -1 | sed 's/.*: *"\?\([^"]*\)"\?/\1/')
        BRIDGE_HOST=$(grep -E "^\s+host:" "$CONFIG_DIR/config.yaml" | head -1 | sed 's/.*: *"\?\([^"]*\)"\?/\1/')
        echo -e "  Peer-Name: ${YELLOW}$PEER_NAME${NC}"
        echo -e "  Bridge Server: ${YELLOW}$BRIDGE_HOST${NC}"
    else
        echo -e "  Config: ${RED}nicht vorhanden${NC}"
    fi

    # PolicyKit
    echo ""
    if [[ -f "/etc/polkit-1/rules.d/50-ai-connect.rules" ]]; then
        echo -e "  PolicyKit: ${GREEN}installiert${NC}"
    else
        echo -e "  PolicyKit: ${RED}nicht installiert${NC}"
    fi

    echo ""
}

# Uninstall aufrufen?
if $UNINSTALL; then
    do_uninstall
fi

# Nur Status anzeigen?
if $STATUS_ONLY; then
    show_status
    exit 0
fi

# Bei Update: Modus automatisch erkennen
if $UPDATE_ONLY; then
    SERVER_MODE=$(detect_mode)
    if [[ -z "$SERVER_MODE" ]]; then
        echo -e "${RED}Fehler: Keine Installation gefunden. Führe erst eine Installation durch.${NC}"
        exit 1
    fi
fi

# Modus abfragen wenn nicht per Argument gesetzt
if [[ -z "$SERVER_MODE" ]]; then
    echo "=========================================="
    echo "  AI-Connect Installation"
    echo "=========================================="
    echo ""
    echo "Welchen Modus möchtest du installieren?"
    echo ""
    echo -e "  ${YELLOW}1)${NC} Server - Bridge Server + MCP (für den Hauptrechner)"
    echo -e "  ${YELLOW}2)${NC} Client - Nur MCP (verbindet zu externem Bridge Server)"
    echo ""
    read -p "Auswahl [1/2]: " MODE_CHOICE

    case $MODE_CHOICE in
        1|s|S|server)
            SERVER_MODE="server"
            ;;
        2|c|C|client)
            SERVER_MODE="client"
            ;;
        *)
            echo -e "${RED}Ungültige Auswahl. Abgebrochen.${NC}"
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
        echo -e "${YELLOW}Hinweis:${NC} Der Bridge Server muss separat laufen."
    fi
fi
echo "=========================================="
echo ""

# Prüfe ob wir im richtigen Verzeichnis sind
if [[ "$SERVER_MODE" == "server" ]]; then
    if [[ ! -f "$SCRIPT_DIR/server/websocket_server.py" ]]; then
        echo -e "${RED}Fehler: server/websocket_server.py nicht gefunden${NC}"
        exit 1
    fi
fi
if [[ ! -f "$SCRIPT_DIR/client/http_server.py" ]]; then
    echo -e "${RED}Fehler: client/http_server.py nicht gefunden${NC}"
    exit 1
fi

# Anzahl der Schritte
if [[ "$SERVER_MODE" == "server" ]]; then
    TOTAL_STEPS=6
else
    TOTAL_STEPS=5
fi

# 1. Python venv erstellen/aktualisieren
echo -e "${YELLOW}[1/$TOTAL_STEPS]${NC} Python Virtual Environment..."
if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    echo "  Erstelle venv..."
    python3 -m venv "$SCRIPT_DIR/venv"
else
    echo "  venv existiert bereits"
fi

# 2. Dependencies installieren/aktualisieren
echo -e "${YELLOW}[2/$TOTAL_STEPS]${NC} Python Dependencies..."
"$SCRIPT_DIR/venv/bin/pip" install -q --upgrade pip
"$SCRIPT_DIR/venv/bin/pip" install -q --upgrade websockets pyyaml fastmcp
echo -e "  ${GREEN}Dependencies aktualisiert${NC}"

# 3. Config-Verzeichnis erstellen
echo -e "${YELLOW}[3/$TOTAL_STEPS]${NC} Konfiguration..."
mkdir -p "$CONFIG_DIR"

if [[ -f "$CONFIG_DIR/config.yaml" ]]; then
    echo -e "  ${GREEN}Config existiert bereits - wird nicht überschrieben${NC}"
    if ! $UPDATE_ONLY; then
        read -p "  Config neu erstellen? [j/N]: " RECREATE_CONFIG
        if [[ "$RECREATE_CONFIG" =~ ^[jJyY]$ ]]; then
            cp "$CONFIG_DIR/config.yaml" "$CONFIG_DIR/config.yaml.bak"
            echo "  Backup erstellt: config.yaml.bak"
            rm "$CONFIG_DIR/config.yaml"
        fi
    fi
fi

if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
    # Frage nach Peer-Name
    read -p "  Peer-Name für diesen Rechner [$(hostname)]: " PEER_NAME
    PEER_NAME=${PEER_NAME:-$(hostname)}

    # Frage nach Bridge-Host
    if [[ "$SERVER_MODE" == "server" ]]; then
        DEFAULT_HOST="127.0.0.1"
    else
        DEFAULT_HOST="192.168.0.252"
    fi
    read -p "  Bridge Server Host [$DEFAULT_HOST]: " BRIDGE_HOST
    BRIDGE_HOST=${BRIDGE_HOST:-$DEFAULT_HOST}

    cat > "$CONFIG_DIR/config.yaml" << EOF
bridge:
  host: "$BRIDGE_HOST"
  port: 9999

peer:
  name: "$PEER_NAME"
  auto_connect: true

mcp:
  host: "127.0.0.1"
  port: 9998
EOF
    echo -e "  ${GREEN}Config erstellt: $CONFIG_DIR/config.yaml${NC}"
fi

# 4. Systemd Services installieren
STEP=4
echo -e "${YELLOW}[$STEP/$TOTAL_STEPS]${NC} Systemd Services..."
echo "  (benötigt sudo-Rechte)"

# Bridge Server Service (nur im Server-Modus)
if [[ "$SERVER_MODE" == "server" ]]; then
    sudo tee /etc/systemd/system/ai-connect.service > /dev/null << EOF
[Unit]
Description=AI-Connect Bridge Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python -m server.websocket_server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    echo -e "  ${GREEN}ai-connect.service installiert${NC}"
fi

# MCP HTTP Server Service (immer)
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
echo -e "  ${GREEN}ai-connect-mcp.service installiert${NC}"

# 5. PolicyKit Regel installieren
echo -e "${YELLOW}[5/$TOTAL_STEPS]${NC} PolicyKit Regel..."

if [[ "$SERVER_MODE" == "server" ]]; then
    sudo tee /etc/polkit-1/rules.d/50-ai-connect.rules > /dev/null << 'EOF'
// PolicyKit Regel für AI-Connect Services
// Erlaubt User 'mp' die Steuerung ohne sudo

polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "mp" &&
        (action.lookup("unit") == "ai-connect.service" ||
         action.lookup("unit") == "ai-connect-mcp.service")) {
        return polkit.Result.YES;
    }
});
EOF
else
    sudo tee /etc/polkit-1/rules.d/50-ai-connect.rules > /dev/null << 'EOF'
// PolicyKit Regel für AI-Connect MCP Service
// Erlaubt User 'mp' die Steuerung ohne sudo

polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "mp" &&
        action.lookup("unit") == "ai-connect-mcp.service") {
        return polkit.Result.YES;
    }
});
EOF
fi

sudo chmod 644 /etc/polkit-1/rules.d/50-ai-connect.rules
sudo systemctl restart polkit.service
echo -e "  ${GREEN}PolicyKit Regel installiert${NC}"

# 6. Services aktivieren und (neu)starten (nur bei Server-Modus Schritt 6)
if [[ "$SERVER_MODE" == "server" ]]; then
    echo -e "${YELLOW}[6/$TOTAL_STEPS]${NC} Services aktivieren und starten..."
else
    echo -e "${YELLOW}[5/$TOTAL_STEPS]${NC} Services aktivieren und starten..."
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
    echo -e "  ${GREEN}Update abgeschlossen!${NC}"
else
    echo -e "  ${GREEN}Installation abgeschlossen!${NC}"
fi
echo "=========================================="

show_status

echo "Befehle:"
echo "  ./install.sh --status    # Status anzeigen"
echo "  ./install.sh --update    # Update durchführen"
echo "  ./install.sh --uninstall # Deinstallieren"
echo ""
echo "Logs:"
if [[ "$SERVER_MODE" == "server" ]]; then
    echo "  journalctl -u ai-connect.service -f"
fi
echo "  journalctl -u ai-connect-mcp.service -f"
echo ""
echo "VS Code MCP Konfiguration (~/.config/Code/User/settings.json):"
echo '  "mcp": {'
echo '    "servers": {'
echo '      "ai-connect": {'
echo '        "type": "http",'
echo '        "url": "http://127.0.0.1:9998/mcp"'
echo '      }'
echo '    }'
echo '  }'
echo ""
