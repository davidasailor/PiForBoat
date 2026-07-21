#DEBUG = True will log more, and speed up first phone home
DEBUG = False
ONBOARD_HARDWARE = True
RADIO_EQUIPPED = ONBOARD_HARDWARE
#RADIO_EQUIPPED = False
BME_EQUIPPED = ONBOARD_HARDWARE
ACCEL_EQUIPPED = ONBOARD_HARDWARE
ADS_EQUIPPED = ONBOARD_HARDWARE

import configparser
import threading
import time
import math
import adafruit_adxl34x
import statistics
import datetime
import logging
import queue
import socket
#from telnetlib import Telnet
import RPi.GPIO as GPIO
import atexit
import subprocess
import operator
from functools import reduce
import signal
from func_timeout import func_timeout, FunctionTimedOut
import board
import adafruit_rfm69
import busio
from digitalio import DigitalInOut, Direction, Pull
import mariadb
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import digitalio
import requests
import pickle
import pandas as pd
from sklearn.neural_network import MLPRegressor
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import glob
import adafruit_bme680

PS = 13 # Pin for sensing power state
BILGE_PIN = 21 # Input from bilge pump enabled
RFM69_G0 = 5 # Interrupts from RFM69 radio
#VOC_EN = 23 # EN pin for VOC sensor

SIGNALK_PORT = 55557 # Port for sending datagrams to localhost SignalK

# Resolve configuration and logging directory (PATH)
PATH = "./"
if os.path.exists("./piForBoatPy.conf"):
    PATH = "./"
else:
    found_path = None
    for h in glob.glob("/home/*"):
        if os.path.exists(os.path.join(h, "piForBoatPy.conf")):
            found_path = h + "/"
            break
    if found_path:
        PATH = found_path
    else:
        if os.path.exists("/etc/piForBoatPy.conf"):
            PATH = "/etc/"
        else:
            PATH = os.path.expanduser("~") + "/"

BOAT_NAME = "YOUR_BOAT_NAME" # Default fallback, will be overridden by the config file section header

# Simple defaults
battHouse = [0.0, 0.0, 0.0]
battEngine = [0.0, 0.0, 0.0]
battAux = [0.0, 0.0, 0.0]
amps = [0.0, 0.0, 0.0]
netCurrent = [0.0, 0.0, 0.0]
heel = [0.0, 0.0, 0.0]
tempCabin = [0.0, 0.0, 0.0]
tempEngine = [0.0, 0.0, 0.0]
tempExhaust = [0.0, 0.0, 0.0]
soc = 1.0
revs = [0, 0, 0]
gasLevel = [0.0, 0.0, 0.0]
water1 = 0
water2 = 0
fuel = 0
bilgeTime = 0
bilge = 0
ampHours = 0.0
lastNav = datetime.datetime.now()
location = ""
battHouseTemp = [0.0, 0.0, 0.0]
tempFridge = [0.0, 0.0, 0.0]
polarSpeed = 0.0
refrigerator_govee = ""
pressure = [0.0, 0.0, 0.0]
humidity = [0.0, 0.0, 0.0]

# RFM69 Initialization
if(RADIO_EQUIPPED):
    CS = digitalio.DigitalInOut(board.CE0)
    RESET = digitalio.DigitalInOut(board.D25)
    SPI = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    FREQ = 433.0
    rfm69 = adafruit_rfm69.RFM69(SPI, CS, RESET, FREQ)
    rfm69.encryption_key = ( b"\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26" )

# Load values from config file
config = configparser.ConfigParser()
config.read(PATH + 'piForBoatPy.conf')
# Automatically detect the boat name from the first section header of the config file
sections = config.sections()
if sections:
    BOAT_NAME = sections[0]
configs = config[BOAT_NAME]
heelOffset = float(configs['heelOffset'])
factorBattHouse = float(configs['factorBattHouse'])
factorBattEngine = float(configs['factorBattEngine'])
factorBattAux = float(configs['factorBattAux'])
factorFuel = float(configs['factorFuel'])
factorAmps = float(configs['factorAmps'])
factorRPMs = float(configs['factorRPMs'])
nmeaHost = configs['nmeaHost']
nmeaPort = int(configs['nmeaPort'])
water_cutoff_full = float(configs["water_cutoff_full"])
water_cutoff_3_quarters = float(configs["water_cutoff_3_quarters"])
water_cutoff_2_quarters = float(configs["water_cutoff_2_quarters"])
water_cutoff_1_quarter = float(configs["water_cutoff_1_quarter"])
mysql_host = configs["mysql_host"]
mysql_user = configs["mysql_user"]
mysql_password = configs["mysql_password"]
mysql_database = configs["mysql_database"]
refrigerator_govee = configs["refrigerator_govee"]

