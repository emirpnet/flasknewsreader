# flasknewsreader.py
# Version: <see below>
# Author : Jochen Peters


from flask import Flask, render_template, request, redirect
from datetime import datetime
from operator import itemgetter
from shutil import copyfile
import json
from lib.newsfeed2json import load_feedlist_from_json, save_feedlist_to_json, is_valid_url, get_newsfeed_url, parse_news, print_news


# Parameters and settings
VERSION_INFO = {
	'version_number': '0.4',
	'version_date': '2020-04-05'
}
MAX_NUM_FEEDS = 50
FEEDLIST_FILENAME = 'feeds.json'
APPSETTINGS_FILENAME = 'settings.json'
APPSETTINGS_DEFAULT = {
	'remote_access': False,
	'auto_update': False,
}
appsettings = {}

# Globals
app = Flask(__name__)
feeds = None


# General functions

def main():
	global app, appsettings, feeds

	# Initialize
	load_appsettings()
	feeds = load_feedlist_from_json(FEEDLIST_FILENAME)
	reset_all_feed_status()

	# start server
	if appsettings['remote_access']:
		app.run(host='0.0.0.0', port=8080, debug=False) # disable SSL
		#app.run(host='0.0.0.0', port=8080, debug=False, ssl_context=('cert.pem', 'key.pem'))
	else:
		app.run(host='127.0.0.1', port=8080, debug=False)
	

def reset_all_feed_status():
	global feeds
	for f in feeds:
		f['fetched'] = False


def load_appsettings():
	global appsettings, APPSETTINGS_FILENAME, APPSETTINGS_DEFAULT
	try:
		with open(APPSETTINGS_FILENAME, mode='r') as f:
			appsettings = json.load(f)
	except:
		app.logger.info(APPSETTINGS_FILENAME + "not found, restoring default settings.")
		appsettings = APPSETTINGS_DEFAULT
		save_appsettings()


def save_appsettings():
	global appsettings, APPSETTINGS_FILENAME
	try:
		with open(APPSETTINGS_FILENAME, mode='w') as f:
			json.dump(appsettings, f)
		app.logger.info("Settings saved to " + APPSETTINGS_FILENAME)
	except:
		app.logger.error("Settings could not be written to " + APPSETTINGS_FILENAME)


def save_feedlist():
	global feeds, FEEDLIST_FILENAME

	# backup existing feedlist file
	try:
		copyfile(FEEDLIST_FILENAME, FEEDLIST_FILENAME+'~')
	except:
		app.logger.error("Could not create backup of " + FEEDLIST_FILENAME)
		
	# save current feedlist
	try:
		save_feedlist_to_json(feeds, FEEDLIST_FILENAME)
		app.logger.info("Feedlist saved to " + FEEDLIST_FILENAME)
	except:
		app.logger.error("Feedlist could not be written to " + FEEDLIST_FILENAME)


def fetch_news(feed):
	try:
		xmlstring = get_newsfeed_url(feed["url"])
		news = parse_news(xmlstring, remove_tags=True)
	except:
		news = None

	feed["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	feed["news"] = news


def sanitize_feed_idx(idx):
	global feeds

	try:
		feed_idx = int(idx)
	except:
		return None

	if feed_idx < 0 or feed_idx >= len(feeds):
		return None

	return feed_idx


# Routes

@app.route('/')
def home():
	return redirect('/news')


@app.route('/news')
def news():
	global appsettings, feeds

	feed_idx = sanitize_feed_idx(request.args.get('feed'))
	if feed_idx is None:
		return redirect('/news?feed=0')

	if not feeds[feed_idx]['fetched'] or appsettings['auto_update']:
		fetch_news(feeds[feed_idx])
		feeds[feed_idx]['fetched'] = True

	return render_template('news.html', feeds=feeds, feed_idx=feed_idx)


@app.route('/reload')
def reload():
	feed_idx = sanitize_feed_idx(request.args.get('feed'))
	if feed_idx is None:
		return redirect('/news?feed=0')
	fetch_news(feeds[feed_idx])
	return redirect('/news?feed=' + str(feed_idx))


@app.route('/settings', methods=['POST','GET'])
def settings():
	global appsettings, VERSION_INFO, feeds
	
	if request.method == 'GET':
		return render_template('settings.html', feeds=feeds, **appsettings, **VERSION_INFO)
	
	elif request.method == 'POST':
		
		if request.form.get('action') == 'save_settings':
			# remote_access
			if request.form.get('remote_access'):
				appsettings['remote_access'] = True
			else:
				appsettings['remote_access'] = False

			# auto_update
			if request.form.get('auto_update'):
				appsettings['auto_update'] = True
			else:
				appsettings['auto_update'] = False

			# save and return
			save_appsettings()
			return redirect('/settings')

		elif request.form.get('action') == 'save_feedlist':

			# grab form information
			feeds_position = []
			feeds_url = []
			feeds_active = []
			for i, f in enumerate(feeds):
				feeds_position.append(int(request.form.get('position_' + str(i))))

				new_url = request.form.get('url_' + str(i))
				if is_valid_url(new_url):
					feeds_url.append(new_url)
				else:
					feeds_url.append(feeds[i]['url'])

				if request.form.get('active_' + str(i)):
					feeds_active.append(True)
				else:
					feeds_active.append(False)

			# update feeds
			for i, f in enumerate(feeds):
				f['url'] = feeds_url[i]
				f['active'] = feeds_active[i]

			# sort feeds according to position
			feeds = [x for _, x in sorted(zip(feeds_position, feeds), key=itemgetter(0))]

			# save and return
			save_feedlist()
			return redirect('/settings#newsfeeds')

		elif request.form.get('action') == 'add_feed':
			if len(feeds) < MAX_NUM_FEEDS:
				new_name = request.form.get('new_name')
				new_url = request.form.get('new_url')
				new_feed_active = request.form.get('new_feed_active')
				f = {
					'name': new_name,
					'url': new_url,
					'active': new_feed_active,
					'fetched': False,
				}
				feeds.append(f)
				app.logger.info('Feed \"' + f['name'] + '\" (' + f['url'] + ') added.')
			else:
				app.logger.warning('Maximum number of feeds reached, submit of new feed was ignored.')

			return redirect('/settings#add_feed')

		elif request.form.get('remove_feed'):
			feed_idx =  sanitize_feed_idx(request.form.get('remove_feed'))
			if feed_idx is None:
				return redirect('/settings#newsfeeds')

			f = feeds.pop(feed_idx)
			app.logger.info('Feed \"' + f['name'] + '\" (' + f['url'] + ') removed.')

			return redirect('/settings#newsfeeds')


# run main()
if __name__ == '__main__':
	main()

