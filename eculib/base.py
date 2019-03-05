import os, sys, platform
from pylibftdi import Device
from ctypes import *
import time

class KlineAdapter(Device):

	def __init__(self, device_id, baudrate=10400):
		super(KlineAdapter, self).__init__(device_id, auto_detach=(platform.system()!="Windows"))
		self.baudrate = baudrate
		self.ftdi_fn.ftdi_usb_reset()
		self.ftdi_fn.ftdi_set_line_property(8, 1, 0)
		self.ftdi_fn.ftdi_usb_purge_buffers()

	def kline(self):
		self.ftdi_fn.ftdi_set_bitmode(1, 0x00)
		self._write(b'\x00')
		time.sleep(.002)
		ret = (self._read(1) == b'\x00')
		self.ftdi_fn.ftdi_set_bitmode(1, 0x00)
		self.ftdi_fn.ftdi_set_bitmode(0, 0x00)
		return ret

class ECU(object):

	def __init__(self, klineadapter):
		self.dev = klineadapter
