# flasknewsreader.py
# Version: <see below>
# Author : Jochen Peters


from flask import Flask, render_template, request, redirect
from datetime import datetime
from operator import itemgetter
from shutil import copyfile
import json
import os
from lib.newsfeed2json import load_newsfeed, parse_news, create_feed_id, is_valid_url


# Parameters and settings
VERSION_INFO = {
	'version_number': '0.5',
	'version_date': '2020-04-10'
}
MAX_NUM_FEEDS = 50
FEEDLIST_FILENAME = 'feeds.json'
NEWS_FILENAME = 'news.json'
APPSETTINGS_FILENAME = 'settings.json'
APPSETTINGS_DEFAULT = {
	'remote_access': False,
	'auto_update': False,
}

# Globals
app = Flask(__name__)
app.appsettings = {}
app.feeds = {}
app.news = {}


# General functions

def main():
	# Initialize
	load_app_status()

	# start server
	if app.appsettings['remote_access']:
		app.run(host='0.0.0.0', port=8080, debug=False) # disable SSL
		#app.run(host='0.0.0.0', port=8080, debug=False, ssl_context=('cert.pem', 'key.pem'))
	else:
		app.run(host='127.0.0.1', port=8080, debug=False)


def load_app_status():
	global APPSETTINGS_FILENAME, FEEDLIST_FILENAME, NEWS_FILENAME
	this_folder = os.path.dirname(os.path.abspath(__file__))

	# load app settings
	APPSETTINGS_FILENAME= os.path.join(this_folder, APPSETTINGS_FILENAME)
	try:
		app.appsettings = load_from_json(APPSETTINGS_FILENAME)
	except:
		app.logger.info('Error loading application settings from ' + APPSETTINGS_FILENAME + ', restoring default settings.')
		app.appsettings = APPSETTINGS_DEFAULT
		save_to_json(app.appsettings, APPSETTINGS_FILENAME, False)

	# load feedlist
	FEEDLIST_FILENAME = os.path.join(this_folder, FEEDLIST_FILENAME)
	try:
		app.feeds = load_from_json(FEEDLIST_FILENAME)
	except:
		app.logger.info('Error loading feedlist from ' + APPSETTINGS_FILENAME)
		app.feeds = {}

	# load news items
	NEWS_FILENAME = os.path.join(this_folder, NEWS_FILENAME)
	try:
		app.news = load_from_json(NEWS_FILENAME)
	except:
		app.logger.info('Error loading feedlist from ' + APPSETTINGS_FILENAME)
		app.news = {}


def save_app_status():
	save_to_json(app.appsettings, APPSETTINGS_FILENAME, False)
	save_to_json(app.feeds, FEEDLIST_FILENAME)
	save_to_json(app.news, NEWS_FILENAME, False)


def load_from_json(filename):
	with open(filename, mode='r') as f:
		dictionary = json.load(f)
	return dictionary


def save_to_json(dictionary, filename, create_backup=True):
	# backup existing file
	if create_backup:
		try:
			copyfile(filename, filename+'~')
		except:
			app.logger.error('Could not create backup of ' + filename)

	# write json-file
	try:
		with open(filename, mode='w') as f:
			json.dump(dictionary, f, indent=0, separators=(',', ': '))
			app.logger.info(filename + ' written.')
	except:
		app.logger.error('Error writing ' + filename)


