import os
import re

import serial
import threading
import time
import sys
import signal
import paho.mqtt.client as mqtt

# Open the serial connection
import platform
from dotenv import load_dotenv
from paho.mqtt.enums import CallbackAPIVersion

if platform.system() == 'Windows':
    ser = serial.Serial('COM3', 115200, timeout=1)  # Adjust baudrate if necessary
elif platform.system() == 'Linux':
    ser = serial.Serial('/dev/serial0', 9600, timeout=1)

# Flag to control thread shutdown
running = True


# Function to handle graceful exit on CTRL+C
def signal_handler(sig, frame):
    global running
    print("\nCTRL+C detected. Exiting...")
    running = False
    ser.close()
    sys.exit(0)


# Attach signal handler to SIGINT (CTRL+C)
signal.signal(signal.SIGINT, signal_handler)


# Function to continuously read lines from the device
def handle_temp(line: str):
    match = re.search(r"t (\d+)F (\d+)C", line)
    if match:
        temp = match.group(2)
        client.publish(f"{mqtt_root}/Temp", str(temp))
    else:
        print(line)


def handle_rain(line: str):
    match = re.search(r"R (\d+)", line)
    if match:
        rain_value = match.group(1)
        client.publish(f"{mqtt_root}/Rain", rain_value)
    else:
        print(line)


def handle_lensbad():
    client.publish(f"{mqtt_root}/LensBad", "1")


def handle_emitter_saturated():
    client.publish(f"{mqtt_root}/EmSat", "1")


def handle_reset(line):
    match = re.search(r"Reset (\w)", line)
    if match:
        letter = match.group(1)
        message = {
            "N": "Normal Power Up",
            "M": "MCLR",
            "W": "Watchdog Timer Reset",
            "O": "Stack Overflow",
            "U": "Stack Underflow",
            "B": "Brownout(Low Voltage / disconnected)",
            "D": "Other"
        }.get(letter)
        client.publish(f"{mqtt_root}/Reset", message)
    else:
        print(line)


def parse_line(line) -> bool:
    if line.startswith("t"):
        handle_temp(line)
        return True
    elif "Reset" in line:
        handle_reset(line)
        return True
    elif line.startswith("R"):
        handle_rain(line)
        return True
    elif "LensBad" in line:
        handle_lensbad()
        return True
    elif "EmSat" in line:
        handle_emitter_saturated()
        return True
    return False


def read_from_serial():
    while running:
        if ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8').strip()  # Read a line from the serial device
                if line:
                    if not parse_line(line):
                        print(f"Received unknown line: {line}")
            except Exception as e:
                print(f"Error reading from serial: {e}")
                break


# Function to send "R\r\n" every 60 seconds
# the sensor seems to print a value even when not polling, so this is mostly to check things are alive
def main_loop():
    while running:
        try:
            request_rain()
            request_temp()
        except Exception as e:
            print(f"Error writing to serial: {e}")
            break
        time.sleep(60)


def request_temp():
    ser.write(b'T\r\n')


def request_rain():
    ser.write(b'R\r\n')


def request_restart():
    ser.write(b'K\r\n')


def on_connect(client, userdata, flags, reason_code, properties):
    print("Connected with result " + str(reason_code))
    print(f"Publishing to {mqtt_root}")


def on_disconnect(client, userdata, flags, reason_code, properties):
    print("disconnected, exiting")
    os.kill(os.getpid(), signal.SIGINT)
    time.sleep(5)
    os._exit(1)


def on_message(client, userdata, message):
    pass


def create_client() -> mqtt:
    host = os.environ["MQTT_HOST"]
    username = os.environ["MQTT_USER"]
    password = os.environ["MQTT_PASS"]
    print(f"Connecting to {host}")
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    client.username_pw_set(username, password)
    client.on_message = on_message
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(host, 1883, 60)
    return client


if __name__ == '__main__':
    load_dotenv("local.env", override=False)
    mqtt_root = os.getenv("MQTT_ROOT", "benny/rg9")
    client = create_client()
    client.loop_start()
    # Start the RS232 read thread
    read_thread = threading.Thread(target=read_from_serial)
    read_thread.start()

    # reset the device
    time.sleep(1)
    request_restart()

    # main loop - will block until interrupted
    main_loop()

    # cleanup
    read_thread.join()
    client.loop_stop()
    client.disconnect()
