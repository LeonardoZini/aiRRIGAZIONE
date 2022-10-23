from ast import While
from http import client
import paho.mqtt.client as mqtt
import random
import time
import sys
import os
import json
import torch
import random
import cv2
import threading
import signal
import sys
import _thread as thread  # using Python 3

rasp_build=True #change if you are using pc client (not raspberry)
if(rasp_build):
	import RPi.GPIO as GPIO

path_to_folder= os.path.join("/","home","pi","Desktop","airrigazione")
#path_to_folder= os.path.join(".") #just for testing


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
	led_pin = 33
	picture_button_pin = 40

	webcam_switch:CustomPushButton=None
	automatic_switch:CustomPushButton=None

	camera = None 
	client = None
	city = None
	model = None
	ipBroker = None
	last_frame = None
	timer = -1


def setup_raspi():
	print("setting raspberry pins..")
	DeviceData.camera = cv2.VideoCapture(0)

	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(DeviceData.led_pin ,GPIO.OUT)
	GPIO.setup(DeviceData.picture_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

	DeviceData.webcam_switch = CustomPushButton(11,12,False)
	DeviceData.automatic_switch = CustomPushButton(15,16,True)

	GPIO.add_event_detect(DeviceData.picture_button_pin, GPIO.FALLING, callback=camera_button_callback, bouncetime=200)
	return

def start_camera_stream(): #different thread just to extract frames.
	while True:
		if(DeviceData.camera is not None):
			ret, frame = DeviceData.camera.read()
			if(ret):
				DeviceData.last_frame = frame


def camera_button_callback(channel):
	if DeviceData.automatic_switch.Value:
		return
	else:
		print("camera Button pressed!")
		elaborate_weather()


#read the switch and decide where to take from the picture (webcam/dataset).
def get_picture():
	if DeviceData.webcam_switch.Value:
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
	parentDir = os.path.join(path_to_folder,"sky_pictures")
	pic = os.path.join(parentDir,random.choice(os.listdir(parentDir)))
	img = cv2.imread(pic)

	save_last_picture(img)

	img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

	return img

def set_led_value(is_raining:bool):
	GPIO.output(DeviceData.led_pin, is_raining)
	return

def set_raining_value(is_raining :bool, city: str, client):
	"""A value True means it is going to rain."""
	if(is_raining):
		#print("It is going to rain.")
		topic = "{}/nowcasting/1".format(city)
	else:
		#print("no, it will not rain.")
		topic = "{}/nowcasting/0".format(city)

	if(rasp_build):
		set_led_value(is_raining)
	print("publishing: ", topic, time.asctime(time.localtime(time.time())))
	client.publish(topic)


def elaborate_weather():
	if DeviceData.client.is_connected():
		img = get_picture()
		result = DeviceData.model.evaluatePicture(img)
		set_raining_value(result,DeviceData.city,DeviceData.client)
	else:
		print("not connected. Impossible to send data.")
	return

def automatic_client():
	if(DeviceData.automatic_switch is not None and DeviceData.automatic_switch.Value):
		elaborate_weather()
	threading.Timer(DeviceData.timer, automatic_client).start()


def on_connect(client, userdata, flags, rc):
	print("Connected with result code "+str(rc))



def signal_handler(sig, frame):

	if DeviceData.camera:
		DeviceData.camera.release()

	GPIO.cleanup()
	sys.exit(0)

def main_core(argv):
	print(argv)

	torch.set_num_threads(3) #setting 3 threads (out of 4)

	print("loading model..")
	model = torch.load(os.path.join(path_to_folder,"modello"))
	model.eval()
	DeviceData.model = model
	print("model loaded.")

	print("starting mqtt client nowcaster..")

	f = open(argv)
	config = json.load(f)

	DeviceData.city = config['City']
	DeviceData.timer = config['RoutinePeriod'] #in seconds
	DeviceData.ipBroker = config["IpBroker"]
	print("timer: ", DeviceData.timer)

	client = mqtt.Client()
	DeviceData.client = client
	client.on_connect=on_connect
	client.will_set("{}/nowcasting/dead/".format(DeviceData.city))
	

	if rasp_build:
		thread.start_new_thread(start_camera_stream, ())

	automatic_client()
	if(rasp_build):
		setup_raspi()

	set_connection()

	signal.signal(signal.SIGINT, signal_handler)
	signal.pause()
	

def set_connection():
	try:
		client = DeviceData.client
		client.connect(DeviceData.ipBroker, 1883, 60)
		client.loop_start() #start the loop
	except:
		print("Impossible to start a connection to ", DeviceData.ipBroker,"; retrying in 5 seconds..")
		threading.Timer(5, set_connection).start()
		return
	return



if __name__ == '__main__':
	if len(sys.argv) > 1:
		argv=sys.argv[1]
		print()
	else:
		argv= os.path.join(path_to_folder,"node_config.json")
	
	main_core(argv)