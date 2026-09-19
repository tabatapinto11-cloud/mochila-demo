#!/usr/bin/env bash
# Instala Mochila Virtual como servicio en Raspberry Pi OS (Bookworm).
# Uso:  cd ~/mochila-demo && bash scripts/install-pi.sh
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USUARIO="$(whoami)"

echo "==> Proyecto en: $PROYECTO"
echo "==> Usuario:     $USUARIO"

echo "==> Instalando Python y venv"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip

echo "==> Creando entorno virtual"
python3 -m venv "$PROYECTO/.venv"
"$PROYECTO/.venv/bin/pip" install --upgrade pip
"$PROYECTO/.venv/bin/pip" install -r "$PROYECTO/requirements.txt"

echo "==> Registrando el servicio systemd"
sudo tee /etc/systemd/system/mochila.service > /dev/null <<EOF
[Unit]
Description=Mochila Virtual - asistente socratico offline
After=network.target

[Service]
Type=simple
User=$USUARIO
WorkingDirectory=$PROYECTO/app
Environment="KB_PATH=$PROYECTO/knowledge_base"
Environment="DB_PATH=$PROYECTO/uso.db"
ExecStart=$PROYECTO/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mochila
sudo systemctl restart mochila
sleep 4

echo
echo "==> Estado del servicio:"
sudo systemctl --no-pager status mochila | head -n 12
echo
echo "==> Prueba local:"
curl -s localhost:8000/api/salud || echo "(el servicio aun no responde, revisa: journalctl -u mochila -n 40)"
echo
echo
IP=$(hostname -I | awk '{print $1}')
echo "Listo. Desde cualquier dispositivo de la red:  http://$IP:8000"
