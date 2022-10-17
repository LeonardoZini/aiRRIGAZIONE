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

rasp_build=True
if(rasp_build):
	import RPi.GPIO as GPIO

class RaspConfig:
	led_pin = 15
	source_switch_pin = 11
	picture_button_pin = 13
	manual_camera = True

	#to be filled in runtime
	camera = None 
	client = None
	city = None
	model = None
	last_frame = None
	timer = -1


def setup_raspi():
	RaspConfig.camera = cv2.VideoCapture(0)
	thread.start_new_thread(start_camera_stream, ())

	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(RaspConfig.led_pin ,GPIO.OUT)
	GPIO.setup(RaspConfig.picture_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
	GPIO.setup(RaspConfig.source_switch_pin, GPIO.IN)

	GPIO.add_event_detect(RaspConfig.picture_button_pin, GPIO.FALLING, callback=camera_button_callback, bouncetime=200)
	GPIO.add_event_detect(RaspConfig.source_switch_pin, GPIO.BOTH, callback=switch_callback, bouncetime=500)

	switch_callback(None)
	return

def start_camera_stream(): #different thread just to extrcat frames.
	while True:
		ret, frame = RaspConfig.camera.read()
		if(ret):
			RaspConfig.last_frame = frame

def switch_callback(channel):
	pin_value = GPIO.input(RaspConfig.source_switch_pin)
	if pin_value and not RaspConfig.manual_camera:
		print("-----Switched to manual-----")
		RaspConfig.manual_camera = True

	if not pin_value and RaspConfig.manual_camera:
		print("-----Switched to automatic-----")
		RaspConfig.manual_camera = False
		automatic_client()

	return

def camera_button_callback(channel):
	if not RaspConfig.manual_camera:
		return
	else:
		print("camera Button pressed!")
		elaborate_weather()


#read the switch and decide where to take from the picture (webcam/dataset).
def get_picture():
	if RaspConfig.manual_camera:

		#grabbed, pic = RaspConfig.camera.read()
		pic = RaspConfig.last_frame
		save_last_picture(pic)
		pic = cv2.cvtColor(pic, cv2.COLOR_BGR2RGB)

	else:
		pic = get_picture_from_dataset()
	return pic

def save_last_picture(picture):
	path = "last_image.jpg"
	if os.path.exists(path):
		os.remove(path)
	writingRes = cv2.imwrite(path, picture)
	return

def get_picture_from_dataset():
	parentDir = "sky_pictures"
	_, dirs, _ = next(os.walk(parentDir))
	category = os.path.join(parentDir, random.choice(dirs))
	pic = os.path.join(category,random.choice(os.listdir(category)))
	img = cv2.imread(pic)

	save_last_picture(img)

	img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

	return img

def set_led_value(is_raining:bool):
	GPIO.output(RaspConfig.led_pin, is_raining)
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
	print("publishing: ", topic)
	client.publish(topic)


def elaborate_weather():
	if RaspConfig.client.is_connected():
		img = get_picture()
		result = RaspConfig.model.evaluatePicture(img)
		set_raining_value(result,RaspConfig.city,RaspConfig.client)
	else:
		print("not connected. Impossible to send data.")
	return

def automatic_client():
	if(RaspConfig.manual_camera):
		return
	elaborate_weather()
	threading.Timer(RaspConfig.timer, automatic_client).start()


def on_connect(client, userdata, flags, rc):
	print("Connected with result code "+str(rc))



def signal_handler(sig, frame):

	if RaspConfig.camera:
		RaspConfig.camera.release()

	GPIO.cleanup()
	sys.exit(0)

def main_core(argv):
	print(argv)

	torch.set_num_threads(3) #setting 3 threads (out of 4)

	print("loading model..")
	model = torch.load("modello")
	model.eval()
	RaspConfig.model = model
	print("model loaded.")

	print("starting mqtt client nowcaster..")

	f = open(argv)
	config = json.load(f)

	RaspConfig.city = config['City']
	RaspConfig.timer = config['RoutinePeriod'] #in seconds
	print("timer: ", RaspConfig.timer)

	client = mqtt.Client()
	RaspConfig.client = client
	client.on_connect=on_connect
	client.will_set("{}/nowcasting/dead/".format(RaspConfig.city))

	print("trying to connect to ip ",config["IpBroker"])
	client.connect(config["IpBroker"], 1883, 60)
	client.loop_start() #start the loop

	if(rasp_build):
		setup_raspi()

	signal.signal(signal.SIGINT, signal_handler)
	signal.pause()

if __name__ == '__main__':
	if len(sys.argv) > 1:
		argv=sys.argv[1]
		print()
	else:
		argv= "node_config.json"
	
	main_core(argv)