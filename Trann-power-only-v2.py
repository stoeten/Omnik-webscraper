# Trannergy inverter webscraper
#
from requests.auth import HTTPBasicAuth

import requests
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import time
import datetime
import sys
import warnings
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import json
from urllib.request import urlopen
import time
import datetime

from datetime import timedelta
from time import sleep

sun_url 	= "http://192.168.1.70:8888/json.htm?type=command&param=getSunRiseSet"		# Domoticz server
baseURL 	= 'http://192.168.1.70:8888/json.htm?type=command&param=udevice&nvalue=0'

TrannLoginAdress = 'http://admin:admin@192.168.1.76'									# Trannergyinverter fixed local IP adress BC-54-F9-F3-E2-B5
TrannIPAdress 	 = '192.168.1.76'	

INTERVAL 	= 120    	# default tijd tussen akties in sec
LOGFILE  	= '/ubuntu/Trann-scraper.log'
ENERGYFILE  = '/ubuntu/Trann-energy.log'

def suntimes():
	json_url= urlopen(sun_url)
	data 	= json.loads(json_url.read())

	hour 	= float(data["Sunset"][0:2])
	minute 	= float(data["Sunset"][3:5])
	dark 	= round(hour + minute /60 + 1, 2)
	#print(dark)

	hour 	= float(data["Sunrise"][0:2])
	minute 	= float(data["Sunrise"][3:5])
	light 	= round(hour + minute /60 - 0.4, 2)
	#print(light)

	return(light, dark)

def Ping(host):
    
    # Building the command. Ex: "ping -c 1 google.com"
    command = ['ping', '-c', '1', host]

    return subprocess.run(args=command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

def LogSchrijven(loginfo):
	f = open(LOGFILE, 'a')
	f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + ": " + str(loginfo) + "\n")
	f.close()

def EnergyLog(loginfo):
	text = str(loginfo)
	text = text.replace(".", ",")[:-4]			# replace . with , and remove the " kWh" at the end
	f = open(ENERGYFILE, 'a')
	f.write(text + datetime.datetime.now().strftime(" %Y-%m-%d") + "\n")
	f.close()

def Domoticz_update(power):
	url = baseURL + "&idx=%s&svalue=%s" % ("13", power)   			# use correct IDX; energy calculated by domoticz
	#LogSchrijven('P: %s' % power)
	try:
		r = requests.get(url)
	except requests.ConnectionError:
		pass		# ignore the exception and hope next time connection is there again
		LogSchrijven('Connection error to Domoticz')

def main():

	LogSchrijven('==== starting =============')

	options = Options()
	options.add_argument('--no-sandbox')
	options.add_argument('--headless')
	options.add_argument('--disable-dev-shm-usage')

	light, dark  = suntimes()
	driver_init = False

	try:
		while True:
			hour = round(datetime.datetime.now().hour + datetime.datetime.now().minute/60, 2)	# calculate hour in decimal
			wait_next_day = False
			if hour >= light and hour <= dark:					# daylight

				wait = INTERVAL

				if not driver_init:								# first time today
					light, dark = suntimes()
					LogSchrijven('Licht: Login and init driver van %0.1f' %light + ' tot %0.1f' %dark)

					if Ping(TrannIPAdress):									# check of omvormer bereikbaar
						Trann_running = True
						LogSchrijven('Omvormer: Normal mode')
					elif hour > (dark -2):									# omvormer niet bereikbaar en namiddag
						Trann_running = False
						wait_next_day = True
						LogSchrijven('Omvormer: niet bereikbaar; Namiddag dus wacht tot morgen')
					else:													# omvormer niet bereikbaar en ochtend
						LogSchrijven('Omvormer: niet bereikbaar; Wacht op Normal mode')
						while not Ping(TrannIPAdress):						# wacht tot bereikbaar
							sleep(INTERVAL)
						sleep(300)											# extra opstarttijd
						Trann_running = True
						LogSchrijven('Omvormer: Normal Mode')

					if Trann_running:
						driver = webdriver.Chrome(executable_path='/usr/bin/chromedriver',options=options)
						driver.get(TrannLoginAdress)
						driver_init = True
						LogSchrijven('Login succesvol en laden pagina gelukt')	
				else:
					driver.refresh()
					sleep(20)												# wellicht niet nodig?

				if driver_init:
					try:	
						s = WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "child_page")))
						#LogSchrijven('child_page loaded')
					except:
						LogSchrijven('Unable to load child_page')
						driver_init = False
						try:
							driver.close()											# close driver
							driver.quit()
						except:
							pass

				if driver_init:				
					try:
						s = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "webdata_now_p")))
					except:
						LogSchrijven("'Webdata_now_p missed")
						pass

					try:																# convert to integer
						#LogSchrijven('Trannergy power  : %s' % s.get_attribute("innerHTML"))
						powerstr = re.sub(' W', '', s.get_attribute("innerHTML"))		# remove " W"
						
						if powerstr == "---":											# return power is zero when not active
							power = 0
						else:
							power = int(powerstr)
					except ValueError:													# handle spurious empty string
						pass
						power = -1

					if power >= 0:
						Domoticz_update(power)

					if (powerstr == "---") and (abs(hour - dark) < 2): 					# omvormer gaat zo uit
						LogSchrijven('Omvormer gaat zo uit')
						s = driver.find_element_by_id("webdata_total_e")
						total_energy = s.get_attribute("innerHTML")
						EnergyLog(' %s' % total_energy)
						#LogSchrijven('Total energy: %s'% total_energy)
						driver.close()													# close driver
						driver.quit()
						driver_init 	= False
						wait_next_day 	= True

					wait = INTERVAL - 20												# compenseer de extra wachtijd na refresh

			elif (hour < light):														# risk of waiting too long
				wait = (light - hour) * 3600
				LogSchrijven('Early morning: wait till %0.1f' % light)
			elif hour > dark: 
				wait_next_day = True
			else:																		# early morning just before sunrise
				wait = INTERVAL

			if wait_next_day:
				wait = (24 - hour + light) * 3600
				wait_next_day = False
				LogSchrijven('Evening: wacht %0.1f' % (wait / 3600) + ' hrs tot %0.1f' % light)				

			#LogSchrijven('wait %0.1f (s)' % wait)
			sleep(wait)

	except (KeyboardInterrupt, OSError, RuntimeError):
		print("Unexpected error:", sys.exc_info()[0])
		LogSchrijven('Interrupted')
		if driver_init:
			driver.close()											# close driver
			driver.quit()
#------------- Voer Main uit ----------------------------------------------------------------------
main()
