# OMNIK inverter webscraper
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

import json
from urllib.request import urlopen
import time
import datetime

from datetime import timedelta
from time import sleep

sun_url 	= "http://192.168.1.70:8888/json.htm?type=command&param=getSunRiseSet"		# Domoticz server
baseURL 	= 'http://192.168.1.70:8888/json.htm?type=command&param=udevice&nvalue=0'

OmnikAdress = 'http://192.168.1.75'									# Omnik inverter fixed local IP adress

INTERVAL 	= 120    	# default tijd tussen akties in sec
LOGFILE  	= '/ubuntu/Omnik-scraper.log'
ENERGYFILE  = '/ubuntu/Omnik-energy.log'

def suntimes():
	json_url= urlopen(sun_url)
	data 	= json.loads(json_url.read())

	hour 	= float(data["Sunset"][0:2])
	minute 	= float(data["Sunset"][3:5])
	dark 	= round(hour + minute /60 + 1, 2)
	#print(dark)

	hour 	= float(data["Sunrise"][0:2])
	minute 	= float(data["Sunrise"][3:5])
	light 	= round(hour + minute /60 - 0.5, 2)
	#print(light)

	return(light, dark)

def LogSchrijven(loginfo):
	f = open(LOGFILE, 'a')
	f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + ": " + str(loginfo) + "\n")
	f.close()

def EnergyLog(loginfo):
	text = str(loginfo)
	text = text.replace(".", ",")[:-4]			# replace . with , and remove the " kWh" at the end
	f = open(ENERGYFILE, 'a')
	f.write(datetime.datetime.now().strftime("%Y-%m-%d ") + text + "\n")
	f.close()

def Domoticz_update(power):
	url = baseURL + "&idx=%s&svalue=%s" % ("12", power)   			# use correct IDX; energy calculated by domoticz
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
	browser_init = False

	try:
		while True:
			hour = round(datetime.datetime.now().hour + datetime.datetime.now().minute/60, 2)	# calculate hour in decimal
			if hour >= light and hour <= dark:					# daylight

				if not browser_init:								# first time today
					light, dark = suntimes()
					LogSchrijven('Licht: Login and init browser van %0.1f' %light + ' tot %0.1f' %dark)
					res = requests.post(OmnikAdress, verify=False, auth=HTTPBasicAuth('admin', 'admin'))
					browser = webdriver.Chrome(executable_path='/usr/bin/chromedriver',options=options)
					browser_init     = True
					sleep(3)

				try:
					browser.get(OmnikAdress)				# retrieve the screen and swith to the child page
					s = WebDriverWait(browser, 20).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "child_page")))
					#browser.switch_to.frame('child_page')
				except: 
					LogSchrijven('Unable to load child_page')
					browser_init = False
					try:
						browser.close()											# close browser
						browser.quit()	
					except:
						pass
				else:
					sleep(3)
					s = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "webdata_now_p")))
					try:																# convert to integer
						#LogSchrijven('Omnik power  : %s' % s.get_attribute("innerHTML"))
						powerstr = re.sub(' W', '', s.get_attribute("innerHTML"))		# remove " W"
						power = int(powerstr)	
					except ValueError:													# handle spurious empty string
						pass
						power = -1

					if power >= 0:
						Domoticz_update(power)

				wait = INTERVAL

			elif hour > dark: 	                 					# donker
				if browser_init:
					s = browser.find_element_by_id("webdata_total_e")
					total_energy = s.get_attribute("innerHTML")
					EnergyLog(' %s' % total_energy)
					browser.close()									# close browser
					browser.quit()	
					browser_init = False

				wait = (24 - hour + light) * 3600
				LogSchrijven('Evening: wacht %0.1f' % (wait / 3600) + ' hrs tot %0.1f' % light)

			elif (hour < light):								# risk of waiting too long
				wait = (light - hour) * 3600
				LogSchrijven('Early morning: wait till %0.1f' % light)

			else:													# early morning just before sunrise
				wait = INTERVAL

			sleep(wait)

	except (KeyboardInterrupt, OSError, RuntimeError):
		print("Unexpected error:", sys.exc_info()[0])
		LogSchrijven('Interrupted')
		if browser_init:
			browser.close()											# close browser
			browser.quit()	
#------------- Voer Main uit ----------------------------------------------------------------------
main()
