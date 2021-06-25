import json
import numpy as np
from ..abc.lookup import Lookup
from pymemcache.client import base

import logging

L = logging.getLogger(__name__)

###

L = logging.getLogger(__name__)

###


class Memcachedookup(Lookup):

	ConfigDefaults = {
		'max_size': '',
		'expiry_seconds': 3600,
		'memcache': '127.0.0.1:11211',
	}


	def __init__(self, app, max_size=1000, expiry_seconds=0, memcache = None):
		super().__init__()

		self.App = app
		self.MaxSize = max_size
		self.Expiration = expiry_seconds
		self.Target = None

		if memcache:
			self.Client = base.Client(tuple(memcache.split(":")))
		else:
			raise Exception("Memcache service path not set.")


	def rest_get(self, to_chache: dict):
		for key, value in to_chache.items():
			returned = self.Client.set(key, value, expire=self.Expiration)
		if returned is not True:
			L.warning("Setting a memcached key-value failed")
		L.debug("Successfully set key-value")

	def get(self, key):
		return self.Client.get(key)

	def delete(self ,key):
		self.Client.delete(key)
		L.debug("Deleted {} form memcache.".format(key))


	def close_connection(self):
		self.Client.close()
		L.info("Closed connection to memcache")


	def flush_all(self):
		self.Client.flush_all()
		L.info("Chache flushed")
