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
        self._wait = False
        self._nowcaster = NowCaster()

    def change_wait(self, wait):
        self._wait = wait

    def addStatement(self):
        return f"{self._city}/add/{self._zone}/{self._name}"

    def irrigazStatement(self, status):
        return f"{self._city}/irrigaz/{self._zone}/{self._name}/{status}"


class MQTTClient(mqtt.Client):

    _client_list = list()

    def __init__(self,dev:MyDevice, callback_irr, callback_now):
        super().__init__()
        self._my_dev = dev  #Aggiungo un my_dev per gestire e memorizzare meglio le richieste
        self._queue = 0     #Contatore che tiene in memoria quanti dispositivi stanno annaffiando o hanno fatto richiesta
        
        self.logger = logging.getLogger("mqtt") 
        self.logger.setLevel(logging.INFO)
        
        self.logger.info(f"device info: {dev}")
        # self.logger.info("start client loop_forever")

        self.callback_irr = callback_irr
        self.callback_now = callback_now

    #Controllo se posso partire con l'irrigazione da questo dispositivo
    def check_if_can_go(self):
        if(self._queue == 0):
            self._my_dev.change_wait(False)
            return False
        else:
            self._my_dev.change_wait(True)
            return True


    def on_connect(self, client, userdata, flags, rc):
        self.logger.info("Connected with result code " + str(rc))

        
        #Pubblico add statement, comunico che il device è online
        client.publish(self._my_dev.addStatement())

        #Check statement, chiedo quali altri dispositivi sono online
        client.publish("{}/check".format(self._my_dev._city))

        #Mi iscrivo ai topic di interesse per la mia città
        client.subscribe("{}/#".format(self._my_dev._city))


    # The callback for when a PUBLISH message is received from the server.
    def on_message(self,client, userdata, msg):
        topic = str(msg.topic).split('/')

        #Controllo il secondo campo del topic, che è quello che specifica il comando
        if topic[1] == 'irrigaz':
            self.logger.info(f"watering statement from {topic[2]}/{topic[3]}")
            dev_tmp = Device(self._my_dev._city,topic[2],topic[3])
            try:
                indx = self._client_list.index(dev_tmp)
                
                if topic[4] == 'start':

                    '''
                    Teniamo comunque traccia di tutti gli irrigatori della città anche se non sono del nostro parco
                    per poter estendere la decisione tenendo conto anche degli altri parchi in un futuro
                    '''
                    self._client_list[indx]._status = True

                    #Controlla che il client sia in stato False!
                    if topic[2] == self._my_dev._zone and topic[3] != self._my_dev._name:
                        # Se qualcuno inizia ad irrigare e ne avevo segnati 0 allora io non posso più
                        if self._queue==0:
                            self.callback_irr(False)

                        self._queue += 1
                        self.check_if_can_go()

                elif topic[4] == 'stop':
                    self._client_list[indx]._status = False
                    if topic[2] == self._my_dev._zone and topic[3] != self._my_dev._name:
                        self._queue -= 1

                        # Se da 1 passo a 0 allora tornano le condizioni
                        if self._queue == 0: 
                            self.callback_irr(True)
                        self.check_if_can_go()

                self.logger.info(self._client_list[indx])            

            except ValueError:
                #Device non registrato nella lista
                self.logger.warning("watering statement from a device not registered")
                pass

            
        elif topic[1] == 'nowcasting':

            self.logger.info(f"nowcasting statement (0 sun, 1 rain, dead :( ): {topic[2]}")
            if topic[2] != 'dead':
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
            else:
                self._my_dev._nowcaster.status = False # Nowcaster offline

                self._my_dev.sun=True   # Se il nowcaster non va consideriamo che ci sia il sole, così nel dubbio annaffiamo

                self.logger.warning("nowcasting device is offline") # Non viene notificato quando torna online, ma viene rilevato e funziona

        elif topic[1] == 'add':
            
            dev_tmp=Device(topic[0],topic[2],topic[3])
            if dev_tmp not in self._client_list:                
                self._client_list.append(dev_tmp)
                self.logger.info(f"new device-> {dev_tmp._zone}/{dev_tmp._name}; status->{dev_tmp._status}")

        elif topic[1] == 'dead':
            
            #Problema: qui lo stato di tmp è per forza falso, come faccio a controllare se invece era true?
            #Risolto, messa una pezza 
            tmp = Device(topic[0],topic[2],topic[3])
            if tmp in self._client_list:
                #Devo fare cosi per recuperare l'oggetto nella lista vero
                if self._client_list[self._client_list.index(tmp)]._status == True:
                    self._queue-=1
                    if self.queue == 0 : 
                        self.callback_irr(True)
                    self.check_if_can_go()
                self._client_list.remove(tmp)

            self.logger.info(f"will statement, {tmp._zone}/{tmp._name} is dead")

        elif topic[1]=='check':
            client.publish(self._my_dev.addStatement())




'''
def main_core(argv):

    f = open(argv)
    config = json.load(f)


    this_device = MyDevice(config['City'],config['Park'],config['Code'])
    client = MQTTClient(this_device)

    client.will_set(this_device._city+"/dead/"+this_device._zone+"/"+this_device._name)
    client.connect(config["IpBroker"], 1883, 60)

    logger = logging.getLogger()

    logger.setLevel(logging.INFO)

    logging.info(f"device info: {this_device}")
    logging.info("start scheduler..")


    logging.info("start client loop_forever")
    t_client =threading.Thread(target=client.loop_forever)
    t_client.start()
    t_client.join()

'''