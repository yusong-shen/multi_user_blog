import os
import re
import random
import hashlib
import hmac
from string import letters

import webapp2
import jinja2

from google.appengine.ext import db

# set up the jinja , let it know where template is and load it
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

secret = 'g9823weuorhfnovkd'


def make_secure_val(val):
    """
        hash a value with secret phrase to make it more secure
    """
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    """
        check if a given value match correct format, if not return None
    """
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val


def render_str(template, **params):
    """
        helper function to format string to specific place in templete
    """
    t = jinja_env.get_template(template)
    return t.render(params)

class BlogHandler(webapp2.RequestHandler):
    """ Summary of  BlogHandler class : 
        Base case for other blog page

    """    
    def write(self, *a, **kw):
        """
            get the content from parameter and write it to html
        """
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        """
            format string to specific place in templete
        """
        return render_str(template, **params)

    def render(self, template, **kw):
        """
            call write() and reder_str()
            render the templete with given parameter
        """
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        """
            set a cookie with secure value
        """
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        """
            read a given cookie, check if it match correct format
            if so, return cookie_val, otherwise return false
        """
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        """

        """
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        """

        """
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        """
            a function called by GAE before every request.
            check if user cookie exists, if so, store the actual user object
        """
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))

def render_post(response, post):
    """
        render the post page html
    """
    response.out.write('<b>' + post.subject + '</b><br>')
    response.out.write(post.content)

class MainPage(BlogHandler):
    """ Summary of  MainPage class : 
        Main page that respond to a request with welcome
        message
    """  
    def get(self):
        self.render('index.html')


##### user stuff
def make_salt(length = 5):
    """
        make a salt : a random 5 character phrase by default
    """
    return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = None):
    """
        make a hashed salted password
    """
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)

def valid_pw(name, password, h):
    """
        check if a password is valid
    """
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)

def users_key(group = 'default'):
    """
        create the ancestor element in the database to store
        all the users
    """
    return db.Key.from_path('users', group)

class User(db.Model):
    """
        A class that represent user object
    """
    # user's attributes
    name = db.StringProperty(required = True)
    pw_hash = db.StringProperty(required = True)
    email = db.StringProperty()

    # similar to static method in Java
    @classmethod
    def by_id(cls, uid):
        """
            look up user by its id
        """
        return User.get_by_id(uid, parent = users_key())

    @classmethod
    def by_name(cls, name):
        """
            look up user by its name
        """
        u = User.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, pw, email = None):
        """
            create a new user object
        """
        pw_hash = make_pw_hash(name, pw)
        return User(parent = users_key(),
                    name = name,
                    pw_hash = pw_hash,
                    email = email)

    @classmethod
    def login(cls, name, pw):
        """

        """
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u



##### blog stuff

def blog_key(name = 'default'):
    """
        for datastore use, create a key with 'blog/[name]'
    """
    return db.Key.from_path('blogs', name)

class Post(db.Model):
    """ Summary of Post class : 
        Class represent the post entry

    """ 
    # properties that blog post entry has 
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True) # make time up-to-date
    last_modified = db.DateTimeProperty(auto_now = True) 

    def render(self):
        """
            reder post html page
        """
        self._render_text = self.content.replace('\n', '<br>') # deal with new line
        return render_str("post.html", p = self)

class BlogFront(BlogHandler):
    """ Summary of  BlogFront class : 
        handler for blog/

    """  
    def get(self):
        """
            look up all the ten most recent created post
        """
        posts = db.GqlQuery("select * from Post order by created desc limit 10")
        self.render('front.html', posts = posts)

class PostPage(BlogHandler):
    """ Summary of  PostPage class : 
        handler for particular post page

    """  
    def get(self, post_id):
        """
            get method for PostPage
            Parameter :
                post_id is passed from url
        """
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)

        # if use request a non-exist post, render 404 error
        if not post:
            self.error(404)
            return

        self.render("permalink.html", post = post)

class NewPost(BlogHandler):
    """ Summary of NewPost class : 
        New post page handler

    """  
    def get(self):
        """
            render the newpost.html
        """
        self.render("newpost.html")

    def post(self):
        """
            post method to create a new post
        """
        subject = self.request.get('subject')
        content = self.request.get('content')

        # if user enter good subject and content, redirect them to new post page
        if subject and content:
            p = Post(parent = blog_key(), subject = subject, content = content)
            p.put() # store the post element into database
            self.redirect('/blog/%s' % str(p.key().id()))
        # otherwise, render an error page    
        else:
            error = "subject and content, please!"
            self.render("newpost.html", subject=subject, content=content, error=error)


# use regular expression to validate username, password and email
USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    return password and PASS_RE.match(password)

EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)

class Signup(BlogHandler):
    """ Summary of Signup class : 
        handler for Signup page

        Attributes :
            username : a string represent username
            password : a string represent hashed password
            verify : a bool value represent if verified
            email : a string represent email address

    """  
    def get(self):
        """
            get method to render signup-form.html        
        """
        self.render("signup-form.html")

    def post(self):
        """
            post method to process signup form
        """
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')

        params = dict(username = self.username,
                      email = self.email)

        if not valid_username(self.username):
            params['error_username'] = "That's not a valid username."
            have_error = True

        if not valid_password(self.password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True

        if not valid_email(self.email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('signup-form.html', **params)
        else:
            self.done()

    def done(self, *a, **kw):
        """
            base method need to be override
        """
        raise NotImplementedError


class Register(Signup):
    """
        Inherit from Signup base class
    """
    def done(self):
        """
            method invoked when sign up input is valid
            if user sign up successfully, make them login and redirect
            them to blog page
        """
        #make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('signup-form.html', error_username = msg)
        else:
            u = User.register(self.username, self.password, self.email)
            u.put()

            self.login(u)
            self.redirect('/blog')

class Login():
    pass

class Logout():
    pass
                                

class Welcome(BlogHandler):
    """ Summary of Welcome class : 
        Handler for welcome page 
    """  
    def get(self):
        """
            get method to render welcome.html if user signup
            successfully, otherwise redirect user back to signup
            page 
        """
        if self.user:
            self.render('welcome.html', username = self.user.name)
        else:
            self.redirect('/signup')

# route the url to specific web handler class
app = webapp2.WSGIApplication([('/', MainPage),
                               ('/signup', Register),
                               ('/welcome', Welcome),
                               ('/blog/?', BlogFront),
                               ('/blog/([0-9]+)', PostPage),
                               ('/blog/newpost', NewPost),
                               ('/login', Login),
                               ('/logout', Logout),
                               ],
                              debug=True)
