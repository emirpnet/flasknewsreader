# newsfeed2json.py
# Version: 0.8 (2020-04-10)
# Author: Jochen Peters

import sys
import re
import json
import urllib.request
import xml.etree.ElementTree as etree
from hashlib import md5


def load_newsfeed(url):
	''' Request XML feed via HTTP and return as string '''
	try:
		fp = urllib.request.urlopen(url)
		xmlstring = fp.read().decode('utf-8')
		fp.close()
		return xmlstring
	except:
		fp.close()
		return None


def load_newsfeed_from_file(filename):
	''' Load XML feed from file and return as string '''
	try:
		with open(filename, mode='r', encoding='utf-8') as xmlfile:
			xmlstring = xmlfile.read()
		return xmlstring
	except:
		return None


def determine_feedtype(xmlstring):
	''' Determines news feed type (Atom or RSS2.0) '''

	atom_regex = re.compile('<feed\s.*xmlns=\"http:\/\/www\.w3\.org\/2005\/Atom')
	rss_regex_1 = re.compile('<rss\s.*xmlns:content=\"http:\/\/purl\.org\/rss\/1\.0\/modules\/content\/')
	rss_regex_2 = re.compile('<rss\s.*version=\"2.0\"')

	if atom_regex.search(xmlstring):
		return 1
	elif rss_regex_1.search(xmlstring) or rss_regex_2.search(xmlstring):
		return 2
	else:
		return 0


def extract_text(element):
	''' Helper function to extract text from paser element or return an empty string'''
	if element is not None:
		if element.text is not None:
			return element.text
	return ''


def extract_attrib(element, aname):
	''' Helper function to extract attribute from paser element or return an empty string'''
	if element is not None:
		if element.attrib[aname] is not None:
			return element.attrib[aname]
	return ''


def parse_atomfeed(atomfeed, remove_tags, max_entries):
	''' Parse atom feed from XML string and return news as list of dictionaries '''
	
	xmltree = etree.ElementTree(etree.fromstring(atomfeed))
	root = xmltree.getroot()
	entries = root.findall('{http://www.w3.org/2005/Atom}entry')
	
	news = []
	for entry in entries:
		title = entry.find('{http://www.w3.org/2005/Atom}title')
		summary = entry.find('{http://www.w3.org/2005/Atom}summary')
		link = entry.find('{http://www.w3.org/2005/Atom}link')
		published = entry.find('{http://www.w3.org/2005/Atom}published')
		updated = entry.find('{http://www.w3.org/2005/Atom}updated')
		
		if title.text is not None:
			t = extract_text(title)
			s = extract_text(summary)
			h = extract_attrib(link, 'href')
			p = extract_text(published)
			u = extract_text(updated)
			if remove_tags:
				t = remove_html_tags(t)
				s = remove_html_tags(s)
			news.append({'title': t, 'summary': s, 'link': h, 'published': p, 'updated': u})
		
		if len(news) >= max_entries:
			break
	
	return news


def parse_rss2feed(rssfeed, remove_tags, max_entries):
	''' Parse RSS2.0 feed from XML string and return news as list of dictionaries '''
	
	xmltree = etree.ElementTree(etree.fromstring(rssfeed))
	root = xmltree.getroot()
	channel = root.find('channel')
	items = channel.findall('item')
	
	news = []
	for item in items:
		title = item.find('title')
		summary = item.find('description')
		link = item.find('link')
		published = item.find('pubDate')
		updated = published
		
		if title.text is not None:
			t = extract_text(title)
			s = extract_text(summary)
			h = extract_text(link)
			p = extract_text(published)
			u = extract_text(updated)
			if remove_tags:
				t = remove_html_tags(t)
				s = remove_html_tags(s)
			news.append({'title': t, 'summary': s, 'link': h, 'published': p, 'updated': u})
		
		if len(news) >= max_entries:
			break
	
	return news


def parse_news(xmlstring, remove_tags=False, max_entries=80):
	''' Determines feed type and calls according parsing function '''

	feedtype = determine_feedtype(xmlstring)
	if feedtype == 1:
		#print("ATOM feed identified") # DEBUG
		return parse_atomfeed(xmlstring, remove_tags, max_entries)
	elif feedtype == 2:
		#print("RSS2 feed identified") # DEBUG
		return parse_rss2feed(xmlstring, remove_tags, max_entries)
	else:
		print("parse_news(): data is not in Atom or RSS2.0 format")
		return None


def print_news(news, format='json'):
	''' Print news (= list of dictionaries) in specified format '''

	if format.lower() == 'json':
		newsstr = json.dumps(news)
	elif format.lower() == 'plain':
		newsstr = ''
		for n in news:
			newsstr += n['title'].upper() + '\n'
			newsstr += n['summary'] + '\n'
			if n['link'] is not None:
				newsstr += '[' + n['link'] + ']\n'
			newsstr += n['updated'] + '\n'
			newsstr += ('-' * 79) + '\n'
	elif format.lower() == 'ticker':
		newsstr = ''
		for n in news:
			newsstr += n['title'].upper() + ': '
			newsstr += n['summary'] + ' --- '
	else:
		raise NameError("Invalid format name.")
	
	return newsstr


def is_valid_url(s):
	chk_regex = re.compile('^(http:\/\/|https:\/\/)[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$')
	return chk_regex.match(s)


def remove_html_tags(html):
	cleanregex = re.compile("<.*?>")
	return re.sub(cleanregex, '', html)


def create_feed_id(feed):
	return md5(feed['url'].encode('utf8')).hexdigest()


if __name__ == '__main__':
	
	if len(sys.argv) < 2:
		print("Usage: python " + sys.argv[0] + " URL")
		print("Abort.")
		sys.exit(1)
	else:
		url = sys.argv[1]
	
	try:
		xmlstring = load_newsfeed(url)
		#xmlstring = load_newsfeed_from_file('testfeed.xml') # for TESTING
	except:
		print("Error loading the feed '" + url + "'\nAbort.")
		sys.exit(2)
	
	try:
		news = parse_news(xmlstring, remove_tags=True)
	except:
		print("Error parsing the feed '" + url + "'\nAbort.")
		sys.exit(3)

	print(print_news(news, format='plain'))