# Load persistent values saved from previous shutdown
oldValues = configparser.ConfigParser()
oldValues.read(PATH + 'persistent_data')
oldValuesMine = oldValues["OldValues"]
ampHours = float(oldValuesMine["ampHours"])
bilgeTime = datetime.datetime.strptime(oldValuesMine["bilgeTime"],
                                            "%Y-%m-%d %H:%M:%S.%f")
lastNav = datetime.datetime.strptime(oldValuesMine["lastNav"],
                                            "%Y-%m-%d %H:%M:%S.%f")
location = oldValuesMine["location"]
bilge = int(oldValuesMine["bilgeCount"])

measurement_lock = threading.Lock() # Thread safety for measurements

# Queue and file for storing output
nmea_queue = queue.Queue()
nmea_file = open(PATH + "Log.nmea", "a")

# Declare socket for sending to SignalK
signalK = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# I2C for ADS and ADXL
i2c = busio.I2C(board.SCL, board.SDA)

def bilge_monitor_task(onTime):
    logging.warning("Bilge pump monitor started")
    setBilgeTime(onTime)
    incBilge()

    stillRunning = False
    # Monitor for up to 120 seconds
    endTime = datetime.datetime.now() + datetime.timedelta(seconds=120)
    
    while datetime.datetime.now() < endTime:
        if not GPIO.input(BILGE_PIN):
            break
        time.sleep(1.0)

    if GPIO.input(BILGE_PIN):
        stillRunning = True
        logging.warning("Continuous bilge since " + str(onTime))
    else:
        logging.warning(f"Bilge stopped. Ran for {(datetime.datetime.now()-onTime).total_seconds()}s")
    
    sql_home(getVals())

# Callback for bilge pump turning on
def bilgeOn(channel):
    # Debounce manually
    time.sleep(0.5)
    if not GPIO.input(BILGE_PIN):
        logging.warning("Bilge reader pin bounced; disregarding")
        return
        
    # Offload the long-running task to a new thread so we don't block other interrupts
    onTime = datetime.datetime.now()
    t = threading.Thread(target=bilge_monitor_task, args=(onTime,))
    t.start()

def rfm69_callback(rfm69_irq):
    # see if this was a payload_ready interrupt ignore if not
    if rfm69.payload_ready:
        packet = rfm69.receive(timeout=None, with_header=True)
        if packet is not None:
            logging.debug("RFM69 Received: " + packet.hex())
            if (packet[1] == 2): #NodeID=2 for Aft Cabin Pico
                if len(packet) != 37:
                    logging.warning("Discarding RFM69 packet from Node 2 with invalid length: " + str(len(packet)) + " bytes (expected 37)")
                    return
                v_bytes = packet[4:6]
                v_int = int.from_bytes(v_bytes, "big")
                v_float = v_int / 1000.0   # SmartShunt sends millivots
                temp_bytes = packet[6:8]
                temp_int = int.from_bytes(temp_bytes, "big", signed=True)
                temp_float = temp_int * (9/5) + 32  # SmartShunt sends Celcius
                i_bytes = packet[8:11]
                i_int = int.from_bytes(i_bytes, "big", signed=True)
                i_float = i_int / 1000.0    # SmartShunt sends milliamps
                ah_bytes = packet[11:14]
                ah_int = int.from_bytes(ah_bytes, "big")
                ah_float = ah_int / 1000.0  # SmartShunt sends milliamps
                soc_bytes = packet[14:16]
                soc_int = int.from_bytes(soc_bytes, "big")
                soc_float = soc_int / 10.0  # SmartShunt sends tenths of percentage
                ttg_bytes = packet[16:19]
                ttg_int = int.from_bytes(ttg_bytes, "big", signed=True)
                dold_bytes = packet[19:21]
                dold_int = int.from_bytes(dold_bytes, "big")
                # SmartShunt sends milliamps, but pico divides by 10 to fit in 2 byte buffer
                # This should be ok for up to 650 AH
                dold_float = dold_int / 100.0  
                tsf_bytes = packet[21:25]
                tsf_int = int.from_bytes(tsf_bytes, "big")
                vt_bytes = packet[25:27]
                vt_int = int.from_bytes(vt_bytes, "big")
                vt_float = vt_int           # Voltage Divider factor built in to Set function
                load_bytes = packet[27:29]
                load_int = int.from_bytes(load_bytes, "big")
                load_float = load_int       # Factor built into Set function
                revs_bytes = packet[29:31]
                revs_int = int.from_bytes(revs_bytes, "big")    # Factor built into Set function
                vs_bytes = packet[31:33]
                vs_int = int.from_bytes(vs_bytes, "big")
                vs_float = vs_int
                temp1_bytes = packet[33:35]
                temp1_int = int.from_bytes(temp1_bytes, "big", signed=True)
                temp1_float = temp1_int / 10.0
                temp2_bytes = packet[35:37]
                temp2_int = int.from_bytes(temp2_bytes, "big", signed=True)
                temp2_float = temp2_int / 10.0

                setBattHouse(v_float)
                setBattEngine(vs_float)
                setNetCurrent(i_float)
                setAmpHours(ah_float)
                setSOC(soc_float)
                setTTG(ttg_int)

                setDOLD(dold_float)
                setTSF(tsf_int)
                setBattAux(vt_float)
                setAmps(load_float)
                setRevs(revs_int)
                setBattHouseTemp(temp_float)

                # TODO: Check that engine and exhaust aren't flipped
                setTempEngine(temp1_float * 9.0 / 5.0 + 32.0) # Convert to Fahrenheit
                setTempExhaust(temp2_float * 9.0 / 5.0 + 32.0) # Convert to Fahrenheit

                # Nead to read back in from measurements to use factors
                nmea_log("ADC", "{:.2f}".format(getBattHouse()[1]) +
                        ", " + "{:.2f}".format(getBattEngine()[1]) +
                        ", " + "{:.2f}".format(getBattAux()[1]) +
                        ", " + "{:.2f}".format(getNetCurrent()[1]) +
                        ", " + "{:.0f}".format(getAmpHours()) +
                        ", " + "{:.2f}".format(getSOC()) +
                        ", " + "{:.2f}".format(getAmps()[1]) +
                        ", " + "{:.2f}".format(getBattHouseTemp()[1] ))
                if(revs_int > 1):
                    # Should multiply by factorRPMs, but that would be inconsistent with old logs
                    nmea_log("RPM", "{:.0f}".format(revs_int))

                nmea_log("EGT", "{:.2f}".format(getTempEngine()[1]) + 
                         ", " + "{:.2f}".format(getTempExhaust()[1]))

            elif (packet[1] == 0xff): #NodeID=1 for refrigerator sensor
                t_bytes = packet[8:9]
                t_int = int.from_bytes(t_bytes, "big", signed=True)-2 # Reads ~2 degrees high
                logging.debug("Got Temperature: " + str(t_int))
                setFridgeTemp(t_int)

