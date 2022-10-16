import airrigazione_mqtt as aimqtt
import sys
import os 
import random 


def f1(b:bool):
	print(f"Irrigaz callback. val:{b}")

def f2(b:bool):
	print(f"Nowcasting callback. val:{b}")



if len(sys.argv) > 1:
    argv=os.path.join("Managers","irrigation_configs", sys.argv[1])
else:
    argv= os.path.join("Managers","irrigation_configs", "config1.json")

r_argv="..\\" + argv
print(r_argv)
tmp = aimqtt.Core(f1,f2,r_argv)
val=0

while True:
    while val<20:
        tmp.start_mqtt(t_out=3)
        val+=1
    val=0

    tmp.set_irrigation_value(True)