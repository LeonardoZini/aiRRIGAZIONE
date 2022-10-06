import paho.mqtt.client as mqtt
import logging
import threading
import time
import schedule
import functools
import json
import sys


class Device:
    

    def __init__(self,city="",zone="", name="", status=False):
        self._city=city
        self._zone=zone
        self._name=name
        self._status=status

    def __str__(self):
        return "Device: "+self._city+"/"+self._zone+"/"+self._name+"\tstatus: "+str(self._status)

    def __repr__(self):
        return self.__str__()

    def __eq__(self,dev1):
        return (self._city==dev1._city and self._zone==dev1._zone and self._name==dev1._name)

    def change_status(self,status):
        _status=status

class MyDevice(Device):
    def __init__(self,city="",zone="", name="", status=False):
        super().__init__(city,zone,name,status)
        self._wait=False

    def change_wait(self, wait):
        self._wait=wait

class MQTTClient(mqtt.Client):

    _client_list=list()

    def __init__(self,dev:MyDevice):
        super().__init__()
        self._my_dev = dev
        self._queue=0

    def check_if_can_go(self):
        if(self._queue==0):
            self._my_dev.change_wait(False)
        else:
            self._my_dev.change_wait(True)


    def on_connect(self,client, userdata, flags, rc):
        print("Connected with result code " + str(rc))

        
        #AA111 da sostituire con conf filee
        client.publish("{}/add/{}/{}".format(
            self._my_dev._city, self._my_dev._zone,
            self._my_dev._name ))
        client.publish("{}/check".format(self._my_dev._city))
        #Mi iscrivo ai topic di interesse per la mia città
        client.subscribe("{}/#".format(self._my_dev._city))


    # The callback for when a PUBLISH message is received from the server.
    def on_message(self,client, userdata, msg):
        #print(msg.topic + " " + str(msg.payload))
        topic = str(msg.topic).split('/')

        if topic[1] == 'irrigaz':
            print("Irrigazione statement")
            dev_tmp=Device('modena',topic[2],topic[3])
            try:
                indx = self._client_list.index(dev_tmp)
                
                if topic[4] == 'start':
                    #Controlla che il client sia in stato False!
                    self._client_list[indx]._status=True
                    self._queue+=1
                    self.check_if_can_go()

                elif topic[4] == 'stop':
                    self._client_list[indx]._status=False
                    self._queue-=1
                    self.check_if_can_go()

                print(self._client_list[indx])            

            except ValueError:
                #Device non registrato nella lista
                pass

            

        elif topic[1] == 'nowcasting':
            print("Nowcasting Statement")

        elif topic[1] == 'add':
            
            dev_tmp=Device(topic[0],topic[2],topic[3])
            if dev_tmp not in self._client_list:
                print('New Device')
                self._client_list.append(dev_tmp)
                print(dev_tmp)

        elif topic[1] == 'dead':
            print("Will Statement")
            print(self._client_list)
            tmp = Device(topic[0],topic[2],topic[3])
            if tmp in self._client_list:
                self._client_list.remove(tmp)
            print(self._client_list)

        elif topic[1]=='check':
            client.publish("{}/add/{}/{}".format(
            self._my_dev._city, self._my_dev._zone,
            self._my_dev._name ))


def irrigaz(dev:MyDevice, client:MQTTClient, time_to_wait:int):
    print("Start routine..")
    print("Can We Go? "+str(not dev._wait))
    while dev._wait==True:
        print("Must wait...")
        time.sleep(time_to_wait)

    #MANCA DA TROVARE I NODI GIà IN RETE!
    #Manca gestione degli errori
    print("Inizio irrigaz..")
    dev.change_status(True)
    client.publish("{}/irrigaz/{}/{}/start".format(
            dev._city, dev._zone, dev._name))
    time.sleep(30)
    print("Fine irrigaz..")
    dev.change_status(False)
    client.publish("{}/irrigaz/{}/{}/stop".format(
            dev._city, dev._zone, dev._name))
    print("Publish message sent..")

def pending():
    while True:
        schedule.run_pending()
        time.sleep(1)

def main_core(argv):

    #Da inserire configurazione da File!!


    f = open(argv)
    config = json.load(f)


    this_device = MyDevice(config['City'],config['Park'],config['Code'])
    client = MQTTClient(this_device)

    '''
    client.will_set("{}/dead/{}/{}".format(
        this_device._city,
     this_device._zone, 
     this_device._name))
    '''

    client.will_set(this_device._city+"/dead/"+this_device._zone+"/"+this_device._name)
    client.connect("localhost", 1883, 60)

    print("start scheduler..")
    schedule.every(config['RoutinePeriod']).minutes.do(functools.partial(irrigaz,this_device, client, config['TimeToWait']))


    print("start client loop_forever")
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
        argv='config2.json'

    main_core(argv)
