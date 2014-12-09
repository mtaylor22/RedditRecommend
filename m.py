#!/usr/bin/env python
import httplib
from google.appengine.api import urlfetch
import os
import logging
import operator
import urllib
import urllib2

import webapp2
from google.appengine.api import memcache
import re
from google.appengine.ext.db import NotSavedError
import requests
from google.appengine.ext.webapp import template
from google.appengine.ext import db
import json
import praw
from math import log10, sqrt, isnan

stem = __import__("porter2").stem
mongo = __import__("pymongo")
json_util = __import__("json_util")
secret = __import__("pass")

class Term(db.Model):
    term = db.StringProperty()


class Subreddit(db.Model):
    display_name = db.StringProperty()
    description = db.TextProperty()
    title = db.StringProperty()
    id_name = db.StringProperty()
    tokens = db.StringListProperty()
    description_tokens = db.StringListProperty()


class TF(db.Model):
    num = db.IntegerProperty()
    term = db.ReferenceProperty(Term)


class IDF(db.Model):
    num = db.IntegerProperty()
    term = db.ReferenceProperty(Term)
    subreddit = db.ReferenceProperty(Subreddit)


class IDF_simple():
    def __init__(self, term, num, subreddit):
        self.num = num
        self.term = term
        self.subreddit = subreddit


def getIDFBySubreddit(idfList, subreddit):
    newlist = []
    for idf in idfList:
        if idf.subreddit == subreddit:
            newlist.append(idf)
    return newlist


def getIDFByTerm(idfList, term):
    newlist = []
    for idf in idfList:
        if idf.term == term:
            newlist.append(idf)
    return newlist


def getIDFBySubredditTerm(idfList, subreddit, term):
    newlist = []
    for idf in idfList:
        if idf.term == term and idf.subreddit == subreddit:
            newlist.append(idf)
    return newlist


