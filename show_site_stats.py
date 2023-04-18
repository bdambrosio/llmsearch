import requests
import json
import sys
import os
import io
import time
import string
from datetime import date
from datetime import datetime
import random


site_stats = {} # initialize dictionay of sites used

try:
  with open("site_stats.json", 'r') as f:
    site_stats = json.loads(f.read())
except:
  print('Failed to read site_stats.')

sites = {} # initialize dictionay or sites used
try:
  with open("sites.json", 'r') as f:
    sites = json.loads(f.read())
except:
  print('Failed to read sites.')

site_list = []
for site in site_stats.keys():
  site_list.append(site_stats[site])

# ordered, sort and compute cumulative
site_list.sort(reverse = True, key=lambda item: (item['chars']/(max(1000, item['get']+item['extract']+item['openai']))))

for site in site_list:
  total_time = max(1000, site['get']+site['extract']+site['openai'])
  if 'hits' in site.keys():
    hits = site['hits']
  else:
    hits = 0
  quality = int((site['chars']*1000000)/total_time)
  arg = ''
  if len(sys.argv) > 1: arg = sys.argv[1]
  print_site = False
  if ('new' in arg):
    if quality > 0 and site['name'] not in sites.keys(): print_site = True
  elif len(sys.argv) == 1 and quality > 0: print_site = True
  elif 'all' in arg: print_site = True
  elif quality > 0: print_site = True
  if print_site:
    print(site['name'], hits, site['chars'], quality, end='')
    if quality > 0 and site['name'] not in sites.keys():
      print('*')
    else: print()
