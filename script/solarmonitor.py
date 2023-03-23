#!/usr/bin/env python3

import time
import os
import paho.mqtt.client as mqtt

from configparser import RawConfigParser
from pymodbus.client.sync import ModbusSerialClient as ModbusClient

from growatt import Growatt

settings = RawConfigParser()
settings.read(os.path.dirname(os.path.realpath(__file__)) + '/solarmonitor.cfg')

interval = settings.getint('query', 'interval', fallback=1)
offline_interval = settings.getint('query', 'offline_interval', fallback=60)
error_interval = settings.getint('query', 'error_interval', fallback=60)

mqtt_host = settings.get('mqtt', 'host')
mqtt_port = settings.getint('mqtt', 'port')
mqtt_topic = settings.get('mqtt','topic', fallback = 'growatt')
mqtt_clientid = settings.get('mqtt','clientid', fallback='inverter')

# Clients

print('Connect to MQTT broker... ', end='')

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print("connected OK to MQTT Returned code=",rc)
    else:
        print("Bad connection Returned code=",rc)

mqtt = mqtt.Client(mqtt_clientid)
mqtt.on_connect = on_connect
mqtt.connect(mqtt_host, mqtt_port)
mqtt.loop_start()
time.sleep(5)

print('Setup Serial Connection... ', end='')
port = settings.get('solarmon', 'port', fallback='/dev/ttyUSB0')
client = ModbusClient(method='rtu', port=port, baudrate=9600, stopbits=1, parity='N', bytesize=8, timeout=1)
client.connect()
print('Done!')

print('Loading inverters... ')
inverters = []
for section in settings.sections():
    if not section.startswith('inverters.'):
        continue

    name = section[10:]
    unit = int(settings.get(section, 'unit'))
    measurement = settings.get(section, 'measurement')
    growatt = Growatt(client, name, unit)
    growatt.print_info()
    inverters.append({
        'error_sleep': 0,
        'growatt': growatt,
        'measurement': measurement
    })
print('Done!')

while True:
    online = False
    for inverter in inverters:
        # If this inverter errored then we wait a bit before trying again
        if inverter['error_sleep'] > 0:
            inverter['error_sleep'] -= interval
            continue

        growatt = inverter['growatt']
        try:
            now = time.time()
            info = growatt.read()

            if info is None:
                continue

            # Mark that at least one inverter is online so we should continue collecting data
            online = True

            points = [{
                'time': int(now),
                'measurement': inverter['measurement'],
                "fields": info
            }]

            print(growatt.name)
            print(points)


        except Exception as err:
            print(growatt.name)
            print(err)
            inverter['error_sleep'] = error_interval

    if online:
        time.sleep(interval)
    else:
        # If all the inverters are not online because no power is being generated then we sleep for 1 min
        print('All inverters are offline .. Sleeping')
        time.sleep(offline_interval)