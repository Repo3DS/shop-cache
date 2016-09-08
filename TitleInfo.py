import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES
from PIL import Image
from IconManager import IconManager
from datetime import datetime, timezone
import sys, logging, struct, hashlib, math, unicodedata
import common


class TitleInfo:
				
	def __init__(self, id, uid = None):
		self.id = id.upper()
		self.uid = uid
		self.name = None
		self.name_normalized = None
		self.regions = 0
		self.icon_index = -1
		self.country_code = None
		self.seed = None
		self.size = None
		self.genres = []
		self.languages = []
		self.features = []
		self.vote_score = None
		self.vote_count = 0
		self.release_date = None
		self.product_code = None
		self.platform = None
		self.publisher = None

		self.icon = None
		self.logger = logging.getLogger()
		if not self.uid:
			self.uid = TitleInfo.get_id_pairs([self.id])[0]
		self.process_icon_data()
		self.fetch_data()
		if self.icon:
			self.icon_index = common.icon_manager.add_image(self.icon)


	def __repr__(self):
		return "{} {} {} {}".format(
			self.id, self.regions, self.country_code, self.name)


	def to_array(self):
		return [self.name, self.name_normalized, self.uid, self.regions,
		        self.country_code, self.size, self.icon_index, self.seed, self.genres,
		        self.languages, self.features, self.vote_score, self.vote_count,
		        self.release_date, self.product_code, self.platform, self.publisher]


	@staticmethod
	def normalize_text(text):
		text = text.translate({ord(i):' ' for i in u"®™"})
		nfkd_form = unicodedata.normalize('NFKD', text)
		return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


	@staticmethod
	def get_id_pairs(id_list, get_content_id = True):
		ret = [None] * len(id_list)
		from_key = 'title_id' if get_content_id else 'ns_uid'
		to_key = 'title_id' if not get_content_id else 'ns_uid'
		# URI length is limited, so need to break up large requests
		limit = 40
		if len(id_list) > limit:
			ret = []
			ret += TitleInfo.get_id_pairs(id_list[:limit], get_content_id)
			ret += TitleInfo.get_id_pairs(id_list[limit:], get_content_id)
		else:
			try:
				shop_request = urllib.request.Request(common.ninja_url + "titles/id_pair?{}[]=".format(from_key) + ','.join(id_list))
				shop_request.get_method = lambda: 'GET'
				response = urllib.request.urlopen(shop_request, context=common.ctr_context)
				xml = ET.fromstring(response.read().decode('UTF-8', 'replace'))
				for el in xml.findall('*/title_id_pair'):
					index = id_list.index(el.find(from_key).text)
					ret[index] = el.find(to_key).text
			except urllib.error.URLError as e:
				self.logger.error(e)
		return ret;


	def try_regions(self, region_list, try_all):
		title_response = None
		for code in region_list:
			try:
				if self.country_code and (code in common.region_euro_array) and (self.regions & common.region_map['EU']):
					continue
				title_request = urllib.request.Request(common.samurai_url + code + '/title/' + self.uid + '/?shop_id=1')
				title_response = urllib.request.urlopen(title_request, context=common.ctr_context)
				if not self.country_code:
					self.country_code = code
			except urllib.error.URLError as e:
				pass
			else:
				if code in common.region_euro_array:
					self.regions |= common.region_map['EU']
				elif code in common.region_map:
					self.regions |= common.region_map[code]
				if not try_all:
					break
		return title_response


	def fetch_data(self):
		self.genres = []
		self.languages = []
		self.features = []
		title_response = None

		if self.regions:
			if self.regions == common.region_map['US']:
				self.country_code = 'US'
				self.name = None # Use the title provided by samurai instead of icon server
			elif self.regions == common.region_map['JP']:
				self.country_code = 'JP'
			elif self.regions & common.region_map['EU']:
				if not self.regions & common.region_map['US']:
					title_response = self.try_regions(common.region_euro_array, False)
				else:
					# self.country_code = 'GB'
					title_response = self.try_regions(["GB","JP"], False)
				self.name = None
			elif self.regions & common.region_map['JP']:
				self.country_code = 'JP'
			else:
				self.logger.error("Region value {} for {}?".format(self.regions, self.id))
				return

			if self.country_code and not title_response:
				try:
					title_request = urllib.request.Request(common.samurai_url + self.country_code + '/title/' + self.uid + '/?shop_id=1')
					title_response = urllib.request.urlopen(title_request, context=common.ctr_context)
				except urllib.error.HTTPError:
					print(common.samurai_url + self.country_code + '/title/' + self.uid + '/?shop_id=1')
		else:
			# If all else fails, try all regions to see which the title is from
			self.regions = 0
			title_response = self.try_regions(common.region_array, True)

		if not self.regions or not title_response:
			raise ValueError("No region or country code for {}".format(self.id))

		ec_response = urllib.request.urlopen(common.ninja_url + self.country_code + '/title/' + self.uid + '/ec_info', context=common.ctr_context)	
		xml = ET.fromstring(title_response.read().decode('UTF-8', 'replace'))
		self.product_code = xml.find("*/product_code").text
		if not self.name:
			self.name = xml.find("*/name").text.replace('\n', ' ').strip()
			self.name_normalized = TitleInfo.normalize_text(self.name)

		# Fetch icon if it wasn't already (for DSiWare games atm)
		if not self.icon:
			try:
				icon_url = xml.find("*/icon_url").text
				res = urllib.request.urlopen(icon_url, context=common.ctr_context)
				self.icon = Image.open(res)
			except:
				self.logger.warn("No icon for title {} {}".format(self.id, self.name))

		# Get platform and publisher
		self.platform = int(xml.find("*/platform").attrib['id'])
		self.publisher = int(xml.find("*/publisher").attrib['id'])

		# Get genres
		genres = xml.find("*/genres")
		if genres:
			for genre in list(genres):
				self.genres.append(int(genre.attrib['id']))

		# Get features
		features = xml.findall(".//feature/id")
		if features:
			for feature in list(features):
				self.features.append(int(feature.text))

		# Get languages
		languages = xml.findall(".//language/iso_code")
		if languages:
			for language in list(languages):
				self.languages.append(language.text)

		# Get voting info
		try:
			self.vote_score = float(xml.find("*/star_rating_info/score").text)
			self.vote_count = int(xml.find("*/star_rating_info/votes").text)
		except:
			pass

		# Get released timestamp
		date_str = xml.find("*/release_date_on_eshop").text
		date = None
		try:
			date = datetime.strptime(date_str, '%Y-%m-%d')
		except:
			try:
				date = datetime.strptime(date_str, '%Y-%m')
			except:
				pass
		self.release_date = 0 if not date else int(date.replace(tzinfo=timezone.utc).timestamp())
		if self.release_date == 0:
			self.logger.warn("No release date for: {} {}".format(self.id, self.name))

		# Get size and seed
		xml = ET.fromstring(ec_response.read().decode('UTF-8', 'replace'))
		self.size = int(xml.find("*/content_size").text)
		try:
			self.seed = xml.find(".//external_seed").text
		except:
			self.seed = ''


	# On success, defines: name, regions, icon_index
	def process_icon_data(self):
		iv = b'a46987ae47d82bb4fa8abc0450285fa4'
		keys = [b'4ab9a40e146975a84bb1b4f3ecefc47b', b'90a0bb1e0e864ae87d13a6a03d28c9b8', b'ffbb57c14e98ec6975b384fcf40786b5', b'80923799b41f36a6a75fb8b48c95f66f']
		languages = ['JP','EN','FR','DE','IT','ES','TW','KO','NL','PT','RU']
		
		url = "https://idbe-ctr.cdn.nintendo.net/icondata/10/{}.idbe".format(self.id)
		try:
			res = urllib.request.urlopen(url, context=common.ctr_context)
		except:
			# Only warn if it isn't a DSiWare game, those aren't expected to be on icon server
			if self.id[:8] != '00048004':
				self.logger.warn("Failed to fetch icon data for title {}".format(self.id))
			return

		header = res.read(2)
		decryptor = AES.new(unhexlify(keys[header[1]]), AES.MODE_CBC, unhexlify(iv))
		data = decryptor.decrypt(res.read())

		# Get English title
		lang_offset = languages.index('EN') * 0x200 + 0x50
		title = data[lang_offset+0x80:lang_offset+0x180].decode('UTF-16', 'replace')
		self.name = title.strip('\x00').replace('\n', ' ')
		self.name_normalized = TitleInfo.normalize_text(self.name)

		# Get region value
		self.regions = struct.unpack("<L", data[0x30:0x34])[0]
		
		# Get icon data (uncompressed 48x48 RGB565) and make md5 hash to detect duplicates
		icon_data = data[0x2050+0x480:]

		# Convert RGB565 to RGB888
		w = h = 48
		tiled_icon = Image.frombuffer("RGB", (w, h), icon_data, "raw", "BGR;16")
		# Untile the image
		tile_order = [0,1,8,9,2,3,10,11,16,17,24,25,18,19,26,27,4,5,12,13,6,7,14,15,20,21,28,29,22,23,30,31,32,33,40,41,34,35,42,43,48,49,56,57,50,51,58,59,36,37,44,45,38,39,46,47,52,53,60,61,54,55,62,63]
		self.icon = Image.new("RGB", (w, h))
		pos = 0
		for y in range(0, h, 8):
			for x in range(0, w, 8):
				for k in range(8 * 8):
					xoff = tile_order[k] % 8
					yoff = int((tile_order[k] - xoff) / 8)

					posx = pos % w
					posy = math.floor(pos / w)
					pos += 1

					pixel = tiled_icon.getpixel((posx, posy))
					self.icon.putpixel((x + xoff, y + yoff), pixel)
