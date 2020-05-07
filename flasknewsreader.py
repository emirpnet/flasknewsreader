# flasknewsreader.py
# Version: <see below>
# Author : Jochen Peters


from flask import Flask, Blueprint, render_template, request, redirect
from flask_login import login_required
from datetime import datetime
from operator import itemgetter
from shutil import copyfile
import json
import os
import logging

try:
	from lib.newsfeed2json import load_newsfeed, parse_news, create_feed_id, is_valid_url
except:
	from flasknewsreader.lib.newsfeed2json import load_newsfeed, parse_news, create_feed_id, is_valid_url


# Parameters and settings
VERSION_INFO = {
	'version_number': '0.7',
	'version_date': '2020-04-13'
}
MAX_NUM_FEEDS = 50
FEEDLIST_FILENAME = 'feeds.json'
NEWS_FILENAME = 'news.json'
APPSETTINGS_FILENAME = 'settings.json'
APPSETTINGS_DEFAULT = {
	#'remote_access': False,
	'auto_update': False,
}


# Globals
logger = logging.getLogger(__name__)
fnr_bp = Blueprint('flasknewsreader', __name__, template_folder='templates', static_folder='static', static_url_path='/news/static')
fnr_bp.appsettings = {}
fnr_bp.feeds = {}
fnr_bp.news = {}


# General functions

def load_app_status():
	global APPSETTINGS_FILENAME, FEEDLIST_FILENAME, NEWS_FILENAME
	this_folder = os.path.dirname(os.path.abspath(__file__))

	# load app settings
	APPSETTINGS_FILENAME= os.path.join(this_folder, APPSETTINGS_FILENAME)
	try:
		fnr_bp.appsettings = load_from_json(APPSETTINGS_FILENAME)
	except:
		logger.warning('Error loading application settings from ' + APPSETTINGS_FILENAME + ', restoring default settings.')
		fnr_bp.appsettings = APPSETTINGS_DEFAULT
		save_to_json(fnr_bp.appsettings, APPSETTINGS_FILENAME, False)

	# load feedlist
	FEEDLIST_FILENAME = os.path.join(this_folder, FEEDLIST_FILENAME)
	try:
		fnr_bp.feeds = load_from_json(FEEDLIST_FILENAME)
	except:
		logger.error('Error loading feedlist from ' + APPSETTINGS_FILENAME)
		fnr_bp.feeds = {}

	# load news items
	NEWS_FILENAME = os.path.join(this_folder, NEWS_FILENAME)
	try:
		fnr_bp.news = load_from_json(NEWS_FILENAME)
	except:
		logger.warning('Error loading news items from ' + NEWS_FILENAME)
		fnr_bp.news = {}


def save_app_status():
	save_to_json(fnr_bp.appsettings, APPSETTINGS_FILENAME, False)
	save_to_json(fnr_bp.feeds, FEEDLIST_FILENAME)
	save_to_json(fnr_bp.news, NEWS_FILENAME, False)


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
			logger.warning('Could not create backup of ' + filename)

	# write json-file
	try:
		with open(filename, mode='w') as f:
			json.dump(dictionary, f, indent=0, separators=(',', ': '))
			#logger.info(filename + ' written.')
	except:
		logger.error('Error writing ' + filename)


