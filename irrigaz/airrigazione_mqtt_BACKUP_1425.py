import device as dv
import json
import threading


#client = dv.MQTTClient(dv.MyDevice("test","test","test"))

class Core():
<<<<<<< HEAD
    
    # Config già parsato sulla parte che mi serve! 	callback1:irrigators ; callback2:nowcasting
    def __init__(self,callback1, callback2, config:dict):
        '''
        # Usato per fare test
        f = open(config_f)
        config = json.load(f)
        '''

        self.ipBroker = config["IpBroker"]
        self.my_dev = dv.MyDevice(config["City"], config["Park"], config["Code"]) 
        # Configurazione mqtt client
        self.mqtt_client = dv.MQTTClient(self.my_dev, callback1, callback2)
        self.mqtt_client.will_set(self.my_dev._city+"/dead/"+self.my_dev._zone+"/"+self.my_dev._name)

        self.logger = dv.logging.getLogger("core")
        self.logger.setLevel(dv.logging.INFO)

        self.set_connection()

    def set_connection(self):
        try:
            self.mqtt_client.connect(self.ipBroker, 1883, 60)
            self.mqtt_client.loop_start() #start the loop
        except:
            print("Impossible to start a connection to ", self.ipBroker,"; retrying in 5 seconds..")
            threading.Timer(5, self.set_connection).start()
            return
        return

    def is_connected(self):
        return self.mqtt_client.is_connected()

    # In base al valore che mi passi faccio la richiesta mqtt
    def set_irrigation_value(self, val:bool):
        if val==True:
            self.mqtt_client.publish(self.my_dev.irrigazStatement("start"))
        else:
            self.mqtt_client.publish(self.my_dev.irrigazStatement("stop"))
=======
	
	# Config già parsato sulla parte che mi serve! 	callback1:irrigators ; callback2:nowcasting
	def __init__(self,callback1, callback2, config:dict):
		'''
		# Usato per fare test
		f = open(config_f)
		config = json.load(f)
		'''
		self.my_dev = dv.MyDevice(config["City"], config["Park"], config["Code"]) 
		self.my_dev.set_coordinates(config["coordinates"]["lat"], config["coordinates"]["lon"])
		# Configurazione mqtt client
		self.mqtt_client = dv.MQTTClient(self.my_dev, callback1, callback2)
		self.mqtt_client.will_set(self.my_dev._city+"/dead/"+self.my_dev._zone+"/"+self.my_dev._name)
		self.mqtt_client.connect(config["IpBroker"], 1883, 60)

		self.logger = dv.logging.getLogger("core")
		self.logger.setLevel(dv.logging.INFO)

		self.mqtt_client.loop_start()

	# In base al valore che mi passi faccio la richiesta mqtt
	def set_irrigation_value(self, val:bool):
		if val==True:
			self.mqtt_client.publish(self.my_dev.irrigazStatement("start"))
		else:
			self.mqtt_client.publish(self.my_dev.irrigazStatement("stop"))
>>>>>>> 0cdcc7bea8cf33bb18f7a9fecd6b93a142601a2a



        
        