import this
import airrigazione_mqtt as aimqtt
import sys
import os 
import random
import time
import json
import _thread as thread  # using Python 3
import threading
import signal
import time

rasp_build=False #change if you are using pc client (not raspberry)
if(rasp_build):
    import RPi.GPIO as GPIO

if rasp_build:
    path_to_folder= os.path.join("/","home","pi","Desktop","airrigazione")
else:
    path_to_folder= os.path.join("irrigaz") #just for testing

rasp_configured=False


class DeviceData:
    irrigaz_led_pin = 5
    network_led_pin = 13
    sun_led_pin = 19

    watering = False
    sun = True
    noOthers = True #if other nodes are using water

    client = None
    irrigaz_time=None
    waiting_time=None #how long to wait before trying again to irrigate?
    timer = -1

class StoppableThread():
    def __init__(self):
        global auto_thread
        auto_thread = self

        self._must_be_stopped_ = False
        self.__in_loop__ = True
        x = threading.Thread(target=self._loop_, daemon=True)
        x.start()

    def stop(self):
        self._must_be_stopped_ = True

    def stopped(self):
        return self._must_be_stopped_

    def _loop_(self):
        while(self.__in_loop__):
            self.loop()

    def terminate_thread(self):
        self.__in_loop__ = False
        global auto_thread
        if auto_thread is self:
            auto_thread = None

    def loop(self): #to be overwritten.
        return


class TryingToIrrigateThread(StoppableThread):
    def loop(self):
        #print("autoIrrigat: i'm awake now")
        if(self.stopped()):
            #print("autoIrrigat: i've been stopped in the meantime..")
            self.terminate_thread()
            return

        print("autoIrrigat: let's try to irrigate..")
        if(try_to_irrigate()):
            #abbiamo irrigato
            #se siamo in modalità automatica, attiva nuovo thread.
            #print("autoIrrigat: irrigation finished")
            x = ScheduleNewIrrigationThread()
            self.terminate_thread()
        else:
            #print("autoIrrigat: irrigation unavailable..")
            timeToWait = DeviceData.waiting_time + (random.random() *2)-1 #adding a random factor to avoid coincidences..
            time.sleep(timeToWait)


class ScheduleNewIrrigationThread(StoppableThread):
    def loop(self):
        #print("autoSched: start waiting timer..")
        timeToWait = DeviceData.timer + (random.random() *2)-1 #adding a random factor to avoid coincidences..
        time.sleep(timeToWait)
        #print("autoSched: started again after timer..")
        if(self.stopped()):
            #print("autoSched: i've been stopped in the meantime..")
            self.terminate_thread()
            return
        #print("autoSched: let's try to irrigate!")
        x = TryingToIrrigateThread()
        self.terminate_thread()
        return

def setup_raspi():
    print("setting raspberry pins..")

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(DeviceData.irrigaz_led_pin ,GPIO.OUT)
    GPIO.setup(DeviceData.network_led_pin ,GPIO.OUT)
    GPIO.setup(DeviceData.sun_led_pin ,GPIO.OUT)

    global rasp_configured
    rasp_configured=True

    on_change_water_usage(DeviceData.noOthers)
    on_change_weather(DeviceData.sun)
    return

def set_led_value(pin:int, value:bool):
    if rasp_build and rasp_configured:
        GPIO.output(pin, value)
    return

def set_irrigaz_value(value:bool):
    print("setting irrigaz value to: ", value)
    set_led_value(DeviceData.irrigaz_led_pin, value)
    DeviceData.client.set_irrigation_value(value)
    return


def activate_irrigation():
    DeviceData.watering = True
    set_irrigaz_value(True)
    time.sleep(DeviceData.irrigaz_time)
    set_irrigaz_value(False)
    DeviceData.watering = False
    return
    

def try_to_irrigate(): #bloccante!
    if DeviceData.watering:
        print("We are already irrigating, impossible to start again now.")
        return False
    if not DeviceData.sun:
        print("There are not weather condition now.")
        return False
    if not DeviceData.noOthers:
        print("Someone else is using water, impossible to start now.")
        return False

    if DeviceData.client.is_connected():
        toIrrigate = round(random.random())

        if toIrrigate:
            #there is nobody,let's activate irrigation.
            print("the park is free --> Starting irrigation!")
            activate_irrigation()
            return True
        else:
            print("There is someone in the park. impossible to start now")
            return False
    else:
        print("not connected. Impossible to send data.")
        return False


def signal_handler(sig, frame):
    if rasp_build:
        GPIO.cleanup()
    sys.exit(0)

def on_change_water_usage(b:bool):
    print(f"someone else is using water:{not b}")
    set_led_value(DeviceData.network_led_pin, b)
    DeviceData.noOthers = b

def on_change_weather(b:bool):
    print(f"There is sun:{b}")
    set_led_value(DeviceData.sun_led_pin,b)
    DeviceData.sun = b


def main_core(argv):

    print(argv)
    f = open(argv)
    config = json.load(f)

    DeviceData.timer = config['RoutinePeriod'] #in seconds
    DeviceData.irrigaz_time = config["IrrigationTime"] #in seconds
    DeviceData.waiting_time = config["TimeToWait"] #in seconds
    print("timer: ", DeviceData.timer)


    DeviceData.client = aimqtt.Core(on_change_water_usage, on_change_weather,config)	#here it will try to connect.


    if(rasp_build):
        setup_raspi()
    x = ScheduleNewIrrigationThread()


    signal.signal(signal.SIGINT, signal_handler)
    if rasp_build:
        signal.pause()

    while(True):
        time.sleep(1)



if __name__ == '__main__':
    if len(sys.argv) > 1:
        argv= sys.argv[1]
    else:
        argv= os.path.join(path_to_folder,"node_config.json")
    
    main_core(argv)