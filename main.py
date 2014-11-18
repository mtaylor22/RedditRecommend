#!/usr/bin/env python

import urllib2, os, logging, webapp2, random
#use logging.info("") to print stuff
from google.appengine.ext import webapp
from webapp2_extras import sessions
from google.appengine.ext.webapp import template
from google.appengine.ext import db
import json


class BaseHandler(webapp2.RequestHandler):
  def render_template(self, view_filename, params={}):
    path = os.path.join(os.path.dirname(__file__), 'templates', view_filename)
    self.response.out.write(template.render(path, params))

class MainHandler(BaseHandler):
    def get(self):
      self.render_template('index.html', {})
class TestHandler(BaseHandler):
    def get(self):
      self.render_template('test.html', {'hello':'world'})

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/test', TestHandler)
], debug=True)