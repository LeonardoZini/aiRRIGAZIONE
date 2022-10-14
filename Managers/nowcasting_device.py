import paho.mqtt.client as mqtt
import random
import time
import sys
import os
import json


def on_connect(client, userdata, flags, rc):
	
	print("Connected with result code "+str(rc))
	#client.subscribe("modena/#")
    

def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))


def main_core(argv):
	print(argv)
	print("starting mqtt client nowcaster..")

	f = open(argv)
	config = json.load(f)

	city = config['City']
	timeToWait = config['RoutinePeriod'] * 60

	client = mqtt.Client()
	client.on_connect=on_connect
	client.on_message=on_message
	#client.will_set("modena/nowcasting/dead/")
	client.will_set("{}/nowcasting/dead/".format(city))
	client.connect(config["IpBroker"], 1883, 60)
	
	#5pippo

	while True:
		lvl = str(random.randrange(0,2))
		print(lvl)
		#client.publish("modena/nowcasting/"+lvl)
		client.publish("{}/nowcasting/{}".format(city, lvl))
		time.sleep(timeToWait)
	

if __name__ == '__main__':
    if len(sys.argv) > 1:
        argv=sys.argv[1]
        print()
    else:
        argv= os.path.join("Managers","nowcaster_configs", "config1.json")
	
    main_core(argv)