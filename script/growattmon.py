#!/usr/bin/env python3

import time
import os
import paho.mqtt.client as mqtt
import json

from configparser import RawConfigParser
from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from pymodbus.exceptions import ModbusIOException

from growatt import Growatt

settings = RawConfigParser()
settings.read(os.path.dirname(os.path.realpath(__file__)) + '/solarmonitor.cfg')

deviceregistersmapping = settings.get('mapping', 'devicemap')

with open(os.path.dirname(os.path.realpath(__file__)) + "/mapping/" + deviceregistersmapping) as f:
    mapping = json.load(f)

interval = settings.getint('query', 'interval', fallback=1)
offline_interval = settings.getint('query', 'offline_interval', fallback=60)
error_interval = settings.getint('query', 'error_interval', fallback=60)

mqtt_host = settings.get('mqtt', 'host')
mqtt_port = settings.getint('mqtt', 'port')
mqtt_topic = settings.get('mqtt','topic', fallback = 'growatt')
mqtt_clientid = settings.get('mqtt','clientid', fallback='inverter')

# functions

def get_single(registers, index, unit):
    return round(float(registers[index]) * unit, 1)

def get_double(registers, index, unit):
    return round(float((registers[index] << 16) + registers[index+1])*unit, 1)


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

time.sleep(2)
# Publish inverter and sensor configuration for HASS autodiscovery

mqtt.publish('test/homeassistant/sensor/growattmqtt/config',payload='{"name": "Growatt MQTT", "object_id": "growatt_inverter"}')

for reg in mapping['registerGroups']:
    regMap = reg['registerMap']
    for map in regMap:
        topic = 'test/homeassistant/sensor/growatt_' + map + '/config'
        payload='{"device_class" : "' + regMap[map]['class'] + '","name" : "'+ regMap[map]['name'] + '","state_topic" : "inverter/growattmqtt/'+map+'","unit_of_measurement" : "' + regMap[map]['unit']+'", "unique_id": "growatt_'+map+'", "object_id": "growatt_'+map+'", "device_id": "growatt_inverter"}'
        mqtt.publish('test/homeassistant/sensor/growatt_' + map + '/config',payload='{"device_class" : "' + regMap[map]['class'] + '","name" : "'+ regMap[map]['name'] + '","state_topic" : "inverter/growattmqtt/'+map+'","unit_of_measurement" : "' + regMap[map]['unit']+'", "unique_id": "growatt_'+map+'", "object_id": "growatt_'+map+'", "device_id": "growatt_inverter"}', retain=True)



# print('Setup Serial Connection... ', end='')
# port = settings.get('solarmon', 'port', fallback='/dev/ttyUSB0')
# client = ModbusClient(method='rtu', port=port, baudrate=9600, stopbits=1, parity='N', bytesize=8, timeout=1)
# client.connect()
# print('Done!')

# print('Loading inverter... ')
# unit = settings.get('inverter','unit', fallback='1')
# print('Done!')





while True:
    online = False
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