#!/bin/bash
#
# AI-Connect Client Installation Script
# Installiert nur den MCP HTTP Server (NICHT den Bridge Server)
# Für Rechner die sich zum zentralen Bridge Server verbinden
#
# Verwendung:
#   ./install-client.sh            # Vollinstallation
#   ./install-client.sh --update   # Nur Services aktualisieren
#   ./install-client.sh --status   # Zeigt nur Status an
#   ./install-client.sh --uninstall # Deinstallation
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

for arg in "$@"; do
    case $arg in
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
            echo "AI-Connect Client Install Script"
            echo ""
            echo "Installiert nur den MCP HTTP Server (Client-Modus)."
            echo "Der Bridge Server muss auf einem anderen Rechner laufen."
            echo ""
            echo "Verwendung:"
            echo "  ./install-client.sh            # Vollinstallation"
            echo "  ./install-client.sh --update   # Nur Services aktualisieren"
            echo "  ./install-client.sh --status   # Status anzeigen"
            echo "  ./install-client.sh --uninstall # Deinstallation"
            echo ""
            exit 0
            ;;
    esac
done

# Uninstall-Funktion
do_uninstall() {
    echo "=========================================="
    echo "  AI-Connect Client Deinstallation"
    echo "=========================================="
    echo ""

    read -p "Wirklich deinstallieren? [j/N]: " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[jJyY]$ ]]; then
        echo "Abgebrochen."
        exit 0
    fi
    echo ""

    # 1. Service stoppen und deaktivieren
    echo -e "${YELLOW}[1/4]${NC} Service stoppen..."
    if systemctl is-active --quiet ai-connect-mcp.service 2>/dev/null; then
        sudo systemctl stop ai-connect-mcp.service
        echo -e "  ${GREEN}Service gestoppt${NC}"
    else
        echo "  Service läuft nicht"
    fi

    if systemctl is-enabled --quiet ai-connect-mcp.service 2>/dev/null; then
        sudo systemctl disable ai-connect-mcp.service 2>/dev/null
        echo -e "  ${GREEN}Service deaktiviert${NC}"
    fi

    # 2. Systemd Service-Datei entfernen
    echo -e "${YELLOW}[2/4]${NC} Service-Datei entfernen..."
    if [[ -f "/etc/systemd/system/ai-connect-mcp.service" ]]; then
        sudo rm /etc/systemd/system/ai-connect-mcp.service
        sudo systemctl daemon-reload
        echo -e "  ${GREEN}Service-Datei entfernt${NC}"
    else
        echo "  Service-Datei existiert nicht"
    fi

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

# Uninstall aufrufen?
if $UNINSTALL; then
    do_uninstall
fi

# Status-Funktion
show_status() {
    echo ""
    echo -e "${BLUE}=== AI-Connect Client Status ===${NC}"
    echo ""

    # MCP Service
    if systemctl is-active --quiet ai-connect-mcp.service 2>/dev/null; then
        echo -e "  ai-connect-mcp.service: ${GREEN}● läuft${NC}"
    else
        echo -e "  ai-connect-mcp.service: ${RED}○ gestoppt${NC}"
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

# Nur Status anzeigen?
if $STATUS_ONLY; then
    show_status
    exit 0
fi

echo "=========================================="
if $UPDATE_ONLY; then
    echo "  AI-Connect Client Update"
else
    echo "  AI-Connect Client Installation"
fi
echo "=========================================="
echo ""
echo -e "${YELLOW}Hinweis:${NC} Dies installiert nur den MCP Client."
echo "         Der Bridge Server muss separat laufen."
echo ""

# Prüfe ob wir im richtigen Verzeichnis sind
if [[ ! -f "$SCRIPT_DIR/client/http_server.py" ]]; then
    echo -e "${RED}Fehler: Script muss aus dem AI-Connect Projektverzeichnis ausgeführt werden${NC}"
    exit 1
fi

# 1. Python venv erstellen/aktualisieren
echo -e "${YELLOW}[1/5]${NC} Python Virtual Environment..."
if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    echo "  Erstelle venv..."
    python3 -m venv "$SCRIPT_DIR/venv"
else
    echo "  venv existiert bereits"
fi

# 2. Dependencies installieren/aktualisieren
echo -e "${YELLOW}[2/5]${NC} Python Dependencies..."
"$SCRIPT_DIR/venv/bin/pip" install -q --upgrade pip
"$SCRIPT_DIR/venv/bin/pip" install -q --upgrade websockets pyyaml fastmcp
echo -e "  ${GREEN}Dependencies aktualisiert${NC}"

# 3. Config-Verzeichnis erstellen
echo -e "${YELLOW}[3/5]${NC} Konfiguration..."
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
    read -p "  Bridge Server Host [192.168.0.252]: " BRIDGE_HOST
    BRIDGE_HOST=${BRIDGE_HOST:-192.168.0.252}

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

# 4. Systemd Service installieren (nur MCP, kein Bridge)
echo -e "${YELLOW}[4/5]${NC} Systemd Service..."

SERVICE_EXISTS=false
if [[ -f "/etc/systemd/system/ai-connect-mcp.service" ]]; then
    SERVICE_EXISTS=true
fi

echo "  (benötigt sudo-Rechte)"

# MCP HTTP Server Service
sudo tee /etc/systemd/system/ai-connect-mcp.service > /dev/null << EOF
[Unit]
Description=AI-Connect MCP HTTP Server
After=network.target

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

if $SERVICE_EXISTS; then
    echo -e "  ${GREEN}Service aktualisiert${NC}"
else
    echo -e "  ${GREEN}Service installiert${NC}"
fi

# 5. PolicyKit Regel installieren
echo -e "${YELLOW}[5/5]${NC} PolicyKit Regel..."

POLKIT_EXISTS=false
if [[ -f "/etc/polkit-1/rules.d/50-ai-connect.rules" ]]; then
    POLKIT_EXISTS=true
fi

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

sudo chmod 644 /etc/polkit-1/rules.d/50-ai-connect.rules

# PolicyKit neu laden
sudo systemctl restart polkit.service

if $POLKIT_EXISTS; then
    echo -e "  ${GREEN}PolicyKit Regel aktualisiert${NC}"
else
    echo -e "  ${GREEN}PolicyKit Regel installiert${NC}"
fi

# Service aktivieren und (neu)starten
echo ""
echo "Service aktivieren und starten..."
sudo systemctl daemon-reload
sudo systemctl enable ai-connect-mcp.service 2>/dev/null

if $UPDATE_ONLY || $SERVICE_EXISTS; then
    sudo systemctl restart ai-connect-mcp.service
else
    sudo systemctl start ai-connect-mcp.service
fi

echo ""
echo "=========================================="
if $UPDATE_ONLY; then
    echo -e "  ${GREEN}Client Update abgeschlossen!${NC}"
else
    echo -e "  ${GREEN}Client Installation abgeschlossen!${NC}"
fi
echo "=========================================="

show_status

echo "Befehle:"
echo "  ./install-client.sh --status  # Status anzeigen"
echo "  ./install-client.sh --update  # Update durchführen"
echo ""
echo "Logs:"
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
