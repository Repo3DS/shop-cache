#!/usr/bin/env python3
import os, sys, json, getopt, logging
from binascii import hexlify
from TitleInfo import TitleInfo
from IconManager import IconManager
import common

# Dictionary of title keys
enc_title_keys = {}
with open('encTitleKeys.bin', 'rb') as f:
	n_entries = os.fstat(f.fileno()).st_size / 32
	f.seek(16, os.SEEK_SET)
	for i in range(int(n_entries)):
		f.seek(8, os.SEEK_CUR)
		title_id = f.read(8)
		title_key = f.read(16)
		enc_title_keys[hexlify(title_id).decode().upper()] = hexlify(title_key).decode()

# Dictionary to store scraped data to turn into json
json_data = {}


def filter_titles(titles):
	#             Game     | DSiWare
	tid_index = ['00040000','00048004']
	ret = []
	for title_id in titles:
		tid_high = title_id[:8]
		if tid_high in tid_index:
			ret.append(title_id)
	return ret


def scrape():
	global json_data
	titles = list(enc_title_keys.keys())
	titles = filter_titles(titles)

	uid_list = TitleInfo.get_id_pairs(titles)

	for i, uid in enumerate(uid_list):
		if not uid:
			print("Failed to get uid for title id: " + titles[i])
		else:
			try:
				title_data = TitleInfo(titles[i], uid)
				json_data[titles[i]] = title_data.to_array()
				print("Title {} out of {}: [{}] {}".format(i+1, len(uid_list), title_data.product_code, title_data.name))
			except ValueError as e:
				logging.warn(e)
				pass
			except KeyboardInterrupt:
				break

	common.icon_manager.save()
	with open('data.json', 'w') as f:
		json.dump(json_data, f, separators=(',', ':'))


def load_cache(input_dir):
	global json_data
	with open(os.path.join(input_dir, "data.json")) as f:
		json_data = json.load(f)

	max_icon_index = max(json_data, key=(lambda x: json_data[x][6]))
	icon_index = json_data[max_icon_index][6] + 1
	common.icon_manager = IconManager(icon_index, os.path.join(input_dir, "images"))

	for i in list(json_data.keys()):
		enc_title_keys.pop(i, None)


def show_usage_exit():
	print('gen_cache.py [-i <input directory>]')
	sys.exit(2)


def main(argv):
	input_dir = None
	logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
	try:
		opts, args = getopt.getopt(argv, "hi:")
	except getopt.GetoptError:
		show_usage_exit()
	for opt, arg in opts:
		if opt == '-h':
			show_usage_exit()
		elif opt in ("-i", "--input"):
			input_dir = arg
	if input_dir:
		load_cache(input_dir)
		scrape()
	else:
		scrape()


if __name__ == '__main__':
	main(sys.argv[1:])
