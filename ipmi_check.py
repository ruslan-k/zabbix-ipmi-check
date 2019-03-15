#!/usr/bin/env python3

import argparse
from datetime import datetime
from subprocess import PIPE, Popen, STDOUT
from traceback import format_exc
import re
import os
import json

SENDER_TIMEOUT = 3
IPMI_TIMEOUT = 5
VOLT_PERCENT_RANGE = 10
VBAT_NORMAL_VOLTAGE = 3.2
CPU_VOLTAGE_MIN = 0.9
CPU_VOLTAGE_MAX = 1.3


def get_args():
    parser = argparse.ArgumentParser(description="Zabbix IPMI request")
    parser.add_argument("hostname", help="Hostname name in zabbix to send data to")
    parser.add_argument("ipmi_addr", help="IPMI interface address")
    parser.add_argument("-u", "--username", help="IPMI User")
    parser.add_argument("-p", "--password", help="IPMI User's password")
    parser.add_argument("-d", "--discovery", action='store_true', help="Force discovery")
    parser.add_argument("-t", "--debug", action='store_true', help="Debug script")
    args = parser.parse_args()
    return args


def syscmd(cmd):
    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT,
              close_fds=True)
    p.wait()
    output = p.stdout.read()
    if len(output) > 1:
        return output.decode('utf-8')
    return p.returncode


def get_voltage_sensor_type(sensor_name):
    voltage_sensor_type = re.search("([\-\.\d]+V|CPU|VBAT)", sensor_name).group(1)
    return voltage_sensor_type


def get_ipmi_data(ipmi_address, username, password):
    command = "ipmi-sensors -h {} -u {} -p {} -l user --session-timeout={}".format(ipmi_address, username, password,
                                                                                   IPMI_TIMEOUT * 1000)
    output = syscmd(command)
    if "not found" in output:
        raise Exception("freeipmi is not installed")
    elif "invalid hostname" in output:
        raise Exception(output.strip())
    elif "connection timeout" in output:
        raise Exception(output.strip())
    elif "internal IPMI error" in output:
        raise Exception("ipmi_sensor_read: internal IPMI error")
    return output


def listed_sensors_data(data):
    sensors_list = []
    for sensor_string in data.split("\n")[1:]:
        sensors_params = [x.strip() for x in sensor_string.split("|")]
        if len(sensors_params) == 6 and sensors_params[3] != "N/A":
            sensors_list.append(sensors_params)
    return sensors_list


def get_min_max_voltage_threshold(num):
    procent_change = ((num / 100) * VOLT_PERCENT_RANGE)
    min_treshold = round(num - procent_change, 2)
    max_treshold = round(num + procent_change, 2)
    if num < 0:
        return max_treshold, min_treshold
    return min_treshold, max_treshold


def append_sensor_discovery_data(data, sender_data_file):
    discovery_data = {
        "temperature_sensors": {"data": []},
        "voltage_sensors": {"data": []},
        "fan_sensors": {"data": []},
    }
    for sensor in data:
        sensor_name = sensor[1]
        sensor_type = sensor[2]
        if sensor_type == "Temperature":
            discovery_data['temperature_sensors']["data"].append({"{#TEMP_SENSOR_NAME}": sensor_name})
        elif sensor_type == "Voltage":
            voltage_sensors_discovery_data = {}
            voltage_sensors_discovery_data["{#VOLT_SENSOR_NAME}"] = sensor_name
            voltage_sensor_type = get_voltage_sensor_type(sensor_name)
            if voltage_sensor_type.endswith("V"):
                voltage_numeric = float(voltage_sensor_type.strip("V"))
                voltage_threshord_level_min, voltage_threshord_level_max = get_min_max_voltage_threshold(
                    voltage_numeric)
                voltage_sensors_discovery_data["{#VOLT_SENSOR_MIN_THR}"] = voltage_threshord_level_min
                voltage_sensors_discovery_data["{#VOLT_SENSOR_MAX_THR}"] = voltage_threshord_level_max
            elif voltage_sensor_type == "CPU":
                voltage_sensors_discovery_data["{#VOLT_SENSOR_MIN_THR}"] = CPU_VOLTAGE_MIN
                voltage_sensors_discovery_data["{#VOLT_SENSOR_MAX_THR}"] = CPU_VOLTAGE_MAX
            elif voltage_sensor_type == ("VBAT"):
                voltage_threshord_level_min, voltage_threshord_level_max = get_min_max_voltage_threshold(
                    VBAT_NORMAL_VOLTAGE)
                voltage_sensors_discovery_data["{#VOLT_SENSOR_MIN_THR}"] = voltage_threshord_level_min
                voltage_sensors_discovery_data["{#VOLT_SENSOR_MAX_THR}"] = voltage_threshord_level_max
            discovery_data['voltage_sensors']["data"].append(voltage_sensors_discovery_data)
        elif sensor_type == "Fan":
            discovery_data['fan_sensors']["data"].append({"{#FAN_SENSOR_NAME}": sensor_name})
    for key, value in discovery_data.items():
        string = "- {} {}\n".format(key, json.dumps(value))
        write_to_file(sender_data_file, string)


def write_to_file(filepath, string):
    with open(filepath, "a+") as infile:
        infile.write(string)


def remove_sender_file(filepath):
    os.remove(filepath)


def append_sensor_item_data(data, sender_data_file):
    for sensor_string in data:
        sensor_type = sensor_string[2]
        sensor_name = sensor_string[1]
        sensor_reading = sensor_string[3]
        string = '- "{}[\\"{}\\"]" {}\n'.format(sensor_type, sensor_name, sensor_reading)
        write_to_file(sender_data_file, string)


def send_data(hostname, sender_data_file):
    command = "timeout {} zabbix_sender -z localhost -s {} -i {} -vv".format(SENDER_TIMEOUT, hostname, sender_data_file)
    output = syscmd(command)
    if "Sending failed" in output or "processed: 0" in output:
        raise Exception(output.strip())
    return output


def is_midnight():
    now = datetime.now()
    if now.hour == 0 and now.minute == 0:
        return True


def main():
    args = get_args()
    try:
        ipmidata = get_ipmi_data(args.ipmi_addr, args.username, args.password)
        sensors_data = listed_sensors_data(ipmidata)
        hostname_formatted = re.sub(r'[.\-]+', '_', args.hostname)
        sender_data_file = "/tmp/{}.zbx".format(hostname_formatted)
        append_sensor_item_data(sensors_data, sender_data_file)
        if is_midnight():
            append_sensor_discovery_data(sensors_data, sender_data_file)
        send_data(args.hostname, sender_data_file)
        remove_sender_file(sender_data_file)
        print("OK")
    except Exception as e:
        print(e)
        if args.debug:
            print(format_exc())


if __name__ == '__main__':
    main()
