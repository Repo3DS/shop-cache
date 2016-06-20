from IconManager import IconManager
import ssl

# Client certs
ctr_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
ctr_context.load_cert_chain('ctr-common-1.crt', keyfile='ctr-common-1.key')
# Map of region bitflags
region_map = {'JP':1<<0, 'US':1<<1, 'EU':1<<2, 'AU':1<<3, 'CN':1<<4, 'KO':1<<5, 'TW':1<<6}

samurai_url = 'https://samurai.ctr.shop.nintendo.net/samurai/ws/'
ninja_url = 'https://ninja.ctr.shop.nintendo.net/ninja/ws/'

region_array = ['JP', 'US', 'GB', 'DE', 'FR', 'ES', 'NL', 'IT'] # 'HK', 'TW', 'KR']
region_euro_array = ['GB', 'DE', 'FR', 'ES', 'NL', 'IT']

icon_manager = IconManager()
