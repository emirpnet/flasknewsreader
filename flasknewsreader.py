# flasknewsreader.py
# Version: <see below>
# Author : Jochen Peters


from flask import Flask, Blueprint, current_app, render_template, request, redirect
from datetime import datetime
from operator import itemgetter
from shutil import copyfile
import json
import os

from flasknewsreader.lib.newsfeed2json import load_newsfeed, parse_news, create_feed_id, is_valid_url


# Parameters and settings
VERSION_INFO = {
	'version_number': '0.6',
	'version_date': '2020-04-13'
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
fnrapp = Blueprint('flasknewsreader', __name__, template_folder='templates', static_folder='static', static_url_path='/news/static')
fnrapp.appsettings = {}
fnrapp.feeds = {}
fnrapp.news = {}


# General functions

def main():
	# Initialize
	load_app_status()

	# start server
	if fnrapp.appsettings['remote_access']:
		fnrapp.run(host='0.0.0.0', port=8080, debug=False) # disable SSL
		#fnrapp.run(host='0.0.0.0', port=8080, debug=False, ssl_context=('cert.pem', 'key.pem'))
	else:
		fnrapp.run(host='127.0.0.1', port=8080, debug=False)


def load_app_status():
	global APPSETTINGS_FILENAME, FEEDLIST_FILENAME, NEWS_FILENAME
	this_folder = os.path.dirname(os.path.abspath(__file__))

	# load app settings
	APPSETTINGS_FILENAME= os.path.join(this_folder, APPSETTINGS_FILENAME)
	try:
		fnrapp.appsettings = load_from_json(APPSETTINGS_FILENAME)
	except:
		current_app.logger.info('Error loading application settings from ' + APPSETTINGS_FILENAME + ', restoring default settings.')
		fnrapp.appsettings = APPSETTINGS_DEFAULT
		save_to_json(fnrapp.appsettings, APPSETTINGS_FILENAME, False)

	# load feedlist
	FEEDLIST_FILENAME = os.path.join(this_folder, FEEDLIST_FILENAME)
	try:
		fnrapp.feeds = load_from_json(FEEDLIST_FILENAME)
	except:
		current_app.logger.info('Error loading feedlist from ' + APPSETTINGS_FILENAME)
		fnrapp.feeds = {}

	# load news items
	NEWS_FILENAME = os.path.join(this_folder, NEWS_FILENAME)
	try:
		fnrapp.news = load_from_json(NEWS_FILENAME)
	except:
		current_app.logger.info('Error loading feedlist from ' + APPSETTINGS_FILENAME)
		fnrapp.news = {}


def save_app_status():
	save_to_json(fnrapp.appsettings, APPSETTINGS_FILENAME, False)
	save_to_json(fnrapp.feeds, FEEDLIST_FILENAME)
	save_to_json(fnrapp.news, NEWS_FILENAME, False)


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
			current_app.logger.error('Could not create backup of ' + filename)

	# write json-file
	try:
		with open(filename, mode='w') as f:
			json.dump(dictionary, f, indent=0, separators=(',', ': '))
			current_app.logger.info(filename + ' written.')
	except:
		current_app.logger.error('Error writing ' + filename)


def fetch_news(feed):
	try:
		xmlstring = load_newsfeed(feed['url'])
		news = parse_news(xmlstring, remove_tags=True)
	except:
		news = None

	feed['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	if 'fid' not in feed:
		feed['fid'] = create_feed_id(feed)
	fnrapp.news[feed['fid']] = news


def clear_all_newsitems():
	for f in fnrapp.feeds:
		f.pop('updated', None)
	fnrapp.news = {}


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

@fnrapp.route('/news')
def news():
	load_app_status()
	feed_idx = sanitize_feed_idx(fnrapp.feeds, request.args.get('feed'))
	if feed_idx is None:
		return redirect('/news?feed=0')

	if fnrapp.appsettings['auto_update']: # or 'updated' not in fnrapp.feeds[feed_idx]:
		fetch_news(fnrapp.feeds[feed_idx])

	# save and return
	save_app_status()
	return render_template('news.html', feeds=fnrapp.feeds, feed_idx=feed_idx, news=fnrapp.news)


@fnrapp.route('/news/reload')
def news_reload():
	load_app_status()
	feed_idx = sanitize_feed_idx(fnrapp.feeds, request.args.get('feed'))
	if feed_idx is None:
		return redirect('/news?feed=0')
	fetch_news(fnrapp.feeds[feed_idx])
	# save and return
	save_app_status()
	return redirect('/news?feed=' + str(feed_idx))


@fnrapp.route('/news/settings', methods=['POST','GET'])
def news_settings():
	load_app_status()

	if request.method == 'GET':
		return render_template('settings.html', feeds=fnrapp.feeds, **fnrapp.appsettings, **VERSION_INFO)

	elif request.method == 'POST':

		if request.form.get('action') == 'save_settings':
			# remote_access
			if request.form.get('remote_access'):
				fnrapp.appsettings['remote_access'] = True
			else:
				fnrapp.appsettings['remote_access'] = False

			# auto_update
			if request.form.get('auto_update'):
				fnrapp.appsettings['auto_update'] = True
			else:
				fnrapp.appsettings['auto_update'] = False

			# save and return
			save_app_status()
			return redirect('/news/settings')

		elif request.form.get('action') == 'clear_all_news':
			clear_all_newsitems()
			save_app_status()
			return redirect('/news/settings')

		elif request.form.get('action') == 'save_feedlist':

			# grab form information
			feeds_position = []
			feeds_url = []
			feeds_active = []
			for i, f in enumerate(fnrapp.feeds):
				feeds_position.append(int(request.form.get('position_' + str(i))))

				new_url = request.form.get('url_' + str(i))
				if is_valid_url(new_url):
					feeds_url.append(new_url)
				else:
					feeds_url.append(fnrapp.feeds[i]['url'])

				if request.form.get('active_' + str(i)):
					feeds_active.append(True)
				else:
					feeds_active.append(False)

			# update feeds
			for i, f in enumerate(fnrapp.feeds):
				f['url'] = feeds_url[i]
				f['active'] = feeds_active[i]
				# now handle possible change of the fid (since it depends on the url):
				old_fid = f['fid']
				f['fid'] = create_feed_id(f)
				if old_fid in fnrapp.news:
					fnrapp.news[f['fid']] = fnrapp.news.pop(old_fid)

			# sort feeds according to position
			fnrapp.feeds = [x for _, x in sorted(zip(feeds_position, fnrapp.feeds), key=itemgetter(0))]

			# save and return
			save_app_status()
			return redirect('/news/settings#newsfeeds')

		elif request.form.get('action') == 'add_feed':
			if len(fnrapp.feeds) < MAX_NUM_FEEDS:
				new_name = request.form.get('new_name')
				new_url = request.form.get('new_url')
				new_feed_active = request.form.get('new_feed_active')
				f = {
					'name': new_name,
					'url': new_url,
					'active': new_feed_active,
				}
				f['fid'] = create_feed_id(f)
				fnrapp.feeds.append(f)
				current_app.logger.info('Feed ' + f['fid'] + ': \'' + f['name'] + '\' (' + f['url'] + ') added.')
			else:
				current_app.logger.warning('Maximum number of feeds reached, submit of new feed was ignored.')

			# save and return
			save_app_status()
			return redirect('/news/settings#add_feed')

		elif request.form.get('remove_feed'):
			feed_idx =  sanitize_feed_idx(fnrapp.feeds, request.form.get('remove_feed'))
			if feed_idx is None:
				return redirect('/news/settings#newsfeeds')

			f = fnrapp.feeds.pop(feed_idx)
			current_app.logger.info('Feed ' + f['fid'] + ': \'' + f['name'] + '\' (' + f['url'] + ') removed.')

			# remove news items of the feed
			fnrapp.news.pop(f['fid'], None)

			# save and return
			save_app_status()
			return redirect('/news/settings#newsfeeds')


# run main()
if __name__ == '__main__':
	main()

