import os, sys, platform
from pylibftdi import Device
from pydispatch import dispatcher

class KlineAdapter(Device):

	def __init__(self, device_id, baudrate=10400):
		super(KlineAdapter, self).__init__(device_id, auto_detach=(platform.system()!="Windows"))
		self.baudrate = baudrate
		self.ftdi_fn.ftdi_usb_reset()
		self.ftdi_fn.ftdi_set_line_property(8, 1, 0)
		self.ftdi_fn.ftdi_usb_purge_buffers()

	def kline(self):
		self.flush()
		self._write(b"\xff")
		return self._read(1) == b"\xff"

class ECU(object):