def getSubreddits(idfList):
    subreddits = []
    for item in idfList:
        if item.subreddit not in subreddits:
            subreddits.append(item.subreddit)
    return subreddits


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
        return [str(word) for word in unicode_word if not isinstance(word, int)]
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
        cap = 1000
        i = 1
        for key in self.data:
            try:
                if 'id' in self.data[key] and not Subreddit.all().filter('id_name =', self.data[key]['id']).get():
                    tokens = [token for token in TextProcess.stemming(TextProcess.stopword(
                        TextProcess.tokenize(''.join([post['title'] for post in self.data[key]['posts']]))))]
                    if not tokens:
                        pass
                    tokens_desc = [token for token in TextProcess.stemming(
                        TextProcess.stopword(TextProcess.tokenize(self.data[key]['description'])))]
                    sub = Subreddit(display_name=self.data[key]['display_name'],
                                    description=self.data[key]['description'],
                                    title=self.data[key]['title'],
                                    id_name=self.data[key]['id']).put()
                    subreddits.append(key)
                    tc = {}
                    for token in tokens:
                        if token in tc:
                            tc[token] += 1
                        else:
                            tc[token] = 1

                    tokens = [([t[0]] * t[1]) for t in
                              sorted(tc.items(), key=operator.itemgetter(1), reverse=True)[:20]]
                    tokens = [a for item in tokens for a in item]

                    for token in tokens:
                        term = Term.all().filter("term =", token).get()
                        if not term:
                            term = Term(term=token)
                        term.put()

                        tf = TF.all().filter("term =", term).get()
                        if not tf:
                            tf = TF(term=term, num=0)
                        tf.num += 1
                        tf.put()

                        idf = IDF.all().filter("term =", term).filter("subreddit =", sub).get()
                        if not idf:
                            idf = IDF(term=term, subreddit=sub, num=0)
                        idf.num += 1
                        idf.put()
                    i += 1
                    if i > cap:
                        return subreddits

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

    @staticmethod
    def pullRedditor(username, limit=4):
        cachedRedditor = memcache.get('_r_' + username)
        if (cachedRedditor is not None):
            return cachedRedditor
        user = {}
        user['name'] = username
        user['posts'] = []
        r = praw.Reddit(user_agent="Reddit Recommend:Subreddit Recommender v9 [User-Grabber]")
        redditor = r.get_redditor(username)
        comment_len = 0
        logging.info("Actually limiting to " + limit)
        for comment in redditor.get_comments(limit=int(limit)):
            comment_len += 1
            user['posts'].extend(TextProcess.process(comment.body))
        user['num'] = comment_len
        memcache.add('_r_'+username, user)
        return user

    def getTFIDF(self, term, subreddit, num_subreddits):
        tf = TF.all().filter("term =", term).get()
        df = IDF.all().filter("term =", term).filter("subreddit =", subreddit).get()
        return 1 + log10(tf) * log10(num_subreddits / df)

    def getAllTF(self):
        terms = []
        query = TF.all()
        cursor = None
        while True:
            if cursor:
                query = query.with_cursor(cursor)
            a = query.fetch(limit=100)
            if not a:
                return
            terms.extend(a)
            cursor = query.cursor()
        return terms


    def getAllIDF(self):
        terms = []
        query = IDF.all()
        cursor = None
        while True:
            if cursor:
                query = query.with_cursor(cursor)
            a = query.fetch(limit=100)
            if not a:
                return
            terms.extend(a)
            cursor = query.cursor()
        return terms


    def cosineRedditor(self, redditor, num_subreddits, update=False):
        # Pull TF & IDF for redditor
        tf = memcache.get('tf')
        if tf is None:
            tf = {}
        idf = memcache.get('idf')
        if idf is None:
            idf = []

        logging.info("Gathering TF...")
        if not tf:
            allTF = self.getAllTF()
            if allTF:
                for a in allTF:
                    tf[a.term.term] = a.num
        else:
            logging.info("(Cached)...")

        memcache.add('tf', tf)

        logging.info("Gathering IDF...")
        if not idf:
            allIDF = self.getAllIDF()
            if allIDF:
                for a in allIDF:
                    idf.append(IDF_simple(a.term.term, a.num, a.subreddit.display_name))
        else:
            logging.info("(Cached)...")

        memcache.add('idf', idf)

        logging.info("Adding Redditor")
        for token in redditor['posts']:
            if token in tf:
                tf[token] += 1
            else:
                tf[token] = 1
            item = getIDFBySubredditTerm(idf, '%REQUESTING_REDDITOR%', token)
            if not item:
                item = IDF_simple(token, 1, '%REQUESTING_REDDITOR%')
                idf.append(item)
            else:
                item = item[0]
            item.num += 1

        logging.info("Normalizing...")
        # Vector Normalization
        tfidf = []
        magnitude = {}
        for item in idf:
            term = item.term
            num = item.num
            subreddit = item.subreddit
            tfidf_item = IDF_simple(term, 1 + log10(tf[item.term]) * log10(num_subreddits / num), subreddit)
            tfidf.append(tfidf_item)
            if subreddit in magnitude:
                magnitude[subreddit] += tfidf_item.num * tfidf_item.num
            else:
                magnitude[subreddit] = tfidf_item.num * tfidf_item.num

        for item in tfidf:
            item.num /= magnitude[item.subreddit]

        cosine_scores = []

        logging.info("Cosine Calculation...")
        user_vec = getIDFBySubreddit(tfidf, '%REQUESTING_REDDITOR%')
        for subreddit in getSubreddits(tfidf):
            cosine = 0
            sub_vec = getIDFBySubreddit(tfidf, subreddit)
            for a in sub_vec:
                if getIDFBySubredditTerm(tfidf, '%REQUESTING_REDDITOR%', a.term):
                    cosine += getIDFBySubredditTerm(tfidf, '%REQUESTING_REDDITOR%', a.term)[0].num * a.num
            cosine_scores.append([subreddit, cosine])

        logging.info("Cosine finished.")
        return cosine_scores


class MainHandler(BaseHandler):
    def get(self):
        words = ""
        with open('words.json', "r") as jsonFile:
            words = json.load(jsonFile)

        self.render_template('index.html', {'words': words['words']})

class jTestHandler(BaseHandler):
    def get(self):
        self.render_template('jtest.html', {})


class PullRedditorHandler(BaseHandler):
    def get(self):
        try:
            redditdata = RedditData()
            if self.request.get('username'):
                redditor = redditdata.pullRedditor(self.request.get('username'), self.request.get('limit'))
            else:
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
        reddit = RedditData()
        if self.request.get('username'):
            redditor = reddit.pullRedditor(self.request.get('username'), self.request.get('limit'))
        else:
            redditor = reddit.pullRedditor(self.request.get('username'))
        results = reddit.cosineRedditor(redditor, 200)
        self.render_json({'success': True, 'results': results})


