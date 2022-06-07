#!/bin/bash
# automated script to update ubuntu docker image to a working ubuntu environment
##############################################################################################
if [ -f /installdone ] ; then
	echo  $(date +"%Y-%m-%d")" install already in place"		# start the execution of the Omnik python script
else
	echo "Install: common ubuntu utils"
	# Set timezone to prevent interactive request for this
	ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $CONTAINER_TIMEZONE > /etc/timezone

	apt-get update -y
	apt-get upgrade -y
	apt-get install -y tzdata
	apt-get install -y software-properties-common
	apt-get install -y iputils-ping
	apt-get install -y nano
	apt-get install -y python3-pip
	apt-get install -y unzip
	#
	echo "Install: wget, download chromedriver 88.0.4324.27"
	apt-get update -y
	apt-get install -y wget
	apt-get update -y
	touch /installdone
fi

