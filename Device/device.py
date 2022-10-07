import paho.mqtt.client as mqtt
import logging
import threading
import time
import schedule
import functools
import json
import sys

#Classe dedicata al nowcaster, struttura che raccoglie i dati che comunica il nowcaster
class NowCaster():

    def __init__(self):
        #Assumiamo che di default sia funzionante e che ci sia il sole (lvl=0)
        self.status = True
        self.lvl = 0


#Struttura che contiene i dati degli altri dipositivi della rete
class Device:
    
    def __init__(self,city="",zone="", name="", status=False):
        self._city = city
        self._zone = zone
        self._name = name
        self._status = status

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
        return f"{self._city}/irrigaz/{self._zone}/{self._name}/{value}"


class MQTTClient(mqtt.Client):

    _client_list = list()

    def __init__(self,dev:MyDevice):
        super().__init__()
        self._my_dev = dev  #Aggiungo un my_dev per gestire e memorizzare meglio le richieste
        self._queue = 0     #Contatore che tiene in memoria quanti dispositivi stanno annaffiando o hanno fatto richiesta
        self.logger = logging.getLogger("mqtt") 


    #Controllo se posso partire con l'irrigazione da questo dispositivo
    def check_if_can_go(self):
        if(self._queue == 0):
            self._my_dev.change_wait(False)
        else:
            self._my_dev.change_wait(True)


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
                    #Controlla che il client sia in stato False!
                    self._client_list[indx]._status = True
                    self._queue += 1
                    self.check_if_can_go()

                elif topic[4] == 'stop':
                    self._client_list[indx]._status = False
                    self._queue -= 1
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
                self._my_dev._nowcaster.lvl = int(lvl)
                if self._my_dev._nowcaster.status == False: self._my_dev._nowcaster.status = True 
            else:
                #Nowcaster offline
                self._my_dev._nowcaster.status = False
                #Non viene notificato quando torna online, ma viene rilevato e funziona
                self.logger.warning("nowcasting device is offline")

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
                    self.check_if_can_go()
                self._client_list.remove(tmp)

            self.logger.info(f"will statement, {tmp._zone}/{tmp._name} is dead")

        elif topic[1]=='check':
            client.publish(self._my_dev.addStatement())


#Funzione che implementa il codice per la parte hardware dell'irrigazione
def irrigaz(dev:MyDevice, client:MQTTClient, time_to_wait:int):
    logger = logging.getLogger("watering")
    logger.info("start routine..")
    logger.info("can go? "+str(not dev._wait))
    while dev._wait == True:
        logger.info("must wait...")
        time.sleep(time_to_wait)
    logger.info("can go now!!")
    #Manca gestione degli errori 

    logger.info("start watering procedure..")
    dev.change_status(True)
    client.publish(dev.irrigazStatement("start"))
    time.sleep(30)
    logger.info("watering end..")
    dev.change_status(False)
    client.publish(dev.irrigazStatement("stop"))
    logger.info("publish message sent..")

def pending():
    while True:
        schedule.run_pending()
        time.sleep(1)

def main_core(argv):

    f = open(argv)
    config = json.load(f)


    this_device = MyDevice(config['City'],config['Park'],config['Code'])
    client = MQTTClient(this_device)

    client.will_set(this_device._city+"/dead/"+this_device._zone+"/"+this_device._name)
    client.connect("localhost", 1883, 60)

    logger = logging.getLogger()

    logger.setLevel(logging.INFO)

    logging.info(f"device info: {this_device}")
    logging.info("start scheduler..")
    schedule.every(config['RoutinePeriod']).minutes.do(functools.partial(irrigaz,this_device, client, config['TimeToWait']))


    logging.info("start client loop_forever")
    t_client =threading.Thread(target=client.loop_forever)
    t_client.start()

    t_sched = threading.Thread(target=pending)
    t_sched.start()
    t_sched.join()

    t_client.join()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        argv=sys.argv[1]
        print()
    else:
        argv='config1.json'

    main_core(argv)