class ConsoleHandler(BaseHandler):
    def get(self):
        logging.info("HELLO?")
        self.render_json({'success': True})


class Mongo():
    def __init__(self):
        self.mongoClient = mongo.MongoClient('mongodb://redditrec:redditrec@ds053310.mongolab.com:53310/redditrec')
        self.db = self.mongoClient.redditrec
        self.subreddit = self.db.subreddit
        self.tf = self.db.tf
        self.df = self.db.df

    def getAllSubreddits(self):
        return [item['display_name'] for item in self.subreddit.find()]

    def findSubredditByIdHTTP(self, id):
        url = "https://api.mongolab.com/api/1/databases/" + secret.db + "/collections/subreddit?q={'_id':{'$oid':'" + str(id) + "'}}&fo=true&apiKey="+secret.key
        logging.info("URL: "+url)
        return json_util.loads(urlfetch.fetch(url).content)


    def findSubredditById(self, id):
        return self.subreddit.find_one({'_id' : id})

    def getDFBySubreddit(self, subreddit_id):
        return [{'term':sub['term'], 'count':sub['count']} for sub in self.df.find({'sub': subreddit_id})]

    def countSubreddits(self):
        return self.subreddit.count()

    def countTF(self, term):
        count = self.tf.find_one({'term': term})
        return 0 if not count else count['count']

    def countDF(self, term, subreddit_id):
        return self.df.find_one({'term': term, 'sub': subreddit_id})['count']

    def getAllTF(self, sort=False, limit=0):
        if sort:
            return [{'term': item['term'], 'count':item['count']} for item in self.tf.find().sort('count', mongo.DESCENDING).limit(limit)]
        else:
            return [{'term': item['term'], 'count':item['count']} for item in self.tf.find().limit(limit)]

    def getAllDF(self, sort=False, limit=0):
        if sort:
            return [{'term': item['term'], 'count':item['count'], 'sub':self.findSubredditById(item['sub'])} for item in self.df.find().sort('count', mongo.DESCENDING).limit(limit)]
        else:
            return [{'term': item['term'], 'count':item['count'], 'sub':self.findSubredditById(item['sub'])} for item in self.df.find().limit(limit)]


    def tfCount(self):
        return self.tf.count()

    def dfCount(self):
        return self.tf.count()

    def processTFIDF(self):
        #     For each IDF
        #     compute tfidf for that term in that document
        #     Note: tf, idf, subreddit should be complete when computed
        subredditCount = self.countSubreddits()
        logging.info("Starting TFIDF")
        for df in self.db.df.find():
            try:
                tfidf = 1 + log10(df['count'])*log10(subredditCount/self.countTF(df['term']))
                item = {'term': df['term'], 'sub': df['sub'], 'tfidf': tfidf}
                if self.db.tfidf.find(item).count() == 0:
                    self.db.tfidf.insert(item)
            except ValueError:
                logging.info("Hit a domain error for " + str(df['term']) + " in " + str(self.findSubredditById(df['sub'])['display_name']) + ".")
                # logging.info("Output "+term+" for " + subreddit)

    def mongoNormalization(self):
        #     for each subreddit
        subredditCount = self.countSubreddits()
        i = 0
        for subreddit in self.db.subreddit.find().sort('$natural', mongo.DESCENDING):
            #     find all tfidf values
            if 'tfidf_n' in self.db.tfidf.find_one({'sub': subreddit['_id']}):
                logging.info("Skipped "+subreddit['display_name'])
                continue
            i+=1
            logging.info("On ("+str(i)+"/"+str(subredditCount)+"): "+str(subreddit['display_name']))
            length = 0
            for tfidf in self.db.tfidf.find({'sub': subreddit['_id']}):
                length += tfidf['tfidf']*tfidf['tfidf']
            length = sqrt(length)
            for tfidf in self.db.tfidf.find({'sub': subreddit['_id']}):
                count = tfidf['tfidf']
                self.db.tfidf.update({'_id': tfidf['_id']}, {'$set': {'tfidf_n': count/length}})

    def mongoCosine_getRedditor(self, name, limit=4):
        logging.info("Imposing limit of " + limit)
        logging.info("Starting Cosine")
        subredditCount = self.countSubreddits()
        tf = {}
        df = {}

        logging.info("Collecting User TF, DF")
        redditor = RedditData.pullRedditor(name, limit)
        # Collect tf and df
        for post in redditor['posts']:
            tf[post] = self.countTF(post)+1 if post not in tf else tf[post]+1
            df[post] = 1 if post not in df else df[post]+1

        return {'tf': tf, 'df': df, 'sub_count': subredditCount}

    def mongoCosine_userTFIDF(self, tf, df, subredditCount):
        # Compute TFIDF
        logging.info("WOrking with: ")
        logging.info(tf)
        logging.info(df)
        tfidf = {}
        length = 0.0
        todel = []
        for post in df:
            logging.info(df[post])
            logging.info(tf[post])
            try:
                tfidf[post] = 1 + log10(df[post])*log10(subredditCount/tf[post])
                if isnan(tfidf[post]):
                    todel.append(post)
                    logging.error("Nan value error on "+str(post))
                else:
                    length += tfidf[post] * tfidf[post]
            except ValueError:
                todel.append(post)
                logging.error("User value error on "+str(post))

        for post in todel:
            tfidf.pop(post, None)
            tf.pop(post, None)
            df.pop(post, None)

        length = sqrt(length)
        for post in tfidf:

            # Normalize
            tfidf[post] /= length


        return {'tf': tf, 'df': df, 'tfidf': tfidf, 'sub_count': subredditCount}

    def mangoCosine_processTerm(self, tfidf, post, cosine):
        todel = []
        for term in self.db.tfidf.find({'term': post}):
            termSub = memcache.get(str(term['sub']))
            if termSub is None:
                termSub = self.findSubredditById(term['sub'])['display_name']
                memcache.add(str(term['sub']), termSub)
            computed = term['tfidf_n'] * tfidf[post]
            cosine[termSub] = computed if termSub not in cosine else cosine[termSub] + computed
        todel = []
        for term in cosine:
            if isnan(cosine[term]):
                todel.append(term)

        for term in todel:
            del cosine[term]
        return cosine

    def mongoCosine(self, redditor):
        # for subreddit in self.db.subreddit.find():
        #     for tfidf in self.db.tfidf.find({'sub': subreddit['_id']}):
        #         # Each Term in the document

        # tfidf for redditor document
        logging.info("Starting Cosine")
        subredditCount = self.countSubreddits()
        tf = {}
        df = {}

        logging.info("Collecting User TF, DF")
        redditor = RedditData.pullRedditor(redditor)
        # Collect tf and df
        for post in redditor['posts']:
            tf[post] = self.countTF(post)+1 if post not in tf else tf[post]+1
            df[post] = 1 if post not in tf else tf[post]+1


        logging.info("Computing User TFIDF")
        # Compute TFIDF
        tfidf = {}
        length = 0.0
        todel = []
        for post in df:
            try:
                tfidf[post] = 1 + log10(df[post])*log10(subredditCount/tf[post])
                if isnan(tfidf[post]):
                    todel.append(post)
                    logging.error("Nan value error on "+str(post))
                else:
                    length += tfidf[post] * tfidf[post]
            except ValueError:
                todel.append(post)
                logging.error("User value error on "+str(post))

        for post in todel:
            tfidf.pop(post, None)
            tf.pop(post, None)
            df.pop(post, None)

        length = sqrt(length)


        logging.info("Normalizing and Computing Cosine")
        cosine = {}
        for post in tfidf:
            # Normalize
            tfidf[post] /= length

            for term in self.db.tfidf.find({'term': post}):
                termSub = memcache.get(str(term['sub']))
                if termSub is None:
                    termSub = self.findSubredditById(term['sub'])['display_name']
                    memcache.add(str(term['sub']), termSub)
                computed = term['tfidf_n'] * tfidf[post]
                cosine[termSub] = computed if termSub not in cosine else cosine[termSub] + computed
        return cosine

    def mongoCosineHTTP(self, redditor):
        # for subreddit in self.db.subreddit.find():
        #     for tfidf in self.db.tfidf.find({'sub': subreddit['_id']}):
        #         # Each Term in the document

        # tfidf for redditor document
        logging.info("Starting Cosine")
        subredditCount = self.countSubreddits()
        tf = {}
        df = {}

        logging.info("Collecting User TF, DF")
        # Collect tf and df
        for post in redditor['posts']:
            tf[post] = self.countTF(post)+1 if post not in tf else tf[post]+1
            df[post] = 1 if post not in tf else tf[post]+1


        logging.info("Computing User TFIDF")
        # Compute TFIDF
        tfidf = {}
        length = 0.0
        todel = []
        for post in df:
            try:
                tfidf[post] = 1 + log10(df[post])*log10(subredditCount/tf[post])
                if isnan(tfidf[post]):
                    todel.append(post)
                    logging.error("Nan value error on "+str(post))
                else:
                    length += tfidf[post] * tfidf[post]
            except ValueError:
                todel.append(post)
                logging.error("User value error on "+str(post))

        for post in todel:
            tfidf.pop(post, None)
            tf.pop(post, None)
            df.pop(post, None)

        length = sqrt(length)


        logging.info("Normalizing and Computing Cosine")
        cosine = {}
        id_tracking = []
        for post in tfidf:
            # Normalize
            tfidf[post] /= length
            url = "https://api.mongolab.com/api/1/databases/"+secret.db+"/collections/tfidf?q={'term':'" + str(post) + "'}&f={'term':1,'sub':1,'tfidf_n':1}&apiKey="+secret.key
            # logging.info("URL: "+url)
            logging.info("Term: "+post)
            try:
                terms = json_util.loads(urlfetch.fetch(url).content)
                for term in terms:
                    termSub = memcache.get(str(term['sub']))
                    if termSub is None:
                        termSub = self.findSubredditByIdHTTP(term['sub'])['display_name']
                        memcache.add(str(term['sub']), termSub)
                    # termSub = term['sub']
                    computed = term['tfidf_n'] * tfidf[post]
                    cosine[termSub] = computed if termSub not in cosine else cosine[termSub] + computed
            except httplib.HTTPException:
                logging.error("Couldn't use "+post)
        return cosine

    def getSubredditData(self, subreddit_id):
        sub = self.db.subreddit.find_one({'_id' if isinstance(subreddit_id, int) else 'display_name': subreddit_id})
        terms = [{'term': term['term'], 'count': term['count']} for term in self.db.df.find({'sub': sub['_id']})]
        return {'name': sub['display_name'], 'desc': sub['description'], 'title': sub['title'], 'terms': terms, 'link': 'http://reddit.com/r/'+sub['display_name'    ]}

    def getTermData(self, term):
        tf = self.db.tf.find_one({'term': term})
        if not tf:
            return
        df = [{'subreddit': self.findSubredditById(df['sub'])['display_name'], 'count': df['count']} for df in self.db.df.find({'term': term})]

        return {'total_occurrences': tf['count'], 'rank': self.getTermRank(term), 'outof': self.tfCount(), 'subreddit_occurrences': sorted(df, key=lambda l: l['count'], reverse=True)}

    def getTermsSortedTF(self, limit=100):
        terms = self.getAllTF(True, limit)
        return [term for term in terms if not isnan(term['count'])]

    def getTermsSortedDF(self, limit=100):
        df = self.getAllDF(True, limit)
        for item in df:
            item['sub'] = item['sub']['display_name']
        return df

    def getTermRank(self, needle):
        terms = self.getAllTF(True)
        i = 0
        count = 0
        for term in terms:
            i += 1
            if term['term'] == needle:
                break
        return i


