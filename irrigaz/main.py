import airrigazione_mqtt as aimqtt
import sys
import os 
import random
import time
import json


def f1(b:bool):
	print(f"Irrigaz callback. val:{b}")

def f2(b:bool):
	print(f"Nowcasting callback. val:{b}")



if len(sys.argv) > 1:
    argv=os.path.join(".","irrigaz","irrigation_configs", sys.argv[1])
else:
    argv= os.path.join(".","irrigaz","irrigation_configs", "config1.json")

print(argv)
f = open(argv)
config = json.load(f)
tmp = aimqtt.Core(f1,f2,config)
val=0
