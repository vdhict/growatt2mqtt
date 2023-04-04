import json
import time
import yaml
import paho.mqtt.client as mqtt
from pymodbus.client.sync import ModbusSerialClient

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")

def read_modbus_registers(client, start, length):
    return client.read_input_registers(start, length, unit=1)

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