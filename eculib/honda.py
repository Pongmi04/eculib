import time
import struct
from enum import Enum
from .base import ECU
from pydispatch import dispatcher

class ECUSTATE(Enum):
	UNDEFINED = -1
	OFF = 0
	READ = 1
	READING = 2
	OK = 3
	RECOVER_OLD = 4
	RECOVER_NEW = 5
	WRITE = 6
	WRITING = 7
	ERASING = 8
	INIT_WRITE = 9
	INIT_RECOVER = 10
	ERROR = 11
	UNKNOWN = 12

DTC = {
	"01-01": "MAP sensor circuit low voltage",
	"01-02": "MAP sensor circuit high voltage",
	"02-01": "MAP sensor performance problem",
	"07-01": "ECT sensor circuit low voltage",
	"07-02": "ECT sensor circuit high voltage",
	"08-01": "TP sensor circuit low voltage",
	"08-02": "TP sensor circuit high voltage",
	"09-01": "IAT sensor circuit low voltage",
	"09-02": "IAT sensor circuit high voltage",
	"11-01": "VS sensor no signal",
	"12-01": "No.1 primary injector circuit malfunction",
	"13-01": "No.2 primary injector circuit malfunction",
	"14-01": "No.3 primary injector circuit malfunction",
	"15-01": "No.4 primary injector circuit malfunction",
	"16-01": "No.1 secondary injector circuit malfunction",
	"17-01": "No.2 secondary injector circuit malfunction",
	"18-01": "CMP sensor no signal",
	"19-01": "CKP sensor no signal",
	"21-01": "0₂ sensor malfunction",
	"23-01": "0₂ sensor heater malfunction",
	"25-02": "Knock sensor circuit malfunction",
	"25-03": "Knock sensor circuit malfunction",
	"29-01": "IACV circuit malfunction",
	"33-02": "ECM EEPROM malfunction",
	"34-01": "ECV POT low voltage malfunction",
	"34-02": "ECV POT high voltage malfunction",
	"35-01": "EGCA malfunction",
	"48-01": "No.3 secondary injector circuit malfunction",
	"49-01": "No.4 secondary injector circuit malfunction",
	"51-01": "HESD linear solenoid malfunction",
	"54-01": "Bank angle sensor circuit low voltage",
	"54-02": "Bank angle sensor circuit high voltage",
	"56-01": "Knock sensor IC malfunction",
	"86-01": "Serial communication malfunction"
}

def format_read(location):
	tmp = struct.unpack(">4B",struct.pack(">I",location))
	return [tmp[1], tmp[3], tmp[2]]

def checksum8bitHonda(data):
	return ((sum(bytearray(data)) ^ 0xFF) + 1) & 0xFF

def checksum8bit(data):
	return 0xff - ((sum(bytearray(data))-1) >> 8)

def validate_checksums(byts, nbyts, cksum):
	ret = False
	fixed = False
	if cksum > 0 and cksum < nbyts:
		byts[cksum] = checksum8bitHonda(byts[:cksum]+byts[(cksum+1):])
		fixed = True
	ret = checksum8bitHonda(byts)==0
	return ret, fixed, byts

def do_validation(byts, nbyts, cksum=0):
	status = "good"
	ret, fixed, byts = validate_checksums(byts, nbyts, cksum)
	if not ret:
		status = "bad"
	elif fixed:
		status = "fixed"
	return ret, status, byts

def format_message(mtype, data):
	ml = len(mtype)
	dl = len(data)
	msgsize = 0x02 + ml + dl
	msg = mtype + [msgsize] + data
	msg += [checksum8bitHonda(msg)]
	assert(msg[ml] == len(msg))
	return msg, ml, dl