# On shutdown, save persistent values (for SIGINT)
def shutdown():
    with open(PATH + "persistent_data", "w") as saveTo:
        saveTo.write("[OldValues]\n")
        saveTo.write("ampHours=" + str(ampHours) + "\n")
        saveTo.write("bilgeTime=" + str(bilgeTime)+ "\n")
        #saveTo.write("bilgeTime=" + str(datetime.datetime.now()) + "\n") # Use this to seed new file
        saveTo.write("lastNav=" + str(lastNav) + "\n")
        saveTo.write("bilgeCount=" + str(bilge)+ "\n")
        saveTo.write("location=" + location + "\n")
        saveTo.write("lastShutdown=" + str(datetime.datetime.now()) + "\n")
    logging.info("Shut down PiForBoatPy")

# On shutdown, save persistent values (for SIGTERM)
def shutdown_sigterm(*args):
    shutdown()
    raise RuntimeError("Force Shutdown") # TODO: Find a cleaner way to halt here

# Auxiliary function to format Signal K Delta
def send_delta(path, value, is_str=False):
    if(is_str):
        delta = ('{"updates": [{"$source": "PiForBoat", "values":[ {"path":"' + path + '","value":"' + str(value) + '"}]}]}\n').encode()
    else:
        delta = ('{"updates": [{"$source": "PiForBoat", "values":[ {"path":"' + path + '","value":' + str(value) + '}]}]}\n').encode()

    signalK.sendto(delta, ("127.0.0.1", SIGNALK_PORT))


# Auxiliary functions to get and set all measurement values

def getBilgeTime():
    return bilgeTime

def getBilge():
    return bilge

def setLocation(loc):
    global location
    with measurement_lock:
        location = loc

def setLastNav(lastT):
    global lastNav
    with measurement_lock:
        lastNav = lastT
    send_delta("navigation.lastOn", lastNav, True)

def getLocation():
    return location

def getLastNav():
    return lastNav

def setBattHouse(volts):
    with measurement_lock:
        battHouse[1] = volts * factorBattHouse
        getMinMax(battHouse)
    send_delta("electrical.batteries.House.voltage", volts)

def getBattHouse():
    with measurement_lock:
        return list(battHouse)

def setBattHouseTemp(temp):
    with measurement_lock:
        battHouseTemp[1] = temp
        getMinMax(battHouseTemp)
    send_delta("electrical.batteries.House.temperature", (5/9) * (temp +459.67))

def getBattHouseTemp():
    with measurement_lock:
        return list(battHouseTemp)

def setBattEngine(volts):
    with measurement_lock:
        battEngine[1] = volts * factorBattEngine
        getMinMax(battEngine)
    send_delta("electrical.batteries.Engine.voltage", battEngine[1])

