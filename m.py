#!/usr/bin/env python

import urllib2, os, logging, webapp2, random
# use logging.info("") to print stuff
from google.appengine.api import memcache
from google.appengine.ext import webapp
import re
import requests
from webapp2_extras import sessions
from google.appengine.ext.webapp import template
from google.appengine.ext import db
# from stemming.porter2 import stem
import json
import praw

stem = __import__("porter2").stem


class Subreddit(db.Model):
    display_name = db.StringProperty()
    description = db.TextProperty()
    title = db.StringProperty()
    id_name = db.StringProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    tokens = db.StringListProperty()
    description_tokens = db.StringListProperty()


class TextProcess(object):
    def __init__(self):
        pass

    @staticmethod
    def read_line(a_json_string_from_document):
        # sample answer:
        return json.loads(a_json_string_from_document)

    @staticmethod
    def tokenize(string):
        unicode_word = re.findall(r'\w+', string.lower())
        return [str(word) for word in unicode_word]
        # return a list of words

    @staticmethod
    def stopword(a_list_of_words):
        stopword = []
        for line in open('data/stop_word', 'r'):
            stopword.append(re.split('\n', line)[0])
        new_list = [word for word in a_list_of_words if word not in stopword]
        return new_list

    @staticmethod
    def stemming(a_list_of_words):
        stems = [stem(word) for word in a_list_of_words]
        return stems
        # return a list of words

    @staticmethod
    def process(string):
        return [token for token in TextProcess.stemming(TextProcess.stopword(TextProcess.tokenize(string)))]


class BaseHandler(webapp2.RequestHandler):
    def render_template(self, view_filename, params={}):
        path = os.path.join(os.path.dirname(__file__), 'templates', view_filename)
        self.response.out.write(template.render(path, params))

    def render_json(self, params={}):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(params))


class RedditData():
    def __init__(self):
        self.data = {}

    def importData(self):
        with open('data/data_subreddits.json', "r") as jsonFile:
            self.data = json.load(jsonFile)

    def exportSubreddits(self):
        subreddits = []
        subreddits_bad = []
        cap = 100
        i = 0
        for key in self.data:
            try:
                if 'id' in self.data[key] and not Subreddit.all().filter('id_name =', self.data[key]['id']).get():
                    tokens = [token for token in TextProcess.stemming(TextProcess.stopword(
                        TextProcess.tokenize(''.join([post['title'] for post in self.data[key]['posts']]))))]
                    sub = Subreddit(display_name=self.data[key]['display_name'],
                                    description=self.data[key]['description'],
                                    title=self.data[key]['title'],
                                    id_name=self.data[key]['id'],
                                    tokens=tokens).put()
                    subreddits.append(key)
                    i += 1
                    if i > cap: return subreddits
            except TypeError:
                logging.warning("Couldnt do " + key)
                subreddits_bad.append(key)
        return subreddits

    def processSubreddits(self):
        client = memcache.Client()
        cursor = client.get("cursor")
        limit = 100
        e = []
        query = Subreddit.all()
        if cursor:
            query.with_cursor(cursor)
        subreddits = query.fetch(limit=limit)
        for subreddit in subreddits:
            e.append(subreddit.display_name)
            if not subreddit.tokens:
                db.delete(subreddit)
            elif not subreddit.description_tokens:
                subreddit.description_tokens = [token for token in TextProcess.stemming(
                    TextProcess.stopword(TextProcess.tokenize(subreddit.description)))]

        memcache.set(key="cursor", value=query.cursor())
        return e

    def pullRedditor(self, username):
        user = {}
        user['name'] = username
        user['posts'] = []
        r = praw.Reddit(user_agent="Reddit Recommend: Subreddit Recommender v3 [User-Grabber]")
        redditor = r.get_redditor(username)
        comment_len = 0
        for comment in redditor.get_comments(limit=100):
            comment_len += 1
            user['posts'].extend(TextProcess.process(comment.body))
        user['num']=comment_len
        return user


class MainHandler(BaseHandler):
    def get(self):
        self.render_template('index.html', {})

class PullRedditorHandler(BaseHandler):
    def get(self):
        # redditdata = RedditData()
        # redditor = redditdata.pullRedditor(self.request.get('username'))
        # self.render_json({'success': True, 'redditor': redditor})
        try:
            redditdata = RedditData()
            redditor = redditdata.pullRedditor(self.request.get('username'))
            self.render_json({'success': True, 'redditor': redditor})
        except requests.HTTPError, err:
            self.render_json({'success': False, 'reason': 'httperror'})

class ProcessHandler(BaseHandler):
    def get(self):
        reddit = RedditData()
        e = reddit.processSubreddits()
        self.render_json({'success': True, 'subreddit': e})


class ExportHandler(BaseHandler):
    def get(self):
        reddit = RedditData()
        reddit.importData()
        e = reddit.exportSubreddits()
        self.render_json({'success': True, 'subreddit': e})

class TestHandler(BaseHandler):
    def get(self):
        c = None
        count = 0
        q = Subreddit.all(keys_only=True)
        while True:
            if c:
                q.with_cursor(c)
            i = q.count(1000)
            count = count + i
            if not i:
                break
            c = q.cursor()
        self.render_template('test.html', {'hello': count})

app = webapp2.WSGIApplication([
                                  webapp2.Route('/', MainHandler, name='home'),
                                  webapp2.Route('/test', TestHandler, name='test'),
                                  webapp2.Route('/export', ExportHandler, name='export'),
                                  webapp2.Route('/process', ProcessHandler, name='process'),
                                  webapp2.Route('/user', PullRedditorHandler, name='user')
                              ], config={'webapp2_extras.sessions': {'secret_key': 'zzzzz!'}}, debug=True)