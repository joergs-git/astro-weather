#!/bin/bash
cd /volume1/homes/klaasjoerg/astro_weather_script/astro_weather
source ./.env
/usr/bin/python3.8 scheduler.py --single
