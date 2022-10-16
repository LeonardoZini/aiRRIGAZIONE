import device as dv
import json


#client = dv.MQTTClient(dv.MyDevice("test","test","test"))

class Core():
	
	# Config già parsato sulla parte che mi serve! 	callback1:irrigators ; callback2:nowcasting
	def __init__(self,callback1, callback2, config:dict):
		'''
		Usato per fare test
		f = open(config_f)
		config = json.load(f)
		'''
		self.my_dev = dv.MyDevice(config["City"], config["Park"], config["Code"]) 
		# Configurazione mqtt client
		self.mqtt_client = dv.MQTTClient(self.my_dev, callback1, callback2)
		self.mqtt_client.will_set(self.my_dev._city+"/dead/"+self.my_dev._zone+"/"+self.my_dev._name)
		self.mqtt_client.connect(config["IpBroker"], 1883, 60)

		self.logger = dv.logging.getLogger("core")
		self.logger.setLevel(dv.logging.INFO)



	# In base al valore che mi passi faccio la richiesta mqtt
	def set_irrigation_value(self, val:bool):
		if val==True:
			self.mqtt_client.publish(self.my_dev.irrigazStatement("start"))
		else:
			self.mqtt_client.publish(self.my_dev.irrigazStatement("stop"))

	def start_mqtt(self, t_out=3, forever=False):
		if forever: 
			self.mqtt_client.loop_forever()
		else:
			self.mqtt_client.loop(timeout=t_out)



        
		