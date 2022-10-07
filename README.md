# aiRRIGAZIONE
README for the group work for IoT exam.<br>
Students: Leonardo Zini, Pietro Martinello and Giovanni Casari

## Topic format
  ### For notify others that a new device is online
  #### \<city\>/add/\<park\>/\<zone\><br>
  Topic used when the device turns on or another device need a check
  ### For notify others that the device who sent the message is dead
  #### \<city\>/dead/\<park\>/\<zone\><br>
  Topic used when the device turns off
  ### For notify others that a device start or stop to irrigating 
  #### \<city\>/irrigaz/\<park>/\<zone\>\<value\><br>
  The value must be 'start' or 'stop' to notify the change of status, other value will not be considered
  ### For a new device that turn on that need to discover other online devices
  #### \<city>/check/\<park>/\<zone\><br>
  When a device turns on, it need to discover other online devices, and this is the topic for this purpose
  ### For nowcasting mechanism, when the nowcasting device wants to comunicate
  #### \<city>/nowcasting/\<value\><br>
  The value must be '0' for sunny values, '1' for rainy values and 'dead' when the device turns offline
  
  
## Config file format

{<br>
	"City": string,       #City where the device is located <br>
	"Park": string,       #Park where the device is locater<br>
	"Code": string,       #Code of the device, must be pseudorandom<br>
	"RoutinePeriod": int, #The interval of the irrigation routine <br>
	"TimeToWait": int     #Time to wait if there are no conditions for watering <br>
}<br>
