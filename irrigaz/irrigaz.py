import this
import airrigazione_mqtt as aimqtt
import sys
import os 
import random
import time
import json
import torch
import cv2
from PIL import Image
from torchvision import datasets, models, transforms
import _thread as thread  # using Python 3
import threading
import signal
import time



rasp_build=True #change if you are using pc client (not raspberry)
if(rasp_build):
    import RPi.GPIO as GPIO

if rasp_build:
    path_to_folder= os.path.join("/","home","pi","Desktop","airrigazione")
else:
    path_to_folder= os.path.join("irrigaz") #just for testing

rasp_configured=False
auto_thread=None


class CustomPushButton:
    def __init__(self, button_pin:int, led_pin:int, startValue=False, callback=None):
        """All pins MUST be defined as GPIO.BOARD. Pull-up resistors are enabled by software --> buttons must just connect to GND when pressed."""

        self.Value = startValue
        self.button_pin = button_pin
        self.led_pin = led_pin
        self.callback = callback
        #button config
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(button_pin, GPIO.FALLING, callback=self.button_callback, bouncetime=200)
        #led config
        GPIO.setup(led_pin, GPIO.OUT)
        GPIO.output(led_pin, startValue)
        if callback is not None:
            callback(startValue)

    def button_callback(self, channel):
        self.Value = not self.Value
        #print("Button at pin ", self.button_pin," pressed. Newvalue:", self.Value)
        GPIO.output(self.led_pin, self.Value)
        if self.callback is not None:
            self.callback(self.Value)
        return


class DeviceData:
    irrigaz_led_pin = 33
    network_led_pin = 35
    sun_led_pin = 36
    picture_button_pin = 40

    webcam_switch:CustomPushButton=None
    automatic_switch:CustomPushButton=None
    
    watering = False
    sun = True
    noOthers = True #if other nodes are using water

    camera = None 
    client = None
    model = None
    irrigaz_time=None
    waiting_time=None #how long to wait before trying again to irrigate?
    last_frame = None
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
            if(DeviceData.automatic_switch is not None and DeviceData.automatic_switch.Value) or (not rasp_build):
                #print("autoIrrigat: rescheduling a new irrigation...")
                x = ScheduleNewIrrigationThread()
            self.terminate_thread()
        else:
            #print("autoIrrigat: irrigation unavailable..")
            time.sleep(DeviceData.waiting_time)


class ScheduleNewIrrigationThread(StoppableThread):
    def loop(self):
        #print("autoSched: start waiting timer..")
        time.sleep(DeviceData.timer)
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
    DeviceData.camera = cv2.VideoCapture(0)

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(DeviceData.irrigaz_led_pin ,GPIO.OUT)
    GPIO.setup(DeviceData.network_led_pin ,GPIO.OUT)
    GPIO.setup(DeviceData.sun_led_pin ,GPIO.OUT)

    GPIO.setup(DeviceData.picture_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    DeviceData.webcam_switch = CustomPushButton(11,12,False)
    DeviceData.automatic_switch = CustomPushButton(15,16,True, callback=on_new_auto_value)

    global cameraButtonToggle
    cameraButtonToggle = False
    GPIO.add_event_detect(DeviceData.picture_button_pin, GPIO.FALLING, callback=camera_button_callback, bouncetime=200)

    global rasp_configured
    rasp_configured=True

    return

def on_new_auto_value(b:bool):
    if b:
        x= ScheduleNewIrrigationThread()
    else:
        if(auto_thread is not None):
            auto_thread.stop()
    return

def start_camera_stream(): #different thread just to extract frames.
    while True:
        if(DeviceData.camera is not None):
            ret, frame = DeviceData.camera.read()
            if(ret):
                DeviceData.last_frame = cv2.rotate(frame, cv2.ROTATE_180)


def camera_button_callback(channel):
    if DeviceData.automatic_switch.Value:
        return
    else:
        global cameraButtonToggle
        if cameraButtonToggle:
            print("camera Button pressed!")
            threading.Thread(target=try_to_irrigate, daemon=True).start()
        cameraButtonToggle = not cameraButtonToggle	#in order to resolve a mechanical problem :(

#read the switch and decide where to take from the picture (webcam/dataset).
def get_picture():
    if rasp_build and DeviceData.webcam_switch.Value:
        pic = DeviceData.last_frame
        save_last_picture(pic)
        pic = cv2.cvtColor(pic, cv2.COLOR_BGR2RGB)
    else:
        pic = get_picture_from_dataset()
    return pic

def save_last_picture(picture):
    path = os.path.join(path_to_folder,"last_image.jpg")
    if os.path.exists(path):
        os.remove(path)
    writingRes = cv2.imwrite(path, picture)
    return

def get_picture_from_dataset():
    parentDir = os.path.join(path_to_folder,"pictures")
    pic = os.path.join(parentDir,random.choice(os.listdir(parentDir)))
    img = cv2.imread(pic)

    save_last_picture(img)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    return img

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
        print("Someone els is using water, impossible to start now.")
        return False

    if DeviceData.client.is_connected():
        img = get_picture()

        # Copio le transform da applicare all'immagine
        input_size = 224
        data_transforms = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize(input_size),
        transforms.CenterCrop(input_size),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        x = data_transforms(img)
        x.unsqueeze_(0)
        y = DeviceData.model(x)
        # il primo valore è per la classe nopeole, il secondo per people, vince il max
        y = torch.argmax(y)
        if y == 0:
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
    if DeviceData.camera:
        DeviceData.camera.release()
    if rasp_build:
        GPIO.cleanup()
    sys.exit(0)

def f1(b:bool):
    print(f"someone else is using water:{not b}")
    set_led_value(DeviceData.network_led_pin, b)
    DeviceData.noOthers = b

def f2(b:bool):
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


    DeviceData.client = aimqtt.Core(f1,f2,config)	#here it will try to connect.


    #torch.set_num_threads(3) #setting 3 threads (out of 4)

    print("loading model..")
    model = torch.load(os.path.join(path_to_folder,"modello"))
    model.eval()
    DeviceData.model = model
    print("model loaded.")

    if rasp_build:
        thread.start_new_thread(start_camera_stream, ())

    if(rasp_build):
        setup_raspi()


    signal.signal(signal.SIGINT, signal_handler)
    if rasp_build:
        signal.pause()
    return



if __name__ == '__main__':
    if len(sys.argv) > 1:
        argv= sys.argv[1]
    else:
        argv= os.path.join(path_to_folder,"node_config.json")
    
    main_core(argv)