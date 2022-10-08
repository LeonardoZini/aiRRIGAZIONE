/*
 * uMQTTBroker demo for Arduino
 * 
 * Minimal Demo: the program simply starts a broker and waits for any client to connect.
 */

#include <ESP8266WiFi.h>
#include "uMQTTBroker.h"

uMQTTBroker myBroker;

/*
 * Your WiFi config here
 */
char ssid[] = "airrigazione_WLAN";       // your network SSID (name) (if AP max 32 chars)
char pass[] = "airrigazione";   // your network password  (min 8 chars)
bool wiFiAP = true;      // Do yo want the ESP as AP?
uint16_t portNumber = 1883;

/*
 * WiFi init stuff
 */
void startWiFiClient()
{
  Serial.println("Connecting to "+(String)ssid);
  WiFi.begin(ssid, pass);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  
  Serial.println("WiFi connected");
  Serial.println("IP address: " + WiFi.localIP().toString());
}

void startWiFiAP()
{
  bool res = WiFi.softAP(ssid, pass);
  Serial.println("AP started at " +(String)ssid + " : " + res);
  Serial.println("IP address: " + WiFi.softAPIP().toString());
}

void setup()
{
  Serial.begin(115200);
  Serial.println();
  Serial.println();

  if(wiFiAP)
  {
    //start the ESP as AP
    startWiFiAP();
  }
  else  
  {
    // Connect to a WiFi network
    startWiFiClient();
  }

  // Start the broker
  Serial.println("Starting MQTT broker");
  myBroker = uMQTTBroker(portNumber);
  myBroker.init();
}

void loop()
{   
  // do anything here
  delay(1000);
}
