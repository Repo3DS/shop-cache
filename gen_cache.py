#!/usr/bin/env python3
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from binascii import hexlify, unhexlify
from PIL import Image
import os, sys, ssl, json, unicodedata, getopt


# Client certs
ctr_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
ctr_context.load_cert_chain('ctr-common-1.crt', keyfile='ctr-common-1.key')
# XML from 3dsdb
# releases_xml = ET.parse('3dsreleases.xml')
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
json_data = {}


def get_id_pairs(ids, get_content_id = True):
	ret = [None] * len(ids)
	from_key = 'title_id' if get_content_id else 'ns_uid'
	to_key = 'title_id' if not get_content_id else 'ns_uid'
	
	ninja_url = 'https://ninja.ctr.shop.nintendo.net/ninja/ws/titles/id_pair'

	# URI length is limited, so need to break up large requests
	limit = 40
	if len(ids) > limit:
		ret = []
		ret += get_id_pairs(ids[:limit], get_content_id)
		ret += get_id_pairs(ids[limit:], get_content_id)
	else:
		try:
			# key = 'title_id' if get_content_id else 'ns_uid'
			shop_request = urllib.request.Request(ninja_url + "?{}[]=".format(from_key) + ','.join(ids))
			shop_request.get_method = lambda: 'GET'
			response = urllib.request.urlopen(shop_request, context=ctr_context)
			xml = ET.fromstring(response.read().decode('UTF-8', 'replace'))
			for el in xml.findall('*/title_id_pair'):
				index = ids.index(el.find(from_key).text)
				ret[index] = el.find(to_key).text
		except urllib.error.URLError as e:
			print(e)

	return ret;


def normalize_text(input):
	input = input.translate({ord(i):' ' for i in u"®™"})
	nfkd_form = unicodedata.normalize('NFKD', input)
	return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


def get_title_data(id, uid):
	# Returns array:
	# 0 - Title name
	# 1 - Title normalized for indexing
	# 2 - Content UID (as provided by arg)
	# 3 - Region list
	# 4 - Country code
	# 5 - Size
	# 6 - Icon url (to later be replaced by icon index)
	# 7 - Title version

	# samurai handles metadata actions, including getting a title's info
	# URL regions are by country instead of geographical regions... for some reason
	samurai_url = 'https://samurai.ctr.shop.nintendo.net/samurai/ws/'
	ec_url = 'https://ninja.ctr.shop.nintendo.net/ninja/ws/'
	region_array = ['JP', 'US', 'GB', 'DE', 'FR', 'ES', 'NL', 'IT'] # 'HK', 'TW', 'KR']
	eur_array = ['GB', 'DE', 'FR', 'ES', 'NL', 'IT']
	regions = []
	country_code = ''

	# try loop to figure out which region the title is from; there is no easy way to do this other than try them all
	for code in region_array:
		try:
			if code in eur_array and 'EU' in regions:
				continue
			title_request = urllib.request.Request(samurai_url + code + '/title/' + uid)
			titleResponse = urllib.request.urlopen(title_request, context=ctr_context)
			country_code = code
		except urllib.error.URLError as e:
			pass
		else:
			if code in eur_array:
				regions.append('EU')
			else:
				regions.append(code)
	if not regions:
		print("No region for {}?".format(id))
		return

	ec_response = urllib.request.urlopen(ec_url + country_code + '/title/' + uid + '/ec_info', context=ctr_context)	
	xml = ET.fromstring(titleResponse.read().decode('UTF-8', 'replace'))
	title_name = xml.find("*/name").text.replace('\n', ' ')
	try:
		icon_url = xml.find("*/icon_url").text.replace('\n', ' ')
	except:
		icon_url = -1

	xml = ET.fromstring(ec_response.read().decode('UTF-8', 'replace'))
	title_size = int(xml.find("*/content_size").text)
	title_version = int(xml.find("*/title_version").text)

	title_normalized = normalize_text(title_name)

	return [title_name, title_normalized, uid, regions, country_code, title_size, icon_url, title_version]


# Fit 441 48x48 icons per 1024x1024 image
img_array = []
img_index = -1
icon_index = 0

def compile_texture(data):
	global img_index
	global icon_index

	if not os.path.exists("images"):
		os.makedirs("images")

	for title, title_data in data.items():
		if not title_data:
			print("No data? ", title)
		else:
			icon_url = title_data[6]
			if isinstance(icon_url, str):
				res = urllib.request.urlopen(icon_url, context=ctr_context)
				img = Image.open(res)
				if img.size != (48, 48):
					img = img.resize((48, 48), 1)

				if icon_index > len(img_array) * 441 - 1:
					img_array.append(Image.new("RGB", (1024, 1024), "white"))
					img_index += 1

				x = int((icon_index % 441) / 21) * 48
				y = ((icon_index % 441) % 21) * 48

				img_array[img_index].paste(img, (x, y))
				data[title][6] = icon_index
				icon_index += 1

	for i, img in enumerate(img_array):
		img.save("images/icons{}.png".format(i), optimize=True)
		img.save("images/icons{}.jpg".format(i), quality=85, optimize=True)


def filter_titles(titles):
	ret = []
	tid_index = ['00040000']
	for title_id in titles:
		tid_high = title_id[:8]
		if tid_high in tid_index:
			ret.append(title_id)
	return ret


def scrape():
	global json_data

	titles = list(enc_title_keys.keys())
	titles = filter_titles(titles)

	uid_list = get_id_pairs(titles)

	for i, uid in enumerate(uid_list):
		if not uid:
			print("Failed to get uid for title id: " + titles[i])
		else:
			title_data = get_title_data(titles[i], uid)
			if title_data:
				json_data[titles[i]] = title_data
				print("Title {} out of {}: {} ({})".format(i+1, len(uid_list), title_data[0], title_data[1]))

	with open('data.json', 'w') as f:
		json.dump(json_data, f, separators=(',', ':'))


def texture_from_json():
	with open("data.json") as f:
		json_data = json.load(f)
	compile_texture(json_data)
	with open('data.json', 'w') as f:
		json.dump(json_data, f, separators=(',', ':'))


def load_cache(input_dir):
	global icon_index
	global img_index
	global json_data

	with open(os.path.join(input_dir, "data.json")) as f:
		json_data = json.load(f)
	max_icon_index = max(json_data, key=(lambda x: json_data[x][6]))
	icon_index = json_data[max_icon_index][6] + 1
	img_index = int(icon_index / 441)
	for i in range(img_index + 1):
		img_array.append(Image.open(os.path.join(input_dir, "images/icons{}.png".format(i))))
	for i in list(json_data.keys()):
		enc_title_keys.pop(i, None)

	titles = list(enc_title_keys.keys())
	titles = filter_titles(titles)

	scrape()
	texture_from_json()


def show_usage_exit():
	print('gen_cache.py -i <input directory>')
	sys.exit(2)


def main(argv):
	input_dir = None
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
	else:
		scrape()
		texture_from_json()


if __name__ == '__main__':
	main(sys.argv[1:])