def fetch_news(feed):
	try:
		xmlstring = load_newsfeed(feed['url'])
		news = parse_news(xmlstring, remove_tags=True)
	except:
		news = None

	feed['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	if 'fid' not in feed:
		feed['fid'] = create_feed_id(feed)
	app.news[feed['fid']] = news


def clear_all_newsitems():
	for f in app.feeds:
		f.pop('updated', None)
	app.news = {}


def sanitize_feed_idx(feeds, idx):
	if feeds is None:
		return None

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
	load_app_status()
	feed_idx = sanitize_feed_idx(app.feeds, request.args.get('feed'))
	if feed_idx is None:
		return redirect('/news?feed=0')

	if app.appsettings['auto_update']: # or 'updated' not in app.feeds[feed_idx]:
		fetch_news(app.feeds[feed_idx])

	# save and return
	save_app_status()
	return render_template('news.html', feeds=app.feeds, feed_idx=feed_idx, news=app.news)


@app.route('/reload')
def reload():
	load_app_status()
	feed_idx = sanitize_feed_idx(app.feeds, request.args.get('feed'))
	if feed_idx is None:
		return redirect('/news?feed=0')
	fetch_news(app.feeds[feed_idx])
	# save and return
	save_app_status()
	return redirect('/news?feed=' + str(feed_idx))


@app.route('/settings', methods=['POST','GET'])
def settings():
	load_app_status()

	if request.method == 'GET':
		return render_template('settings.html', feeds=app.feeds, **app.appsettings, **VERSION_INFO)

	elif request.method == 'POST':

		if request.form.get('action') == 'save_settings':
			# remote_access
			if request.form.get('remote_access'):
				app.appsettings['remote_access'] = True
			else:
				app.appsettings['remote_access'] = False

			# auto_update
			if request.form.get('auto_update'):
				app.appsettings['auto_update'] = True
			else:
				app.appsettings['auto_update'] = False

			# save and return
			save_app_status()
			return redirect('/settings')

		elif request.form.get('action') == 'clear_all_news':
			clear_all_newsitems()
			save_app_status()
			return redirect('/settings')

		elif request.form.get('action') == 'save_feedlist':

			# grab form information
			feeds_position = []
			feeds_url = []
			feeds_active = []
			for i, f in enumerate(app.feeds):
				feeds_position.append(int(request.form.get('position_' + str(i))))

				new_url = request.form.get('url_' + str(i))
				if is_valid_url(new_url):
					feeds_url.append(new_url)
				else:
					feeds_url.append(app.feeds[i]['url'])

				if request.form.get('active_' + str(i)):
					feeds_active.append(True)
				else:
					feeds_active.append(False)

			# update feeds
			for i, f in enumerate(app.feeds):
				f['url'] = feeds_url[i]
				f['active'] = feeds_active[i]
				# now handle possible change of the fid (since it depends on the url):
				old_fid = f['fid']
				f['fid'] = create_feed_id(f)
				if old_fid in app.news:
					app.news[f['fid']] = app.news.pop(old_fid)

			# sort feeds according to position
			app.feeds = [x for _, x in sorted(zip(feeds_position, app.feeds), key=itemgetter(0))]

			# save and return
			save_app_status()
			return redirect('/settings#newsfeeds')

		elif request.form.get('action') == 'add_feed':
			if len(app.feeds) < MAX_NUM_FEEDS:
				new_name = request.form.get('new_name')
				new_url = request.form.get('new_url')
				new_feed_active = request.form.get('new_feed_active')
				f = {
					'name': new_name,
					'url': new_url,
					'active': new_feed_active,
				}
				f['fid'] = create_feed_id(f)
				app.feeds.append(f)
				app.logger.info('Feed ' + f['fid'] + ': \'' + f['name'] + '\' (' + f['url'] + ') added.')
			else:
				app.logger.warning('Maximum number of feeds reached, submit of new feed was ignored.')

			# save and return
			save_app_status()
			return redirect('/settings#add_feed')

		elif request.form.get('remove_feed'):
			feed_idx =  sanitize_feed_idx(app.feeds, request.form.get('remove_feed'))
			if feed_idx is None:
				return redirect('/settings#newsfeeds')

			f = app.feeds.pop(feed_idx)
			app.logger.info('Feed ' + f['fid'] + ': \'' + f['name'] + '\' (' + f['url'] + ') removed.')

			# remove news items of the feed
			app.news.pop(f['fid'], None)

			# save and return
			save_app_status()
			return redirect('/settings#newsfeeds')


# run main()
if __name__ == '__main__':
	main()

