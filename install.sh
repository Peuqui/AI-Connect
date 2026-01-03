#!/bin/bash
#
# AI-Connect Installation Script
# Installiert Bridge Server, MCP HTTP Server und PolicyKit-Regeln
#
# Verwendung:
#   ./install.sh          # Vollinstallation (fragt nach Config)
#   ./install.sh --update # Nur Services aktualisieren (Config bleibt)
#   ./install.sh --status # Zeigt nur Status an
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

for arg in "$@"; do
    case $arg in
        --update|-u)
            UPDATE_ONLY=true
            ;;
        --status|-s)
            STATUS_ONLY=true
            ;;
        --help|-h)
            echo "AI-Connect Install Script"
            echo ""
            echo "Verwendung:"
            echo "  ./install.sh          # Vollinstallation"
            echo "  ./install.sh --update # Nur Services aktualisieren"
            echo "  ./install.sh --status # Status anzeigen"
            echo ""
            exit 0
            ;;
    esac
done

# Status-Funktion
show_status() {
    echo ""
    echo -e "${BLUE}=== AI-Connect Status ===${NC}"
    echo ""

    # Services
    if systemctl is-active --quiet ai-connect.service 2>/dev/null; then
        echo -e "  ai-connect.service:     ${GREEN}● läuft${NC}"
    else
        echo -e "  ai-connect.service:     ${RED}○ gestoppt${NC}"
    fi

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
        echo -e "  Peer-Name: ${YELLOW}$PEER_NAME${NC}"
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

    # Systemd
    echo ""
    if [[ -f "/etc/systemd/system/ai-connect.service" ]]; then
        echo -e "  Systemd Services: ${GREEN}installiert${NC}"
    else
        echo -e "  Systemd Services: ${RED}nicht installiert${NC}"
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
    echo "  AI-Connect Update"
else
    echo "  AI-Connect Installation"
fi
echo "=========================================="
echo ""

# Prüfe ob wir im richtigen Verzeichnis sind
if [[ ! -f "$SCRIPT_DIR/server/websocket_server.py" ]]; then
    echo -e "${RED}Fehler: Script muss aus dem AI-Connect Projektverzeichnis ausgeführt werden${NC}"
    exit 1
fi

# 1. Python venv erstellen/aktualisieren
echo -e "${YELLOW}[1/6]${NC} Python Virtual Environment..."
if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    echo "  Erstelle venv..."
    python3 -m venv "$SCRIPT_DIR/venv"
else
    echo "  venv existiert bereits"
fi

# 2. Dependencies installieren/aktualisieren
echo -e "${YELLOW}[2/6]${NC} Python Dependencies..."
"$SCRIPT_DIR/venv/bin/pip" install -q --upgrade pip
"$SCRIPT_DIR/venv/bin/pip" install -q --upgrade websockets pyyaml fastmcp
echo -e "  ${GREEN}Dependencies aktualisiert${NC}"

# 3. Config-Verzeichnis erstellen
echo -e "${YELLOW}[3/6]${NC} Konfiguration..."
mkdir -p "$CONFIG_DIR"

if [[ -f "$CONFIG_DIR/config.yaml" ]]; then
    echo -e "  ${GREEN}Config existiert bereits - wird nicht überschrieben${NC}"
    if ! $UPDATE_ONLY; then
        read -p "  Config neu erstellen? [j/N]: " RECREATE_CONFIG
        if [[ "$RECREATE_CONFIG" =~ ^[jJyY]$ ]]; then
            # Backup erstellen
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

# 4. Systemd Services installieren (braucht sudo)
echo -e "${YELLOW}[4/6]${NC} Systemd Services..."

# Prüfe ob Services schon existieren
SERVICES_EXIST=false
if [[ -f "/etc/systemd/system/ai-connect.service" ]]; then
    SERVICES_EXIST=true
fi

echo "  (benötigt sudo-Rechte)"

# Bridge Server Service
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

# MCP HTTP Server Service
sudo tee /etc/systemd/system/ai-connect-mcp.service > /dev/null << EOF
[Unit]
Description=AI-Connect MCP HTTP Server
After=network.target ai-connect.service

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

if $SERVICES_EXIST; then
    echo -e "  ${GREEN}Services aktualisiert${NC}"
else
    echo -e "  ${GREEN}Services installiert${NC}"
fi

# 5. PolicyKit Regel installieren
echo -e "${YELLOW}[5/6]${NC} PolicyKit Regel..."

POLKIT_EXISTS=false
if [[ -f "/etc/polkit-1/rules.d/50-ai-connect.rules" ]]; then
    POLKIT_EXISTS=true
fi

sudo tee /etc/polkit-1/rules.d/50-ai-connect.rules > /dev/null << 'EOF'
// PolicyKit Regel für AI-Connect Services
// Erlaubt User 'mp' die Steuerung von AI-Connect ohne sudo

polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "mp" &&
        (action.lookup("unit") == "ai-connect.service" ||
         action.lookup("unit") == "ai-connect-mcp.service")) {
        return polkit.Result.YES;
    }
});
EOF

sudo chmod 644 /etc/polkit-1/rules.d/50-ai-connect.rules

# PolicyKit neu laden
sudo systemctl restart polkit.service

if $POLKIT_EXISTS; then
    echo -e "  ${GREEN}PolicyKit Regel aktualisiert und Dienst neu geladen${NC}"
else
    echo -e "  ${GREEN}PolicyKit Regel installiert und Dienst neu geladen${NC}"
fi

# 6. Services aktivieren und (neu)starten
echo -e "${YELLOW}[6/6]${NC} Services aktivieren und starten..."
sudo systemctl daemon-reload
sudo systemctl enable ai-connect.service ai-connect-mcp.service 2>/dev/null

if $UPDATE_ONLY || $SERVICES_EXIST; then
    echo "  Services werden neugestartet..."
    sudo systemctl restart ai-connect.service
    sleep 2
    sudo systemctl restart ai-connect-mcp.service
else
    sudo systemctl start ai-connect.service
    sleep 2
    sudo systemctl start ai-connect-mcp.service
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
echo "  ./install.sh --status  # Status anzeigen"
echo "  ./install.sh --update  # Update durchführen"
echo ""
echo "Logs:"
echo "  journalctl -u ai-connect.service -f"
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