def fetch_news(feed):
	try:
		xmlstring = load_newsfeed(feed['url'])
		news = parse_news(xmlstring, remove_tags=True)
	except:
		news = None

	feed['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	if 'fid' not in feed:
		feed['fid'] = create_feed_id(feed)
	fnr_bp.news[feed['fid']] = news


def clear_all_newsitems():
	for f in fnr_bp.feeds:
		f.pop('updated', None)
	fnr_bp.news = {}


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

@fnr_bp.route('/news')
def news():
	load_app_status()
	feed_idx = sanitize_feed_idx(fnr_bp.feeds, request.args.get('feed'))
	if feed_idx is None:
		return redirect('/news?feed=0')

	if fnr_bp.appsettings['auto_update']: # or 'updated' not in fnr_bp.feeds[feed_idx]:
		fetch_news(fnr_bp.feeds[feed_idx])

	# save and return
	save_app_status()
	return render_template('news.html', feeds=fnr_bp.feeds, feed_idx=feed_idx, news=fnr_bp.news)


@fnr_bp.route('/news/reload')
def news_reload():
	load_app_status()
	feed_idx = sanitize_feed_idx(fnr_bp.feeds, request.args.get('feed'))
	if feed_idx is None:
		return redirect('/news?feed=0')
	fetch_news(fnr_bp.feeds[feed_idx])
	# save and return
	save_app_status()
	return redirect('/news?feed=' + str(feed_idx))


@fnr_bp.route('/news/settings', methods=['POST','GET'])
@login_required
def news_settings():
	load_app_status()

	if request.method == 'GET':
		return render_template('settings.html', feeds=fnr_bp.feeds, **fnr_bp.appsettings, **VERSION_INFO)

	elif request.method == 'POST':

		if request.form.get('action') == 'save_settings':
			## remote_access
			#if request.form.get('remote_access'):
			#	fnr_bp.appsettings['remote_access'] = True
			#else:
			#	fnr_bp.appsettings['remote_access'] = False

			# auto_update
			if request.form.get('auto_update'):
				fnr_bp.appsettings['auto_update'] = True
			else:
				fnr_bp.appsettings['auto_update'] = False

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
			for i, f in enumerate(fnr_bp.feeds):
				feeds_position.append(int(request.form.get('position_' + str(i))))

				new_url = request.form.get('url_' + str(i))
				if is_valid_url(new_url):
					feeds_url.append(new_url)
				else:
					feeds_url.append(fnr_bp.feeds[i]['url'])

				if request.form.get('active_' + str(i)):
					feeds_active.append(True)
				else:
					feeds_active.append(False)

			# update feeds
			for i, f in enumerate(fnr_bp.feeds):
				f['url'] = feeds_url[i]
				f['active'] = feeds_active[i]
				# now handle possible change of the fid (since it depends on the url):
				old_fid = f['fid']
				f['fid'] = create_feed_id(f)
				if old_fid in fnr_bp.news:
					fnr_bp.news[f['fid']] = fnr_bp.news.pop(old_fid)

			# sort feeds according to position
			fnr_bp.feeds = [x for _, x in sorted(zip(feeds_position, fnr_bp.feeds), key=itemgetter(0))]

			# save and return
			save_app_status()
			return redirect('/news/settings#newsfeeds')

		elif request.form.get('action') == 'add_feed':
			if len(fnr_bp.feeds) < MAX_NUM_FEEDS:
				new_name = request.form.get('new_name')
				new_url = request.form.get('new_url')
				new_feed_active = request.form.get('new_feed_active')
				f = {
					'name': new_name,
					'url': new_url,
					'active': new_feed_active,
				}
				f['fid'] = create_feed_id(f)
				fnr_bp.feeds.append(f)
				logger.info('Feed ' + f['fid'] + ': \'' + f['name'] + '\' (' + f['url'] + ') added.')
			else:
				logger.warning('Maximum number of feeds reached, submit of new feed was ignored.')

			# save and return
			save_app_status()
			return redirect('/news/settings#add_feed')

		elif request.form.get('remove_feed'):
			feed_idx =  sanitize_feed_idx(fnr_bp.feeds, request.form.get('remove_feed'))
			if feed_idx is None:
				return redirect('/news/settings#newsfeeds')

			f = fnr_bp.feeds.pop(feed_idx)
			logger.info('Feed ' + f['fid'] + ': \'' + f['name'] + '\' (' + f['url'] + ') removed.')

			# remove news items of the feed
			fnr_bp.news.pop(f['fid'], None)

			# save and return
			save_app_status()
			return redirect('/news/settings#newsfeeds')