class MongoTest(BaseHandler):
    def get(self):
        mongo = Mongo()
        # mongo.subreddit.find_one()
        # tf = [a['display_name'] for a in mongo.subreddit.find()]
        funny_id = mongo.subreddit.find_one({'display_name':'funny'})['_id']
        self.render_json({'success': True, 'item': mongo.getAllSubreddits()})

class Process(BaseHandler):
    def get(self):
        mongo = Mongo()
        mongo.processTFIDF()
        self.render_json({'success': True})
class Normalize(BaseHandler):
    def get(self):
        mongo = Mongo()
        mongo.mongoNormalization()
        self.render_json({'success': True})

class Cosine(BaseHandler):
    def get(self):
        mongo = Mongo()
        if not self.request.get('username'):
            raise Exception("You must specify Username")
        results = mongo.mongoCosine(self.request.get('username'))
        self.render_json({'success': True, 'results': results})

class CosineHTTP(BaseHandler):
    def get(self):
        mongo = Mongo()
        if not self.request.get('username'):
            raise Exception("You must specify Username")
        redditor = RedditData.pullRedditor(self.request.get('username'))
        results = mongo.mongoCosineHTTP(redditor)
        self.render_json({'success': True, 'results': results})

class Sub(BaseHandler):
    def get(self):
        mongo = Mongo()
        if not self.request.get('subreddit'):
            raise Exception("You must specify subreddit")
        subreddit = mongo.getSubredditData(self.request.get('subreddit'))
        self.render_json({'success': True, 'subreddit': subreddit})

