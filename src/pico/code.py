DEBUG = False

import board
import busio
import adafruit_rfm69
import digitalio
import time
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import countio
import Vedirect

uart = busio.UART(board.GP8, board.GP9, baudrate=19200, receiver_buffer_size = 1024)
shunt = Vedirect.Vedirect()

# If connected to console print debug messages
def log(message):
    if(DEBUG):
        print(message)
#        print(datetime.now() + message)

# Read VE_Direct smart shunt
def read_ve():
    log("Waiting for data")
    uart.reset_input_buffer()
    data = b''
    while "PID" not in data:
        data = b''
        data = uart.readline()
    while(str(data).count("Checksum") < 2): # Full data is in 2 blocks (at least for SmartShunt)
        data += uart.readline()

    log("Shunt Data: " + str(data))

    keys = shunt.read_data_single(data) # Uses auxiliary function from serial VEDirect library

    values = {
        "v_int": int(keys["V"]),
        "t_int": int(keys["T"]),
        "i_int": int(keys["I"]),
        "ah_int": int(keys["CE"]) * -1, # Gets sent as negative mAH, but this allows unsigned byte array
        "soc_int": int(keys["SOC"]),
        "ttg_int": int(keys["TTG"]),
        "dold_int": int(keys["H2"]) * -1, # Gets sent as negative mAH, but this allows unsigned byte array
        "tsf_int": int(keys["H9"])
    }

    # Batteries should not be negative, so work well with unsigned byte arrays
    if(values["v_int"] < 0):
        values["v_int"] = 0
    return values

# Initialize RFM69HCW Radio
spi=busio.SPI(clock=board.GP2, MOSI=board.GP3, MISO=board.GP4)
cs = digitalio.DigitalInOut(board.GP17)
reset = digitalio.DigitalInOut(board.GP16)
rfm69 = adafruit_rfm69.RFM69(spi, cs, reset, 433.0)
rfm69.encryption_key = ( b"\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26\x26" )

# Initialize ADS1115 ADC
ads = ADS.ADS1115(busio.I2C(board.GP19, board.GP18), 1.0)

# Define counter for reading tachometer
counter = countio.Counter(board.GP15)

log("Initialization Complete")

while(True):
    
    # Read ADC shunt and batteries
    chan3 = AnalogIn(ads, ADS.P2).value
    chan12 = AnalogIn(ads, ADS.P0, ADS.P1).value
    chan4 = AnalogIn(ads, ADS.P3).value

    # Values shouldn't be negative, so work nice as unsigned byte arrays
    if(chan3 < 0):
        chan3 = 0
    if(chan12 < 0):
        chan12 = 0
    if(chan4 < 0):
        chan4 = 0

    # Count tach pulses for 1 second
    # Sending RFM69 messages every second seems to cause inconsistency,
    # But enough other things happen reading the shunt to slow this down,
    # So 1 second is OK
    counter.reset()
    time.sleep(1)
    count = counter.count

    ve_values = {
        "v_int": 0,
        "t_int": 0,
        "i_int": 0,
        "ah_int": 0, 
        "soc_int": 0,
        "ttg_int": 0,
        "dold_int": 0,
        "tsf_int": 0
    }

    # Read a VE_Direct packet from UART
    try:
        ve_values = read_ve()

    except BaseException as e:
        log("Failed to read VE_Direct; Using defaults; error was: " + str(e))

    # Convert all ints to appropriate size byte arrays
    v_bytes = ve_values["v_int"].to_bytes(2, "big")
    t_bytes = ve_values["t_int"].to_bytes(2, "big", signed=True)
    i_bytes = ve_values["i_int"].to_bytes(3, "big", signed=True)
    ah_bytes = ve_values["ah_int"].to_bytes(3, "big")
    soc_bytes = ve_values["soc_int"].to_bytes(2, "big")
    ttg_bytes = ve_values["ttg_int"].to_bytes(3, "big", signed=True)
    # Divide Depth of Last Discharge (in mAH) by 10 to fit in 2 bytes
    dold_bytes = round(ve_values["dold_int"]/10).to_bytes(2, "big")
    tsf_bytes = ve_values["tsf_int"].to_bytes(4, "big")
    vt_bytes = chan3.to_bytes(2, "big")
    load_bytes = chan12.to_bytes(2, "big")
    revs_bytes = count.to_bytes(2, "big")
    vs_bytes = chan4.to_bytes(2, "big")
    
    # Combine byte arrays into one large one for sending
    data_arr = v_bytes + vs_bytes + i_bytes + ah_bytes + soc_bytes + ttg_bytes + dold_bytes + tsf_bytes + vt_bytes + load_bytes + revs_bytes + vs_bytes

    # Debug pring what's going to be sent
    log("Preparing to send:")
    log("House Voltage:       " + str(ve_values["v_int"]))
    log("Temperature:         " + str(ve_values["t_int"]))
    log("Net Current:         " + str(ve_values["i_int"]))
    log("AH Used:             " + str(ve_values["ah_int"]))
    log("State of Charge:     " + str(ve_values["soc_int"]))
    log("Time To Go:          " + str(ve_values["ttg_int"]))
    log("Depth Of LD:         " + str(ve_values["dold_int"]))
    log("Time Since Full:     " + str(ve_values["tsf_int"]))
    log("Thruster voltage:    " + str(chan3))
    log("Load:                " + str(chan12))
    log("Revs:                " + str(count))
    log("Start Batt Volts:    " + str(chan4))

    log("Sending packet: " + str(data_arr) + "\n")

    # send the packet out the RFM69
    rfm69.send(data_arr, node=2)
