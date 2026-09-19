# Mochila Virtual - configuracion del router del aula (RouterOS 7.x)
#
# Topologia:
#   ether1  = WAN, SIN USAR durante el demo (red 100% aislada)
#   ether2  = Raspberry Pi 3
#   wlan1   = alumnos y docentes
#
# Carga:  /import file-name=mikrotik-demo.rsc
# Antes verifica los nombres reales de tus interfaces con:  /interface print
#
# IMPORTANTE: cambia la MAC de la Pi en la linea marcada antes de importar.

# --- red local -----------------------------------------------------------
/interface bridge
add name=bridge-aula protocol-mode=none

/interface bridge port
add bridge=bridge-aula interface=ether2
add bridge=bridge-aula interface=wlan1

/ip address
add address=10.10.0.1/24 interface=bridge-aula network=10.10.0.0

/ip pool
add name=alumnos ranges=10.10.0.50-10.10.0.200

/ip dhcp-server
add address-pool=alumnos disabled=no interface=bridge-aula name=dhcp-aula lease-time=4h
/ip dhcp-server network
add address=10.10.0.0/24 dns-server=10.10.0.1 gateway=10.10.0.1

# --- la Pi siempre con la misma IP --------------------------------------
# Reemplaza la MAC por la de tu Raspberry (en la Pi:  ip link show eth0)
/ip dhcp-server lease
add address=10.10.0.10 mac-address=B8:27:EB:00:00:00 server=dhcp-aula comment="Raspberry Pi - Mochila"

# --- que "mochila.edu" lleve a la Pi ------------------------------------
# Asi nadie tiene que escribir una direccion IP en el navegador.
/ip dns
set allow-remote-requests=yes servers=10.10.0.1
/ip dns static
add name=mochila.edu address=10.10.0.10 ttl=1d
add name=www.mochila.edu address=10.10.0.10 ttl=1d

# --- Wi-Fi ---------------------------------------------------------------
# Ajusta segun tu modelo: los equipos con RouterOS 7 wifiwave2 usan
# /interface/wifi en lugar de /interface/wireless.
/interface wireless security-profiles
set [ find default=yes ] authentication-types=wpa2-psk mode=dynamic-keys \
    wpa2-pre-shared-key="mochila2026"

/interface wireless
set wlan1 disabled=no ssid="Mochila-Virtual" mode=ap-bridge band=2ghz-g/n \
    channel-width=20/40mhz-XX frequency=auto distance=indoors \
    default-authentication=yes

# Los dispositivos no se ven entre si: proteccion basica en una red
# compartida por menores de edad.
/interface bridge port
set [ find interface=wlan1 ] horizon=1

# --- aislamiento total ---------------------------------------------------
# Nada sale hacia el puerto WAN aunque alguien enchufe un modem por error.
# Este bloque es el que sostiene la afirmacion de "sin transmision externa"
# en la seccion de privacidad de datos del proyecto.
/ip firewall filter
add chain=forward action=drop out-interface=ether1 comment="Sin salida a internet"
add chain=input action=accept protocol=udp dst-port=53 in-interface=bridge-aula comment="DNS local"
add chain=input action=accept protocol=udp dst-port=67 in-interface=bridge-aula comment="DHCP"
add chain=input action=drop in-interface=ether1 comment="Sin administracion desde WAN"

# --- calidad de servicio (opcional para el demo) -------------------------
# Evita que un dispositivo acapare la radio durante la prueba de carga.
/queue simple
add name=limite-por-cliente target=10.10.0.0/24 max-limit=20M/20M \
    queue=pcq-upload-default/pcq-download-default