def getBattEngine():
    with measurement_lock:
        return list(battEngine)

def setBattAux(volts):
    with measurement_lock:
        battAux[1] = volts * factorBattAux
        getMinMax(battAux)
    send_delta("electrical.batteries.Thruster.voltage", battAux[1])

def getBattAux():
    with measurement_lock:
        return list(battAux)

def setAmps(ampVal):
    with measurement_lock:
        amps[1] = ampVal * factorAmps
        getMinMax(amps)
    send_delta("electrical.batteries.House.load", amps[1])

def getAmps():
    with measurement_lock:
        return list(amps)

def setHeel(angle, from_internal):
    angle_deg = angle * 57.3
    if from_internal:
        with measurement_lock:
            heel[1] = angle_deg + heelOffset
            getMinMax(heel)
        send_delta("navigation.attitude", '{"roll":"' + str(angle + heelOffset/57.3) + '", "pitch":"0.0", "yaw":"0.0"}')
        send_delta("navigation.attitude.heel", angle_deg + heelOffset)
    else:
        with measurement_lock:
            heel[1] = angle_deg
            getMinMax(heel)
        send_delta("navigation.attitude.heel", angle_deg)

def getHeel():
    with measurement_lock:
        return list(heel)

def setTempCabin(temp):
    with measurement_lock:
        tempCabin[1] = temp
        getMinMax(tempCabin)
    send_delta("environment.inside.mainCabin.temperature", (5/9) * (tempCabin[1] +459.67))

def getTempCabin():
    with measurement_lock:
        return list(tempCabin)

def setGasLevel(newGasLevel):
    with measurement_lock:
        gasLevel[1] = newGasLevel
        getMinMax(gasLevel)
    send_delta("environment.inside.mainCabin.voc", gasLevel[1])

def getGasLevel():
    with measurement_lock:
        return list(gasLevel)

def setPressure(newPressure):
    with measurement_lock:
        pressure[1] = newPressure
        getMinMax(pressure)
    send_delta("environment.inside.mainCabin.pressure", pressure[1])

def setHumidity(newHumidity):
    with measurement_lock:
        humidity[1] = newHumidity
        getMinMax(humidity)
    send_delta("environment.inside.mainCabin.humidity", humidity[1])

def setTempEngine(temp):
    with measurement_lock:
        tempEngine[1] = temp
        getMinMax(tempEngine)
    send_delta("propulsion.main.coolantTemperature", (5/9) * (tempEngine[1] + 459.67))

def getTempEngine():
    with measurement_lock:
        return list(tempEngine)

def setTempExhaust(temp):
    with measurement_lock:
        tempExhaust[1] = temp
        getMinMax(tempExhaust)
    send_delta("propulsion.main.exhaustTemperature", (5/9) * (tempExhaust[1] + 459.67))

def getTempExhaust():
    with measurement_lock:
        return list(tempExhaust)

def setRevs(rpms):
    with measurement_lock:
        revs[1] = rpms * factorRPMs
        getMinMax(revs)
    send_delta("propulsion.main.revolutions", revs[1] / 60)

def getRevs():
    with measurement_lock:
        return list(revs)

def setWater1(level):
    global water1
    with measurement_lock:
        water1 = level
    send_delta("tanks.freshWater.aft.currentLevel", (level / 100))

def getWater1():
    return water1

def setWater2(level):
    global water2
    with measurement_lock:
        water2 = level
    send_delta("tanks.freshWater.front.currentLevel", (level / 100))

def getWater2():
    return water2

# TODO: Fix this based on actual voltage readings
def setFuel(level):
    global fuel
    with measurement_lock:
        fuel = max(0, min(100, (level*factorFuel)))
    send_delta("tanks.fuel.main.currentLevel", (fuel / 100))

def getFuel():
    return fuel

def setBilgeTime(level):
    global bilgeTime
    with measurement_lock:
        bilgeTime = level
    send_delta("sensors.bilge.time", level, True)
    logging.debug("Sent bilge time delta: " + str(level))

def incBilge():
    global bilge
    with measurement_lock:
        bilge = bilge + 1
    send_delta("sensors.bilge.count", bilge)

# Legacy from manual calculation before SmartShunt
def incAmpHours(ah):
    with measurement_lock:
        ampHours = max(0, ah + ampHours)
    send_delta("electrical.batteries.House.capacity.dischargeSinceFull", ampHours * 3600)

def setAmpHours(ah):
    global ampHours
    with measurement_lock:
        ampHours = ah
    send_delta("electrical.batteries.House.capacity.dischargeSinceFull", ampHours * 3600)

def getAmpHours():
    return ampHours

def setNetCurrent(amps):
    with measurement_lock:
        netCurrent[1] = amps
        getMinMax(netCurrent)
    send_delta("electrical.batteries.House.current", amps)

def getNetCurrent():
    with measurement_lock:
        return list(netCurrent)