class HondaECU(ECU):

	def init(self):
		self.dev.ftdi_fn.ftdi_set_bitmode(1, 0x01)
		self.dev._write(b'\x00')
		time.sleep(.070)
		self.dev._write(b'\x01')
		self.dev.ftdi_fn.ftdi_set_bitmode(0, 0x00)
		self.dev.flush()
		time.sleep(.130)

	def send(self, buf, ml, timeout=.001):
		self.dev.flush()
		msg = "".join([chr(b) for b in buf]).encode("latin1")
		self.dev._write(msg)
		r = len(msg)
		timeout = .05 + timeout * r
		to = time.time()
		while r > 0:
			r -= len(self.dev._read(r))
			if time.time() - to > timeout: return None
		buf = bytearray()
		r = ml+1
		while r > 0:
			tmp = self.dev._read(r)
			r -= len(tmp)
			buf.extend(tmp)
			if time.time() - to > timeout: return None
		r = buf[-1]-ml-1
		to = time.time()
		while r > 0:
			tmp = self.dev._read(r)
			r -= len(tmp)
			buf.extend(tmp)
			if time.time() - to > timeout: return None
		return buf

	def send_command(self, mtype, data=[], retries=1, delay=0):
		msg, ml, dl = format_message(mtype, data)
		r = 0
		while r <= retries:
			dispatcher.send(signal="ecu.debug", sender=self, msg="%d > [%s]" % (r, ", ".join(["%02x" % m for m in msg])))
			resp = self.send(msg, ml)
			if resp:
				if checksum8bitHonda(resp[:-1]) == resp[-1]:
					dispatcher.send(signal="ecu.debug", sender=self, msg="%d < [%s]" % (r, ", ".join(["%02x" % r for r in resp])))
					rmtype = resp[:ml]
					valid = False
					if ml == 3:
						valid = (rmtype[:2] == bytearray(map(lambda x: x | 0x10, mtype[:2])))
					elif ml == 2:
						valid = ([b for b in rmtype]==mtype)
					elif ml == 1:
						valid = (rmtype == bytearray(map(lambda x: x & 0xf, mtype)))
					if valid:
						rml = resp[ml:(ml+1)]
						rdl = ord(rml) - 2 - len(rmtype)
						rdata = resp[(ml+1):-1]
						if delay > 0:
							time.sleep(delay)
						return (rmtype, rml, rdata, rdl)
					else:
						return None
			r += 1

	def ping(self):
		return self.send_command([0xfe],[0x72], retries=0) != None

	def diag(self):
		return self.send_command([0x72],[0x00, 0xf0]) != None

	def detect_ecu_state(self):
		if self.dev.kline():
			t0 = self.send_command([0x72], [0x71, 0x00], retries=0)
			if t0 is None:
				self.init()
				self.ping()
				t0 = self.send_command([0x72], [0x71, 0x00], retries=0)
			if t0 is not None:
				if bytes(t0[2][5:7]) != b"\x00\x00":
					return ECUSTATE.OK
			if self.send_command([0x7d], [0x01, 0x01, 0x00], retries=0):
				return ECUSTATE.RECOVER_OLD
			if self.send_command([0x7b], [0x00, 0x01, 0x01], retries=0):
				return ECUSTATE.RECOVER_NEW
			writestatus = self.send_command([0x7e], [0x01, 0x01, 0x00], retries=0)
			if writestatus is not None:
				if writestatus[2][1] == 0xf0:
					return ECUSTATE.ERROR
				return ECUSTATE.WRITE
			readinfo = self.send_command([0x82, 0x82, 0x00], [0x00, 0x00, 0x00, 0x08], retries=0)
			if not readinfo is None:
				return ECUSTATE.READ
			return ECUSTATE.UNKNOWN
		else:
			return ECUSTATE.OFF

	def probe_tables(self, tables=None):
		if not tables:
			tables = [0x10, 0x11, 0x17, 0x20, 0x21, 0x60, 0x61, 0x67, 0x70, 0x71, 0xd0, 0xd1]
		ret = {}
		for t in tables:
			info = self.send_command([0x72], [0x71, t])
			if info:
				if info[3] > 2:
					ret[t] = [info[3],info[2]]
			else:
				return {}
		return ret

	def do_init_recover(self):
		self.send_command([0x7b], [0x00, 0x01, 0x01], delay=.5)
		self.send_command([0x7b], [0x00, 0x01, 0x02], delay=.5)
		self.send_command([0x7b], [0x00, 0x01, 0x03], delay=.5)
		self.send_command([0x7b], [0x00, 0x02, 0x76, 0x03, 0x17], delay=.5)
		self.send_command([0x7b], [0x00, 0x03, 0x75, 0x05, 0x13], delay=.5)

	def do_init_write(self):
		self.send_command([0x7d], [0x01, 0x01, 0x01], delay=.5)
		self.send_command([0x7d], [0x01, 0x01, 0x02], delay=.5)
		self.send_command([0x7d], [0x01, 0x01, 0x03], delay=.5)
		self.send_command([0x7d], [0x01, 0x02, 0x50, 0x47, 0x4d], delay=.5)
		self.send_command([0x7d], [0x01, 0x03, 0x2d, 0x46, 0x49], delay=.5)

	def do_erase(self):
		self.send_command([0x7e], [0x01, 0x02], delay=.5)
		self.send_command([0x7e], [0x01, 0x03, 0x00, 0x00], delay=.5)
		self.send_command([0x7e], [0x01, 0x0b, 0x00, 0x00, 0x00, 0xff, 0xff, 0xff], delay=.5)
		self.send_command([0x7e], [0x01, 0x0e, 0x01, 0x90], delay=.5)
		self.send_command([0x7e], [0x01, 0x01, 0x01], delay=.5)
		self.send_command([0x7e], [0x01, 0x04, 0xff], delay=.5)

	def do_erase_wait(self):
		cont = 1
		while cont:
			info = self.send_command([0x7e], [0x01, 0x05])
			if info:
				if info[2][1] == 0x00:
					cont = 0
			else:
				cont = -1
		if cont == 0:
			into = self.send_command([0x7e], [0x01, 0x01, 0x00])

	def do_post_write(self):
		self.send_command([0x7e], [0x01, 0x09], delay=.5)
		self.send_command([0x7e], [0x01, 0x0a], delay=.5)
		self.send_command([0x7e], [0x01, 0x0c], delay=.5)
		info = self.send_command([0x7e], [0x01, 0x0d], delay=.5)
		if info: return (info[2][1] == 0x0f)

	def get_faults(self):
		faults = {'past':[], 'current':[]}
		for i in range(1,0x0c):
			info_current = self.send_command([0x72],[0x74, i])[2]
			for j in [3,5,7]:
				if info_current[j] != 0:
					faults['current'].append("%02d-%02d" % (info_current[j],info_current[j+1]))
			if info_current[2] == 0:
				break
		for i in range(1,0x0c):
			info_past = self.send_command([0x72],[0x73, i])[2]
			for j in [3,5,7]:
				if info_past[j] != 0:
					faults['past'].append("%02d-%02d" % (info_past[j],info_past[j+1]))
			if info_past[2] == 0:
				break
		return faults
