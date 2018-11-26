import time
import logging

import numpy as np

import asab

from .analyzer import Analyzer

###

L = logging.getLogger(__name__)

###

class TimeWindow(object):

	'''
    ## Time window

    --> Columns (time dimension), column "width" = resolution
	+---+---+---+---+---+---+
	|   |   |   |   |   |   |
	+---+---+---+---+---+---+
	|   |   |   |   |   |   |
	+---+---+---+---+---+---+
	|   |   |   |   |   |   |
	+---+---+---+---+---+---+
	|   |   |   |   |   |   |
	+---+---+---+---+---+---+
	|   |   |   |   |   |   |
	+---+---+---+---+---+---+
	^                       ^
	End (past)   <          Start (== now)

	'''


	def __init__(self, app, pipeline, resolution=60, columns=15, start_time):

		if start_time is None:
			start_time = time.time()

		self.Resolution = resolution
		self.Columns = columns

		self.Start = (1 + (start_time // self.Resolution)) * self.Resolution
		self.End = self.Start - (self.Resolution * self.Columns)
		self.Matrix = None

		self.RowMap = {}
		self.RevRowMap = {}


		metrics_service = app.get_service('asab.MetricsService')
		self.Counters = metrics_service.create_counter(
			"counters",
			tags={
				'pipeline': pipeline.Id,
				'tw': "TimeWindow",
			},
			init_values={
				'events.early': 0,
				'events.late': 0,
			}
		)


	def add_column(self):
		self.Start += self.Resolution
		self.End += self.Resolution

		if self.Matrix is None:
			return

		column = np.zeros([len(self.RowMap), 1])
		self.Matrix = np.hstack((self.Matrix, column))
		self.Matrix = np.delete(self.Matrix, 0, axis=1)

	
	def add_row(self, row_name):
		rowcounter = len(self.RowMap)
		self.RowMap[row_name] = rowcounter
		self.RevRowMap[rowcounter] = row_name

		#and to warming up
		row = np.zeros([1, self.TimeWindow.Columns])
		
		if self.Matrix is None:
			self.Matrix = row
		else:
			self.Matrix = np.vstack((self.Matrix, row))

	def get_row(self, row_name):
		return self.RowMap.get(row_name)


	def get_column(self, event_timestamp):

		if event_timestamp <= self.End:
			self.Counters.add('events.late', 1)
			return None

		if event_timestamp > self.Start:
			self.Counters.add('events.early', 1)
			return None

		column_idx = int((event_timestamp - self.End - 1) // self.Resolution)

		assert(column_idx >= 0)
		assert(column_idx < self.Columns)
		
		return column_idx


	def advance(self, target_ts):
		'''
		Advance time window (add columns) so it covers target timestamp (target_ts)
		Also, if target_ts is in top 75% of the last existing column, add a new column too.

		------------------|-----------
		target_ts  ^ >>>  |
		                  ^ 
		                  Start

		'''
		while True:
			dt = (self.Start - target_ts) / self.Resolution
			if dt > 0.25: break
			self.add_column()
			L.warn("Time window was shifted")


	def get_matrix(self):
		return self.Matrix


###

class TimeWindowAnalyzer(Analyzer):
	'''
	This is the analyzer for events with a temporal dimension (aka timestamp).
	Configurable sliding window records events withing specified windows and implements functions to find the exact time slot.
	Timer periodically shifts the window by time window resolution, dropping previous events.
	'''

	ConfigDefaults = {
		'warm_up_count': 2, # at least this amount of events in the matrix should be to analyze 
		'columns': 15,
		'resolution': 60, # Resolution (aka column width) in seconds
	}

	def __init__(self, app, pipeline, start_time=None, clock_driven=True, time_window=None, id=None, config=None):
		super().__init__(app, pipeline, id, config)
		
		if time_window is not None:
			self.TimeWindow = time_window
		else:
			self.TimeWindow = TimeWindow(
				app,
				pipeline,
				int(self.Config['resolution']),
				int(self.Config['columns']),
				start_time
			)


		# to warm up
		self.WarmingUpCount = int(self.Config['warm_up_count'])
		self.WarmingUpRows = []

		if clock_driven:
			self.Timer = asab.Timer(app, self._on_tick, autorestart=True)
			self.Timer.start(self.Resolution / 4) # 1/4 of the sampling
		else:
			self.Timer = None


	def get_column(self, event_timestamp):
		return self.TimeWindow.get_column(event_timestamp)


	def get_row(self, row_name):
		return self.TimeWindow.get_row(row_name)


	#Adding new row to a window
	def add_row(self, row_name):
		self.TimeWindow.add_row(row_name)
		#and to warming up
		self.WarmingUpRows.append(0)


	def advance(self, target_ts):
		self.TimeWindow.advance(target_ts)


	async def _on_tick(self):

		target_ts = time.time()
		self.advance(target_ts)
#		if not self.WarmingUp:
#			await self.analyze()
