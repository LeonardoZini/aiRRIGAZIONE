import requests
import json
import datetime
import osmnx as ox
import paho.mqtt.client as mqtt

def get_forecast_info(city:string, m_client=mqtt.Client):
	t = ox.geocode_to_gdf({'city':city})
	today = datetime.datetime.now().strftime("%Y-%m-%d")

	lat = t["lat"][0]
	lon = t["lon"][0]
	# Modena: 44.643706, 10.927194
	r=requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&start_date={today}&end_date={today}&hourly=temperature_2m,relativehumidity_2m,windspeed_10m")

	m_client.publish(f"{city}/nowcasting/info", payload=r.text)
	#return r.text