import paho.mqtt.client as mqtt
import logging
import threading
import time
import schedule
import functools
import json
import sys
import os

#Classe dedicata al nowcaster, struttura che raccoglie i dati che comunica il nowcaster
class NowCaster():

	def __init__(self):
		#Assumiamo che di default sia funzionante e che ci sia il sole
		self.status = True  # Dispositivo funzionante o meno
		self.sun = True     # Valore attuale del cielo


#Struttura che contiene i dati degli altri dipositivi della rete
class Device:
	
	def __init__(self,city="",zone="", name="", status=False):
		self._city = city #Citta
		self._zone = zone #Parco
		self._name = name #Zona/ID
		self._status = status # True se il dispositivo sta annaffiando, False altrimenti

	def __str__(self):
		return "Device: "+self._city+"/"+self._zone+"/"+self._name+"\tstatus: "+str(self._status)

	def __repr__(self):
		return self.__str__()


	# NOTA: l'uguaglianza non tiene conto dello status siccome non viene specificato nel topic.
	def __eq__(self,dev1):
		return (self._city == dev1._city and self._zone == dev1._zone and self._name == dev1._name)
 
	#Cambia lo stato del dispositivo quando si riceve uno statement di irrigazione
	def change_status(self,status):
		self._status = status

#Classe per gestire il device su cui gira lo scriprìt
class MyDevice(Device):
	def __init__(self,city="",zone="", name="", status=False):
		super().__init__(city,zone,name,status)
		self._nowcaster = NowCaster()
		self.lat = 0.0
		self.lon = 0.0

	def set_coordinates(self,lat:float, lon:float):
		self.lat=lat
		self.lon=lon

	def get_coordinates(self):
		return f"lat={self.lat}&lon={self.lon}"



	def addStatement(self):
		return f"{self._city}/add/{self._zone}/{self._name}"

	def irrigazStatement(self, status):
		return f"{self._city}/irrigaz/{self._zone}/{self._name}/{status}"


class MQTTClient(mqtt.Client):
	
	def __init__(self,dev:MyDevice, callback_irr, callback_now):
		super().__init__()
		self._my_dev = dev  #Aggiungo un my_dev per gestire e memorizzare meglio le richieste
		self._clients_dict = {}
		self.water_busy = False
		
		self.logger = logging.getLogger("mqtt") 
		self.logger.setLevel(logging.INFO)
		
		self.logger.info(f"device info: {dev}")
		# self.logger.info("start client loop_forever")

		self.callback_irr = callback_irr
		self.callback_now = callback_now

	def check_if_water_use_changed(self):
		is_busy = False
		for dev in self._clients_dict.values():
			if dev._status:
				is_busy = True
				break

		if self.water_busy != is_busy:
			self.water_busy = is_busy
			self.callback_irr(not is_busy)
		return



	def on_connect(self, client, userdata, flags, rc):
		self.logger.info("Connected with result code " + str(rc))
		self._clients_dict.clear()
		
		#Pubblico add statement, comunico che il device è online
		client.publish(self._my_dev.addStatement(), payload=self._my_dev.get_coordinates())

		#Check statement, chiedo quali altri dispositivi sono online
		client.publish("{}/check".format(self._my_dev._city))

		#Mi iscrivo ai topic di interesse per la mia città
		client.subscribe("{}/#".format(self._my_dev._city))


	# The callback for when a PUBLISH message is received from the server.
	def on_message(self,client, userdata, msg):
		topic = str(msg.topic).split('/')

		if len(topic) > 3:
			#avoiding self-messages
			if topic[1] != "nowcasting" and topic[3] == self._my_dev._name:
				return

		#Controllo il secondo campo del topic, che è quello che specifica il comando
		if topic[1] == 'irrigaz':
			self.logger.info(f"watering statement from {topic[2]}/{topic[3]}")
			dev_tmp = Device(self._my_dev._city,topic[2],topic[3])
			park_id = topic[3]

			if park_id not in self._clients_dict:
				#Device non registrato nella lista
				self.logger.warning("watering statement from a device not registered")
				return
			other = self._clients_dict[park_id]
			
			if topic[4] == 'start':
				'''
				Teniamo comunque traccia di tutti gli irrigatori della città anche se non sono del nostro parco
				per poter estendere la decisione tenendo conto anche degli altri parchi in un futuro
				'''
				other._status = True
				self.check_if_water_use_changed()
				
			elif topic[4] == 'stop':
				other._status = False
				self.check_if_water_use_changed()

			self.logger.info(other)            

			
		elif topic[1] == 'nowcasting':

			self.logger.info(f"nowcasting statement (0 sun, 1 rain, dead :( ): {topic[2]}")
			if topic[2] == '0' or topic[2] == '1':
				lvl = topic[2]

				# Setto il valore del cielo che ricevo nell'istanza nowcaster del mio device
				sun = int(lvl) == 0
				
				# CHIAMARE CALLBACK (SE LE CONDIZIONI CAMBIANO)
				# sun: false self.sun:true -> false
				# sun:true self.sun:false  -> true
				# quindi nella callback passo come parametro il valore di sun
				# se non erro

				if sun != self._my_dev._nowcaster.sun:
					self.callback_now(sun)
					self._my_dev._nowcaster.sun = sun

				

				# Se ricevo una publish da parte del nowcaster ed era "morto" lo riconsidero attivo
				# così nella parte decisionale lo torno a prendere in considerazione
				if self._my_dev._nowcaster.status == False:
					self._my_dev._nowcaster.status = True 
			elif topic [2] == 'dead':
				self._my_dev._nowcaster.status = False # Nowcaster offline

				self._my_dev.sun=True   # Se il nowcaster non va consideriamo che ci sia il sole, così nel dubbio annaffiamo
				self.callback_now(True)
				self.logger.warning("nowcasting device is offline") # Non viene notificato quando torna online, ma viene rilevato e funziona

		elif topic[1] == 'add':
			park_id = topic[3]
			if park_id not in self._clients_dict:
				#Device non registrato nella lista
				dev=Device(topic[0],topic[2], park_id)
				self._clients_dict[park_id] = dev
				self.logger.info(f"new device-> {dev._zone}/{dev._name}; status->{dev._status}")

		elif topic[1] == 'dead':
			park_id = topic[3]
			if park_id in self._clients_dict:
				dev = self._clients_dict.pop(park_id)
				self.check_if_water_use_changed()
				self.logger.info(f"will statement, {dev._zone}/{dev._name} is dead")

		elif topic[1]=='check':
			client.publish(self._my_dev.addStatement(), payload=self._my_dev.get_coordinates())