def setSOC(state):
    global soc
    with measurement_lock:
        soc = state
    send_delta("electrical.batteries.House.capacity.stateOfCharge", soc / 100.0)

def getSOC():
    return soc

def setTTG(ttg):
    with measurement_lock:
        1==1
        # TTG is probably not worth saving to NMEA or sending home
    send_delta("electrical.batteries.House.capacity.timeRemaining", ttg)

def setDOLD(dold):
    with measurement_lock:
        1==1
        # DOLD is not worth saving to NMEA or sending home (it's already implicitly stored)
    send_delta("electrical.batteries.House.capacity.depthOfLastDischarge", dold)

def setTSF(tsf):
    with measurement_lock:
        1==1
        # TSF is not worth saving to NMEA or sending home (it's already implicitly stored)
    send_delta("electrical.batteries.House.capacity.timeSinceFull", tsf)

def setSSID(ssid):
    send_delta("environment.ssid", ssid, True)

def setFridgeTemp(temp):
    with measurement_lock:
        tempFridge[1] = temp
        getMinMax(tempFridge)
    send_delta("environment.inside.refrigerator.temperature", (5/9) * (tempFridge[1] + 459.67))
    
def setPolarTarget(speed):
    with measurement_lock:
        polarSpeed = speed
    send_delta("performance.polarSpeed", speed*.51444)

# Reset min and max values of measurements
# Values chosen to be immediately overwritten by valid data
def resetMinMax():
    with measurement_lock:
        battHouse[0] = 100.0
        battHouse[2] = -1.0
        battEngine[0] = 100.0
        battEngine[2] = -1.0
        battAux[0] = 100.0
        battAux[2] = -1.0
        amps[0] = 100.0
        amps[2] = -1.0
        netCurrent[0] = 501.0
        netCurrent[2] = -501.0
        heel[0] = 91.0
        heel[2] = -91.0
        tempCabin[0] = 300.0
        tempCabin[2] = -100.0
        tempEngine[0] = 300.0
        tempEngine[2] = -100.0
        tempExhaust[0] = 300.0
        tempExhaust[2] = -100.0
        revs[0] = 4000
        revs[2] = -1
        gasLevel[0] = 1024.0
        gasLevel[2] = 0.0
        battHouseTemp[0] = 300.0
        battHouseTemp[2] = -300.0
        tempFridge[0] = 200
        tempFridge[2] = -200