class TermHandler(BaseHandler):
    def get(self):
        mongo = Mongo()
        if not self.request.get('term'):
            raise Exception("You must specify term")
        term = mongo.getTermData(self.request.get('term'))
        if not term:
            self.render_json({'success': False})
        else:
            self.render_json({'success': True, 'term': term})


class termsTF(BaseHandler):
    def get(self):
        mongo = Mongo()
        if self.request.get('limit'):
            terms = mongo.getTermsSortedTF(int(self.request.get('limit')))
        else:
            terms = mongo.getTermsSortedTF()
        self.render_json({'success': True, 'terms': terms})

class termsDF(BaseHandler):
    def get(self):
        mongo = Mongo()
        if self.request.get('limit'):
            terms = mongo.getTermsSortedDF(int(self.request.get('limit')))
        else:
            terms = mongo.getTermsSortedDF()
        self.render_json({'success': True, 'terms': terms})

class CosineGetRedditor(BaseHandler):
    def get(self):
        mongo = Mongo()
        if not self.request.get('username'):
            raise Exception("You must specify username")
        if self.request.get('limit'):
            redditor = mongo.mongoCosine_getRedditor(self.request.get('username'), self.request.get('limit'))
        else:
            redditor = mongo.mongoCosine_getRedditor(self.request.get('username'))
        self.render_json({'success': True, 'redditor': redditor})
