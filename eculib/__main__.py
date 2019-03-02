import sys
import argparse
from pylibftdi import Driver
from eculib import KlineAdapter

def GetFtdiDevices():
	dev_list = {}
	for device in Driver().list_devices():
		dev_info = map(lambda x: x.decode('latin1'), device)
		vendor, product, serial = dev_info
		dev_list[serial] = (vendor, product)
	return dev_list

def Main():

	devices = GetFtdiDevices()
	default_device = None
	if len(devices) > 0:
		default_device = list(devices.keys())[0]

	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('-d','--device', help="ftdi device serial number", default=default_device)
	subparsers = parser.add_subparsers(metavar='mode',dest='mode')

	parser_kline = subparsers.add_parser('kline', help='test kline')

	db_grp = parser.add_argument_group('debugging options')
	db_grp.add_argument('--list-devices', action='store_true', help="list ftdi devices")
	args = parser.parse_args()

	if args.list_devices:
		print("FTDI Devices:")
		for k,v in devices.items():
			print(" * %s: %s %s" % (k, v[0], v[1]))
		return
	elif args.device is None:
		print("No FTDI device connected")
		return

	dev = KlineAdapter(args.device)

	if args.mode is None:
		parser.print_help()

	elif args.mode == "kline":
		try:
			oldstate = None
			while True:
				newstate = dev.kline()
				if oldstate != newstate:
					sys.stdout.write("\rK-line state: %d" % newstate)
					sys.stdout.flush()
					oldstate = newstate
		except KeyboardInterrupt:
			sys.stdout.write("\n")
			sys.stdout.flush()

if __name__ == '__main__':
	Main()
