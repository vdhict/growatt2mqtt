import json
import sys
import time
import yaml
import paho.mqtt.client as mqtt
from pymodbus.client.sync import ModbusSerialClient

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")

def read_modbus_registers(client, start, length):
    return client.read_input_registers(start, length, unit=1)

def load_config(config_file):
    with open(config_file, "r") as file:
        config = yaml.safe_load(file)
    return config


def connect_mqtt(mqtt_config):
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT broker")
        else:
            print(f"Failed to connect to MQTT broker, return code: {rc}")

    client = mqtt.Client()
    client.username_pw_set(mqtt_config["username"], mqtt_config["password"])
    client.on_connect = on_connect
    client.connect(mqtt_config["host"], mqtt_config["port"])
    client.loop_start()

    return client


def connect_modbus(modbus_config):
    client = ModbusSerialClient(
        method="rtu",
        port=modbus_config["port"],
        baudrate=modbus_config["baudrate"],
        stopbits=modbus_config["stopbits"],
        bytesize=modbus_config["bytesize"],
        parity=modbus_config["parity"],
        timeout=modbus_config["timeout"],
    )

    if client.connect():
        print("Connected to Modbus device")
    else:
        print("Failed to connect to Modbus device")
        sys.exit(1)

    return client

def mqtt_autodiscovery(mqtt_client, autodiscover_prefix, inverter_name, registers_info):
    for register_group in registers_info["registerGroups"]:
        register_map = register_group["registerMap"]
        for register_key, register_info in register_map.items():
            if "name" in register_info and "unit" in register_info and "class" in register_info:
                topic = f"{autodiscover_prefix}/sensor/{inverter_name}/{register_key}/config"
                payload = {
                    "name": f"{inverter_name} {register_info['name']}",
                    "unit_of_measurement": register_info["unit"],
                    "state_topic": f"{config['mqtt']['base_topic']}/{inverter_name}/{register_key}",
                    "device_class": register_info["class"],
                    "unique_id": f"{inverter_name}_{register_key}",
                    "device": {
                        "name": inverter_name,
                        "identifiers": f"{inverter_name}_growatt_inverter",
                        "manufacturer": "Growatt",
                        "model": "Growatt 4000TL",
                    },
                }
                mqtt_client.publish(topic, json.dumps(payload), retain=True)

def main():
    config = load_config("config.yaml")
    mqtt_client = connect_mqtt(config["mqtt"])
    modbus_client = connect_modbus(config["modbus"])

    registers_info = config["registers"]
    base_topic = config["mqtt"]["base_topic"]
    autodiscover_prefix = config["mqtt"]["autodiscover_prefix"]
    inverter_name = config["inverter_name"]
    offline_wait_interval = config["modbus"]["offline_wait_interval"]

    mqtt_autodiscovery(mqtt_client, autodiscover_prefix, inverter_name, registers_info)

    while True:
        for register_group in registers_info["registerGroups"]:
            start = register_group["start"]
            length = register_group["length"]

            try:
                response = read_modbus_registers(modbus_client, start, length)
            except Exception as e:
                print(f"Error reading modbus registers: {e}")
                print(f"Waiting {offline_wait_interval} seconds before trying again")
                time.sleep(offline_wait_interval)
                continue

            values = response.registers
            register_map = register_group["registerMap"]

            for register_key, register_info in register_map.items():
                if "words" in register_info:
                    words = register_info["words"]
                else:
                    words = 1

                index = register_info["id"]
                if words == 1:
                    value = float(values[index])
                else:
                    value = float((values[index] << 16) + values[index + 1])

                if "mul" in register_info:
                    value *= register_info["mul"]

                topic = f"{base_topic}/{inverter_name}/{register_key}"
                mqtt_client.publish(topic, value)

        time.sleep(config["update_interval"])

if __name__ == "__main__":
    main()