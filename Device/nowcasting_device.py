import paho.mqtt.client as mqtt
import random
import time


def on_connect(client, userdata, flags, rc):
	
	print("Connected with result code "+str(rc))
	client.subscribe("modena/#")
    

def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))


def main_core():
	client = mqtt.Client()
	client.on_connect=on_connect
	client.on_message=on_message

	#Il quarto topic era perchè altrimenti i client si rompono, da fixare :)
	client.will_set("modena/dead/nowcasting/kjhgf/")
	client.connect("localhost", 1883, 60)
	
	#5pippo

	print("Eccallà 1")
	while True:
		lvl = str(random.randrange(0,2))
		print(lvl)
		client.publish("modena/nowcasting/"+lvl)
		time.sleep(30)


if __name__ == '__main__':

	main_core()
	print("Rip")