class CosineProcessRedditor(BaseHandler):
    def get(self):
        mongo = Mongo()
        if not self.request.get('tf'):
            raise Exception("You must specify tf")
        tf = json.loads(self.request.get('tf'))
        if not self.request.get('df'):
            raise Exception("You must specify df")
        df = json.loads(self.request.get('tf'))
        if not self.request.get('subredditCount'):
            raise Exception("You must specify Subreddit Count")
        subredditCount = int(self.request.get('subredditCount'))
        data = mongo.mongoCosine_userTFIDF(tf, df, subredditCount)
        self.render_json({'success': True, 'data': data})

class CosineProcessTerm(BaseHandler):
    def get(self):
        mongo = Mongo()
        if not self.request.get('tfidf'):
            raise Exception("You must specify tfidf")
        tfidf = json.loads(self.request.get('tfidf'))
        if not self.request.get('post'):
            raise Exception("You must specify post")
        post = self.request.get('post')
        if self.request.get('cosine'):
            cosine = json.loads(self.request.get('cosine'))
        data = mongo.mangoCosine_processTerm(tfidf, post, cosine)
        self.render_json({'success': True, 'data': data})

app = webapp2.WSGIApplication([
    webapp2.Route('/', MainHandler, name='home'),
    webapp2.Route('/test', TestHandler, name='test'),
    webapp2.Route('/export', ExportHandler, name='export'),
    # webapp2.Route('/process', ProcessHandler, name='process'),
    webapp2.Route('/user', PullRedditorHandler, name='user'),
    webapp2.Route('/mongo', MongoTest, name='MongoTest'),
    webapp2.Route('/process', Process, name='process'),
    webapp2.Route('/normalize', Normalize, name='process'),
    webapp2.Route('/console', ConsoleHandler, name='console'),
    webapp2.Route('/cosine', Cosine, name='cosine'),
    webapp2.Route('/cosinehttp', CosineHTTP, name='cosine'),
    webapp2.Route('/sub', Sub, name='sub'),
    webapp2.Route('/term', TermHandler, name='term'),
    webapp2.Route('/termstf', termsTF, name='termsTF'),
    webapp2.Route('/termsdf', termsDF, name='termsDF'),
    webapp2.Route('/getRedditor', CosineGetRedditor, name='CosineGetRedditor'),
    webapp2.Route('/processRedditor', CosineProcessRedditor, name='CosineProcessRedditor'),
    webapp2.Route('/processTerm', CosineProcessTerm, name='CosineProcessTerm'),
    webapp2.Route('/jtest', jTestHandler, name='jtest'),

    ], config={'webapp2_extras.sessions': {'secret_key': 'zzzzz!'}}, debug=True)