# Build list of SQL values to insert in to database
def getVals():

    # Parse Lat/Lon from NMEA format to discrete floats
    try:
        pos_split = getLocation().split(",")
        lat=pos_split[0]
        lon=pos_split[1]
        lat_min = float(lat[2:])
        lat_deg = float(lat[0:2])
        lat_float = lat_deg + (lat_min / 60.0)
        lon_min = float(lon[3:])
        lon_deg = float(lon[0:3])
        lon_float = (lon_deg + (lon_min / 60)) * -1
    except ValueError:      # GGA is 0's before initialized
        lat_float = 39.546149
        lon_float = -76.085138
    except IndexError:      # GGA is 0's before initialized
        lat_float = 39.546149
        lon_float = -76.085138

    vals = ((datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "{:.2f}".format(getBattHouse()[1]),
        "{:.2f}".format(getBattHouse()[0]),
        "{:.2f}".format(getBattHouse()[2]),
        "{:.1f}".format(getHeel()[0]),
        "{:.1f}".format(getHeel()[2]),
        "{:.1f}".format(getHeel()[1]),
        "{:.8f}".format(lat_float),
        "{:.8f}".format(lon_float),
        "39.546149",
        "-76.085138",
        "{:.1f}".format(getTempCabin()[1]),
        getLastNav().strftime("%Y-%m-%d %H:%M:%S"),
        getBilgeTime().strftime("%Y-%m-%d %H:%M:%S"),
        "{:.2f}".format(getBattEngine()[1]),
        "{:.2f}".format(getBattEngine()[0]),
        "{:.2f}".format(getBattEngine()[2]),
        "{:.2f}".format(getBattAux()[1]),
        "{:.2f}".format(getBattAux()[0]),
        "{:.2f}".format(getBattAux()[2]),
        "{:.2f}".format(getAmps()[1]),
        "{:.2f}".format(getAmps()[0]),
        "{:.2f}".format(getAmps()[2]),
        "{:.0f}".format(getFuel()),
        "{:.0f}".format(getWater1()),
        "{:.0f}".format(getWater2()),
        "{:.0f}".format(getAmpHours()),
        "{:.1f}".format(getTempEngine()[1]),
        "{:.1f}".format(getTempEngine()[0]),
        "{:.1f}".format(getTempEngine()[2]),
        "{:.1f}".format(getTempExhaust()[1]),
        "{:.1f}".format(getTempExhaust()[0]),
        "{:.1f}".format(getTempExhaust()[2]),
        "{:.0f}".format(getRevs()[1]),
        "{:.0f}".format(getRevs()[2]),
        "{:.0f}".format(getRevs()[0]),
        "{:.0f}".format(getGasLevel()[0]),
        "{:.0f}".format(getGasLevel()[1]),
        "{:.0f}".format(getGasLevel()[2]),
        "{:.2f}".format(getNetCurrent()[0]),
        "{:.2f}".format(getNetCurrent()[1]),
        "{:.2f}".format(getNetCurrent()[2]),
        "{:.2f}".format(getSOC()),
        "{:.0f}".format(getBilge()),
        "{:.2f}".format(getBattHouseTemp()[0]),
        "{:.2f}".format(getBattHouseTemp()[1]),
        "{:.2f}".format(getBattHouseTemp()[2]))

    return vals


# Set min / max accordingly if new value exceeds previous bounds
def getMinMax(arr):
    arr[0] = min({arr[0], arr[1]})
    arr[2] = max(arr[-2:])

# Get NMEA data from socket to remote server
def nmeaReader():
    
    # Keep trying to start a connection forever
    while True:
        s = None
        try:
            # Replace deprecated telnetlib with socket
            s = socket.create_connection((nmeaHost, nmeaPort), timeout=10)
            # Make a file-like object for easy line reading
            f = s.makefile('r', encoding='utf-8', errors='replace')
            
            logging.info(f"Connected to NMEA source at {nmeaHost}:{nmeaPort}")
            
            while True:
                line = f.readline()
                if not line:
                    raise EOFError("Connection closed")
                nmea_process(line.strip())
                
        except (socket.timeout, ConnectionRefusedError, OSError, EOFError) as e:
            logging.debug(f"NMEA Connection/Read Error: {e}")
        finally:
            if s:
                s.close()
            time.sleep(10)

# Helper function to save NMEA data
def nmea_process(line):
    if(not line == ''):
        if((line[0] == "$" and line.count("$") == 1)
                or (line[0] == "!" and line.count("!") == 1)): # If it's a valid NMEA line (sanity check)
            logging.debug("NMEA_In:" + line)
            nmea_log("", line)
            parts = line.split(",")
            if(len(parts) > 4 and parts[0] == "$GPGGA"): # Save location into measurements
                setLastNav(datetime.datetime.now())
                setLocation(parts[2] + "," + parts[4])
                logging.debug("Got location:" + parts[2] + "N, " + parts[4] + "W")
            
        else:
            logging.warning("Invalid NMEA String Received: " + line)


def read_ssid():
    while True:
        # Get connected SSID every 2 minutes too
        try:
            output = subprocess.check_output(['iwgetid'])
            setSSID(str(output).split('"')[1])
        except Exception:
            logging.warning("Failed to get wifi SSID")
        
        if(DEBUG):
            time.sleep(120) # Maybe make this faster for some debugging

        else:
            time.sleep(120) # Get temperature every 2 minutes

def read_bme680():

    bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)

    while True:
        try:
            temp = bme680.temperature * 9.0 / 5.0 + 32.0  # Convert to Fahrenheit
            pressure = bme680.pressure
            humidity = bme680.humidity
            gas = (bme680.gas)/1000

            setTempCabin(temp)
            setGasLevel(round(gas))
            setPressure(pressure)
            setHumidity(humidity)
            nmea_log("BME", "{:.2f},{:.2f},{:.2f},{:.2f}".format(temp, pressure, humidity, gas))
        except:
            logging.warning("Failed to read BME680 sensor")

        time.sleep(60)

# Get heel from netorked triducer (if active) or attached accelerometer
def readerAccel():
    accelerometer = adafruit_adxl34x.ADXL343(i2c)
    timestamp = ""
    while True:
        needADXL = True
        try:
            attitude = requests.get("http://localhost:3000/signalk/v1/api/vessels/self/navigation/attitude").json()
            if attitude["$source"] != "PiForBoat":
                needADXL = False
                if(attitude["timestamp"] == timestamp):
                    needADXL = True
                else:
                    setHeel(float(attitude["value"]["roll"]), False)
                timestamp = attitude["timestamp"]

        except (OSError, ValueError, KeyError, TypeError) as e:
            logging.debug(f"Failed to read networked heel ({e}); falling back to ADXL")
            needADXL = True

        if needADXL:
            try:
                # Get 5 point average of heel angle
                heels = []
                for i in range(5):
                    axes = accelerometer.acceleration

                    heels.append(math.atan2(axes[1], axes[2]))

                # Pre-calibrated level adjustment applied by setHeel
                setHeel(statistics.mean(heels), True)

                nmea_log("ACC", "{:.1f}".format(getHeel()[1]))
                time.sleep(4.0)
            except(OSError, ValueError):
                logging.warning("Failed to read accelerometer")

        time.sleep(1.0)

