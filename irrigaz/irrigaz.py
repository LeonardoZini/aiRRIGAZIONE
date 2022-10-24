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



rasp_build=False #change if you are using pc client (not raspberry)
if(rasp_build):
	import RPi.GPIO as GPIO

if rasp_build:
	path_to_folder= os.path.join("/","home","pi","Desktop","airrigazione")
else:
	path_to_folder= os.path.join("irrigaz") #just for testing

rasp_configured=False


class CustomPushButton:
	def __init__(self, button_pin:int, led_pin:int, startValue=False):
		"""All pins MUST be defined as GPIO.BOARD. Pull-up resistors are enabled by software --> buttons must just connect to GND when pressed."""

		self.Value = startValue
		self.button_pin = button_pin
		self.led_pin = led_pin
		#button config
		GPIO.setmode(GPIO.BOARD)
		GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.add_event_detect(button_pin, GPIO.FALLING, callback=self.button_callback, bouncetime=200)
		#led config
		GPIO.setup(led_pin, GPIO.OUT)
		GPIO.output(led_pin, startValue)

	def button_callback(self, channel):
		self.Value = not self.Value
		#print("Button at pin ", self.button_pin," pressed. Newvalue:", self.Value)
		GPIO.output(self.led_pin, self.Value)
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
	last_frame = None
	timer = -1


def setup_raspi():
	print("setting raspberry pins..")
	DeviceData.camera = cv2.VideoCapture(0)

	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(DeviceData.irrigaz_led_pin ,GPIO.OUT)
	GPIO.setup(DeviceData.network_led_pin ,GPIO.OUT)
	GPIO.setup(DeviceData.sun_led_pin ,GPIO.OUT)

	GPIO.setup(DeviceData.picture_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

	DeviceData.webcam_switch = CustomPushButton(11,12,False)
	DeviceData.automatic_switch = CustomPushButton(15,16,True)

	global cameraButtonToggle
	cameraButtonToggle = False
	GPIO.add_event_detect(DeviceData.picture_button_pin, GPIO.FALLING, callback=camera_button_callback, bouncetime=200)

	global rasp_configured
	rasp_configured=True

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
			elaborate_picture()
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
	

def elaborate_picture():
	if DeviceData.watering or (not DeviceData.sun) or (not DeviceData.noOthers):
		return #if we are already irrigating, or there are not weather conditions, or someone else is using water

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
			thread.start_new_thread(activate_irrigation, ())
			print("the park is free..")
		else:
			print("There is someone in the park..")
	else:
		print("not connected. Impossible to send data.")
	return

def automatic_client():
	if(DeviceData.automatic_switch is not None and DeviceData.automatic_switch.Value) or (not rasp_build):
		elaborate_picture()
	threading.Timer(DeviceData.timer, automatic_client).start()


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

	automatic_client()
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