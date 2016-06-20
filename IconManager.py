from PIL import Image
import os, hashlib


class IconManager:
				
	def __init__(self, icon_index = 0, image_dir = "images"):
		self.icon_index = icon_index
		self.image_index = -1 if not icon_index else int(icon_index / 441)
		self.image_array = []
		self.icon_hashes = []
		self.image_dir = image_dir
		# Load images if icon index is non-zero
		for i in range(self.image_index + 1):
			image = Image.open(os.path.join(self.image_dir, "icons{}.png".format(i)))
			self.image_array.append(image)
		# Get icon hashes from images
		for i in range(self.icon_index):
			x = int((i % 441) / 21) * 48
			y = ((i % 441) % 21) * 48
			image = self.image_array[int(i / 441)]
			subimage = image.crop((x, y, x + 48, y + 48))
			md5 = hashlib.md5(subimage.tobytes()).hexdigest()
			self.icon_hashes.append(md5)

	def __repr__(self):
		return "IconManager[{} icons]".format(self.icon_index)

	# Fits 441 48x48 icons per 1024x1024 image
	# Returns index of added icon
	def add_image(self, image):
		if image.size != (48, 48):
			image = image.resize((48, 48), 1)

		# Check stored hashes to prevent dulpicates
		md5 = hashlib.md5(image.tobytes()).hexdigest()
		if md5 in self.icon_hashes:
			return self.icon_hashes.index(md5)
		self.icon_hashes.append(md5)

		if self.icon_index > len(self.image_array) * 441 - 1:
			self.image_array.append(Image.new("RGB", (1024, 1024), "white"))
			self.image_index += 1

		x = int((self.icon_index % 441) / 21) * 48
		y = ((self.icon_index % 441) % 21) * 48
		self.image_array[self.image_index].paste(image, (x, y))

		self.icon_index += 1
		return self.icon_index - 1

	def save(self, path = "images"):
		if not os.path.exists(path):
			os.makedirs(path)
		for i, img in enumerate(self.image_array):
			img.save(os.path.join(path, "icons{}.png".format(i)), optimize=True)
			img.save(os.path.join(path, "icons{}.jpg".format(i)), quality=85, optimize=True)