# Auxiliary function to get tank level from voltage
def waterMapper(voltage):
    if(voltage<water_cutoff_1_quarter):
        return 0
    elif(voltage<water_cutoff_2_quarters):
        return 25
    elif(voltage<water_cutoff_3_quarters):
        return 50
    elif(voltage<water_cutoff_full):
        return 75
    else:
        return 100

# Retrieve data from ADS1115
def readerADC():
    ads = ADS.ADS1115(i2c)
    chan_water1 = AnalogIn(ads, ADS.P0)
    chan_water2 = AnalogIn(ads, ADS.P1)

    water1 = 0
    water2 = 0
    fuel = 0
    voc = 0

    while(True):

        water1_raw=0
        water2_raw=0
        # GPIO.output(VOC_EN, GPIO.LOW)
        t_end = time.time() + 23
        try:
            while(time.time() < t_end):
                water1_raw = max(water1_raw, chan_water1.voltage)
                water2_raw = max(water2_raw, chan_water2.voltage)
                time.sleep(0.05)
            logging.debug("Water1 Raw: " + str(water1_raw))
            logging.debug("Water2 Raw: " + str(water2_raw))

            water1 = waterMapper(water1_raw)
            water2 = waterMapper(water2_raw)

            # voc = AnalogIn(ads, ADS.P3).voltage * 100.0
            # GPIO.output(23, GPIO.HIGH)

            setWater1(water1)
            setWater2(water2)
            setFuel(fuel)
            # setGasLevel(voc)
            nmea_log("TNK", str(water1) + ", " + str(water2) + ", " + str(fuel))
            # nmea_log("GAS", str(voc))

        except (OSError, ValueError):
            logging.warning("Failed to read from ADS1115")

        if(DEBUG):
            time.sleep(10)
        else:
            time.sleep(300) # Only tie up I2C for 23 seconds every 5 mintues, since accellerometer needs it too

# Helper function to enqueue data to log
# TODO: Make robust enough to handle EST in addition to EDT?
def nmea_log(type, message):
    if(not type==""):
        str_to_put = ("$PI" + type + "," + message)
        str_to_put = str_to_put + "," + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        checksum = '{:x}'.format(reduce(operator.xor, (ord(s) for s in str_to_put), 0))
        str_to_put = str_to_put + "*" + checksum
    else:
        str_to_put = message
    nmea_queue.put(str_to_put)
    logging.debug("NMEA_Out: " + str_to_put)

# Periodically dump queued data into log file
def nmea_save():
    while True:
        while not nmea_queue.empty():
            nmea_file.write(nmea_queue.get()+"\r\n")
        nmea_file.flush()
        time.sleep(10)

# Send SQL statement to insert values
def sql_home(vals):
    BoatServer = mariadb.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database
    )

    mycursor = BoatServer.cursor()

    sql = """INSERT INTO status (
        datetime, voltage, minv, maxv, minh, maxh, heel, latgps, longps,
        latgprs, longprs, temperature, lastnav, lastbilge, engv, minengv,
        maxengv, auxv, minauxv, maxauxv, amps, minamps, maxamps, fuel,
        water1, water2, ah, engTemp, minEngTemp, maxEngTemp, exhaustTemp,
        minExhaustTemp, maxExhaustTemp, RPMs, maxRPMs, minRPMs, minGasLevel,
        gasLevel, maxGasLevel, minNetCurrent, netCurrent, maxNetCurrent, soc, bilgeCount, minHouseBattTemp, HouseBattTemp, maxHouseBattTemp ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s )"""

    logging.debug("Executing SQL Statement: " + sql)
    logging.debug("With values: " + str(vals))

    mycursor.execute(sql,vals)
    BoatServer.commit()

    mycursor.close()
    BoatServer.close()

# Send data to house periodically
def phone_home():
    delayTime = 600

    # Wait for data to be ready
    if DEBUG:
        time.sleep(10)
    else:
        time.sleep(120)

    while True:

        try:
            sql_home(getVals())
            resetMinMax()
        except mariadb.Error as err:
            logging.warning("Failed to send data to SQL: " + str(err))
            time.sleep(30)
            continue

        time.sleep(delayTime)

# Use ML polar Model to predict SOG        
def polar_predict():
    model = pickle.load(open(PATH + "MLP_Simple_gws_confirmed.dmp", 'rb'))
    scaler = pickle.load(open(PATH + "MLP_Simple_gws_confirmed_scaler.dmp", 'rb'))
    while True:

        ready = 1
        try:
            gwa_raw = requests.get("http://localhost:3000/signalk/v1/api/vessels/self/environment/wind/angleTrueGroundAverage").json()["value"] / math.pi * 180
            gws_raw = requests.get("http://localhost:3000/signalk/v1/api/vessels/self/environment/wind/speedOverGroundAverage").json()["value"] * 1.94384
        except:
            ready = 0
            gwa_raw = 0
            gws_raw = 0
            
        if(ready == 1):
            frame = pd.DataFrame(
                {
                    'GWA (Rolling)': [gwa_raw],
                    'GWS (Rolling)': [gws_raw],
                }
            )
            tf_scaled = scaler.transform(frame)

            out = model.predict(tf_scaled)[0]

            setPolarTarget(out)
        time.sleep(2)

