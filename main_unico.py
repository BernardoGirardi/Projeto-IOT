# =====================================================================
#  PROJETO IoT - Monitoramento de Temperatura e Umidade
#  ESP8266 + DHT11 + OLED + MQTT + HTTP
#
#  ARQUIVO UNICO - basta salvar este main.py na placa.
#  Bibliotecas necessarias na ESP (instalar via mip - ver README):
#     - ssd1306.py
#     - umqtt/simple.py
# =====================================================================

import time
import network
import dht
import socket
from machine import Pin, SoftI2C
import ssd1306
from umqtt.simple import MQTTClient

# =====================================================================
#  CONFIGURACAO - edite APENAS esta secao
# =====================================================================
WIFI_SSID = "NOME_DA_SUA_REDE"
WIFI_PASS = "SENHA_DA_SUA_REDE"

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

# prefixo UNICO do seu grupo (broker publico e compartilhado)
MQTT_BASE = "ifsc/iot/grupoXYZ"
TOPIC_TEMP = MQTT_BASE + "/temperatura"
TOPIC_HUMID = MQTT_BASE + "/umidade"
TOPIC_STATUS = MQTT_BASE + "/status"
MQTT_CLIENT_ID = b"esp8266-grupoXYZ"

INTERVALO = 3   # segundos entre leituras (DHT11 nao gosta de < 2s)

# =====================================================================
#  1. CONECTAR NO WI-FI
# =====================================================================
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Conectando no Wi-Fi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASS)
        for _ in range(30):            # espera ate 15s
            if wlan.isconnected():
                break
            time.sleep(0.5)
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print("Wi-Fi OK. IP:", ip)
        return ip
    print("FALHOU ao conectar no Wi-Fi. Confira SSID/senha.")
    return None


ip_local = conectar_wifi()

# =====================================================================
#  2. SENSOR E TELA
# =====================================================================
sensor = dht.DHT11(Pin(13))             # DHT11 no GPIO13 (D7)
i2c = SoftI2C(scl=Pin(5), sda=Pin(4))   # OLED: SCL=D1, SDA=D2
oled = ssd1306.SSD1306_I2C(128, 64, i2c)
# Se a tela mostrar lixo deslocado ~2px, e SH1106 (ver README).


def mostrar(temp, humid):
    oled.fill(0)
    oled.text("MONITOR IoT", 18, 2)
    oled.hline(0, 14, 128, 1)
    oled.text("Temp:", 4, 24)
    oled.text(str(temp) + " C", 60, 24)
    oled.text("Umid:", 4, 40)
    oled.text(str(humid) + " %", 60, 40)
    oled.hline(0, 54, 128, 1)
    oled.text("ESP8266 + DHT11", 4, 56)
    oled.show()


# =====================================================================
#  3. MQTT  (protocolo de comunicacao 1)
# =====================================================================
mqtt = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER,
                  port=MQTT_PORT, keepalive=60)


def conectar_mqtt():
    try:
        mqtt.connect()
        mqtt.publish(TOPIC_STATUS, b"online")
        print("MQTT conectado em", MQTT_BROKER)
        return True
    except Exception as e:
        print("Erro MQTT:", e)
        return False


# =====================================================================
#  4. SERVIDOR WEB  (protocolo de comunicacao 2 = HTTP)
# =====================================================================
def pagina_html(temp, humid):
    return """HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Connection: close

<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Monitor IoT</title>
<style>
body{{font-family:sans-serif;background:#0f1117;color:#eee;
text-align:center;margin:0;padding:40px}}
h1{{font-weight:500}}
.card{{display:inline-block;background:#1b1f2a;border-radius:14px;
padding:30px 50px;margin:14px;min-width:160px}}
.v{{font-size:48px;font-weight:600;margin:10px 0}}
.t{{color:#5dcaa5}} .h{{color:#85b7eb}}
small{{color:#888}}
</style></head><body>
<h1>Monitoramento IoT - ESP8266</h1>
<div class="card"><div>Temperatura</div>
<div class="v t">{0} &deg;C</div></div>
<div class="card"><div>Umidade</div>
<div class="v h">{1} %</div></div>
<p><small>Atualiza a cada 5s | DHT11 + MQTT + HTTP</small></p>
</body></html>""".format(temp, humid)


servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
servidor.bind(("", 80))
servidor.listen(1)
servidor.settimeout(0.1)   # nao bloqueia o loop principal
print("Servidor web ativo na porta 80")
if ip_local:
    print("Abra no navegador: http://" + ip_local)

# =====================================================================
#  5. LOOP PRINCIPAL
# =====================================================================
conectar_mqtt()
temp_atual = 0
humid_atual = 0
ultimo = 0

while True:
    agora = time.time()

    # a cada INTERVALO segundos: le, mostra e publica
    if agora - ultimo >= INTERVALO:
        ultimo = agora
        try:
            sensor.measure()
            temp_atual = sensor.temperature()
            humid_atual = sensor.humidity()
            print("Temp:", temp_atual, "C  Umid:", humid_atual, "%")
            mostrar(temp_atual, humid_atual)
            try:
                mqtt.publish(TOPIC_TEMP, str(temp_atual))
                mqtt.publish(TOPIC_HUMID, str(humid_atual))
            except Exception as e:
                print("MQTT caiu, reconectando...", e)
                conectar_mqtt()
        except Exception as e:
            print("Erro ao ler DHT11:", e)

    # atende quem abrir a pagina web
    try:
        cliente, addr = servidor.accept()
        cliente.settimeout(2)
        try:
            cliente.recv(512)
            cliente.send(pagina_html(temp_atual, humid_atual))
        finally:
            cliente.close()
    except OSError:
        pass

    time.sleep(0.1)