# Class for handling Govee BTLE updates
# Expects to read a file at /var/log/goveebttemplogger/gvh-<mac>...
# File is generated by service from https://github.com/wcbonner/GoveeBTTempLogger
class Govee_Handler(FileSystemEventHandler):
    last_time = "00:00:00"
    def on_modified(self, event):
        if event.is_directory:
            return
        
        try:
            logging.debug(f"Handling Govee Event in {event.src_path}")
            if refrigerator_govee in event.src_path:
                with open(event.src_path, 'rb') as f:
                    try:  # catch OSError in case of a one line file 
                        f.seek(-2, os.SEEK_END)
                        while f.read(1) != b'\n':
                            f.seek(-2, os.SEEK_CUR)
                    except OSError:
                        f.seek(0)
                    
                    last_line = f.readline().decode('utf-8', errors='ignore').strip()
                    if not last_line:
                        return

                    parts = last_line.split()
                    if len(parts) < 3:
                        return

                    timestamp = parts[1]
                    if timestamp != self.last_time:
                        temp = round(float(parts[2]) * 9/5 + 32, 1)
                        logging.debug("Got Temperature: " + str(temp))
                        setFridgeTemp(temp)
                        self.last_time = timestamp
        except Exception as e:
            logging.error(f"Error in Govee_Handler: {e}")

# Main function to start threads and execute
def PiForBoatPy():

    # Begin logging
    if DEBUG:
        logging.basicConfig(filename='/var/log/PiForBoatPy.log',
                            level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y%m%d%H%M%S')
    else:
        logging.basicConfig(filename='/var/log/PiForBoatPy.log',
                            level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y%m%d%H%M%S')
    logging.info("Starting PiForBoatPy")

    send_delta("sensors.bilge.time", bilgeTime, True)
    send_delta("sensors.bilge.count", bilge)

    # Set min/max values to defaults on all measurements
    resetMinMax()

    # Start listening for bilge pump
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BILGE_PIN, GPIO.IN)
    GPIO.add_event_detect(BILGE_PIN, GPIO.RISING, callback=bilgeOn, bouncetime=500)

    # Start listening for RFM69 packets
    if(RADIO_EQUIPPED):
        rfm69.listen()
        GPIO.setup(RFM69_G0, GPIO.IN)
        GPIO.add_event_detect(RFM69_G0, GPIO.RISING, callback=rfm69_callback)

    # Initialize VOC sensor and disable the heater for now
    # GPIO.setup(VOC_EN, GPIO.OUT)
    # GPIO.output(VOC_EN, GPIO.HIGH)

    # ADXL343 Acceleromoter
    if(ACCEL_EQUIPPED):
        threadAccel = threading.Thread(target=readerAccel, args=())

    # BME 680 Temp/Humidity/Pressure/VOCs
    if(BME_EQUIPPED):
         thread_bme = threading.Thread(target=read_bme680, args=())

    # ADS1115 ADC
    if(ADS_EQUIPPED):
        threadADC = threading.Thread(target=readerADC, args=())

    # NMEA-style file saving
    threadNmeaLog = threading.Thread(target=nmea_save, args=())

    # Heartbeat to send data home
    threadPhoneHome = threading.Thread(target=phone_home, args=())

    # Save data from NMEA network
    threadNmeaIn = threading.Thread(target=nmeaReader, args=())
    
    # Predict speed based on conditions and polar model
    threadPolar = threading.Thread(target=polar_predict, args=())

    # Get SSID every 2 minutes
    threadSSID = threading.Thread(target=read_ssid, args=())

    # Start gathering data
    threadNmeaLog.start()
    #threadRFM69.start()
    if(ACCEL_EQUIPPED):
        threadAccel.start()
    if(BME_EQUIPPED):
        thread_bme.start()

    threadSSID.start()
    threadNmeaIn.start()
    threadPhoneHome.start()
    if(ADS_EQUIPPED):
        threadADC.start()
    threadPolar.start()

    # Handle Govee thermometer data
    govee_handler = Govee_Handler()
    observer = Observer()

    observer.schedule(govee_handler, "/var/log/goveebttemplogger", recursive=True)
    observer.start()

    atexit.register(shutdown) # Do this on shutdown
    signal.signal(signal.SIGTERM, shutdown_sigterm)

if __name__ == "__main__":
    PiForBoatPy()
