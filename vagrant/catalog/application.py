from flask import Flask
from flask import redirect
from flask import url_for
from flask import request
from flask import session
from flask import render_template
from flask import make_response
from flask.json import jsonify
from flask.json import JSONEncoder
from flask_sqlalchemy import SQLAlchemy
from models import db
from models import Category
from models import CatalogItem
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from functools import wraps
import pprint
import httplib2
import requests
import json
import os
import random
import string
import hashlib
from flaskext.markdown import Markdown


# load OAuth secrets
client_secrets = json.loads(open('client_secrets.json', 'r').read())
CLIENT_ID = client_secrets['web']['client_id']


# initializing Flask & DB
app = Flask(__name__, template_folder='templates')
app.debug = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///catalog.db'
db.init_app(app)


# create a random string
def getRandomString():
    return (''.join(random.choice(string.ascii_uppercase + string.digits)
            for x in xrange(32)))


# get the current anti-csrf token
def getSyncToken():
    state = session.get('state')
    if state is None:
        state = getRandomString()
        session['state'] = state
    return state


# get the nonce for deleting an object
def getNonce(table, id):
    txt = getSyncToken()
    txt += "/" + table + ":" + str(id)
    return hashlib.sha256(txt).hexdigest()


# decorator: is the user logged in?
# Otherwise redirect to page /login
def requires_login(func):
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        # is the user not yet logged in?
        if session.get('access_token') is None:
            return redirect(url_for('showLogin'))
        else:
            return func(*args, **kwargs)
    return func_wrapper


# helper function: get a field from the request body
# irrespective if the body is JSON or multipart
# or urlencoded
def get_request_field(name):
    value = request.form.get(name)
    if value is None:
        json_body = request.get_json(force=True, silent=True, cache=True)
        if json_body is not None:
            value = json_body.get(name)
    return value


# subclass of JSONEncoder: allow jsonify of my model objects
# http://stackoverflow.com/questions/21411497/flask-jsonify-a-list-of-objects
class MyJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Category):
            return {
                'id': obj.id,
                'name': obj.name,
                'image_url': obj.image_url
            }
        return super(MyJSONEncoder, self).default(obj)


# helper function: is a delete operation requested?
def request_wants_delete():
    # check method
    if request.method == 'DELETE':
        return True
    # check argument 'operation'
    if request.args.get('operation', '') == 'delete':
        return True
    # otherwise: no, update is requested
    return False


# helper function: does the request want JSON?
# taken from http://flask.pocoo.org/snippets/45/
# and adjusted
def request_wants_json():
    # check the request's Accept-Header
    best = request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    wants_json = (best == 'application/json' and
                  request.accept_mimetypes[best] >
                  request.accept_mimetypes['text/html'])
    # check for the parameter 'type' being 'json'
    if request.args.get('type', '') == 'json':
        wants_json = True
    return wants_json


# function to render the output - either as JSON or as HTML
def flex_render(template, **kwargs):
    if request_wants_json():
        # JSON response: we send what we get as JSON
        return jsonify(**kwargs)
    else:
        # for HTML output we inject the CSRF-Token, the OAuth CLIENT_ID,
        # if the user is logged-in and the list of categories
        kwargs['AUTHENTICATED'] = (session.get('access_token') is not None)
        kwargs['CLIENT_ID'] = CLIENT_ID
        kwargs['STATE'] = getSyncToken()
        kwargs['categories'] = db.session.query(Category).all()
        return render_template(template, **kwargs)


# When a user is accessing a protected page unauthenticated they
# are redirected to this page
@app.route('/login')
def showLogin():
    return flex_render('error.html',
                       error='Operation requires authentication')


# Start page: show categories and latest items
@app.route('/')
def index():
    # ask Database for all categories
    categories = db.session.query(Category).all()
    # ask Database for the last 10 items
    items = db.session.query(CatalogItem). \
        order_by(CatalogItem.id.desc()).limit(10).all()
    return flex_render('index.html', categories=categories, items=items)


# Show all categories
@app.route('/categories/', methods=['GET'])
def listCategories():
    # ask Database for all categories
    categories = db.session.query(Category).all()
    return flex_render('listCategories.html', categories=categories)


# add a category: post to /categories/
@app.route('/categories/', methods=['POST'])
@requires_login
def addCategory():
    # get category data from request
    name = get_request_field('name')
    image_url = get_request_field('image_url')
    if name == '':
        return flex_render('newCategory.html',
                           name=name, image_url=image_url,
                           error='Field "name" is mandatory')
    # add the category
    category = Category(name=name, image_url=image_url)
    db.session.add(category)
    db.session.commit()
    # show the newly added category
    return showCategory(id=category.id)


# show a specific category: get /categories/<id>
@app.route('/categories/<int:id>', methods=['GET'])
def showCategory(id):
    # load the specified category from DB
    category = db.session.query(Category).filter_by(id=id).one()
    # load the contained items
    items = db.session.query(CatalogItem).filter_by(category_id=id).all()
    # get the nonce for the category
    nonce = getNonce('category', id)
    # show category and items
    return flex_render('showCategory.html',
                       category=category, items=items, nonce=nonce)


# update (delete) a specific category: post/put/delete /categories/<id>
@app.route('/categories/<int:id>', methods=['POST', 'PUT', 'DELETE'])
@requires_login
def updateDeleteCategory(id):
    # load the specified category from DB
    category = db.session.query(Category).filter_by(id=id).one()
    if request_wants_delete():
        # we check the nonce
        nonce1 = request.args.get('nonce')
        nonce2 = getNonce('category', id)
        if nonce1 != nonce2:
            return flex_render(
                'error.html',
                error='Delete failed - nonce missing or incorrect')
        # first we delete all contained items as well
        db.session.query(CatalogItem).filter_by(category_id=id).delete()
        # then delete the category itself
        name = category.name
        db.session.delete(category)
        db.session.commit()
        # return OK message
        return flex_render('feedback.html',
                           message=('Category "%s" (id=%s) has been deleted'
                                    % (name, id)),
                           nextUrl=url_for('listCategories'))
    # update with data specified
    name = get_request_field('name')
    image_url = get_request_field('image_url')
    if name == '':
        return flex_render('editCategory.html',
                           name=name, image_url=image_url, id=id,
                           error='Field "name" is mandatory')
    # update the category
    category.name = name
    category.image_url = image_url
    db.session.add(category)
    db.session.commit()
    # show the updated category
    return showCategory(id)


# add an item: post to /items/
@app.route('/items/', methods=['POST'])
@requires_login
def addItem():
    # load category from request data
    category_id = get_request_field('category_id')
    # check if the category exists
    category = db.session.query(Category).filter_by(id=category_id).one()
    # get item data from request
    name = get_request_field('name')
    description = get_request_field('description')
    image_url = get_request_field('image_url')
    # name is a required field for a category
    if name == '':
        return flex_render('newItem.html',
                           name=name, description=description,
                           image_url=image_url, category_id=category_id,
                           error='Field "name" is mandatory')
    # add the item
    item = CatalogItem(name=name, description=description,
                       image_url=image_url, category=category)
    db.session.add(item)
    db.session.commit()
    # show the newly added item
    return showItem(id=item.id)


# show a specific item: get /items/<id>
@app.route('/items/<int:id>', methods=['GET'])
def showItem(id):
    # load the specified item from DB
    item = db.session.query(CatalogItem).filter_by(id=id).one()
    # get nonce
    nonce = getNonce('item', id)
    # show item
    return flex_render('showItem.html', item=item, nonce=nonce)


# update/delete an item: post/put/delete /items/<id>
@app.route('/items/<int:id>', methods=['POST', 'PUT', 'DELETE'])
@requires_login
def updateDeleteItem(id):
    # load the specified item from DB
    item = db.session.query(CatalogItem).filter_by(id=id).one()
    if request_wants_delete():
        # verify the nonce
        nonce1 = request.args.get('nonce')
        nonce2 = getNonce('item',id)
        if nonce1 != nonce2:
            return flex_render(
                'error.html',
                error='Delete failed - nonce value missing or incorrect')
        name = item.name
        category_id = item.category_id
        db.session.delete(item)
        db.session.commit()
        # return OK message
        return flex_render(
            'feedback.html',
            message=('Catalog item "%s" (id=%s) has been deleted'
                     % (name, id)),
            nextUrl=url_for('showCategory', id=category_id))
    # update with data specified
    name = get_request_field('name')
    description = get_request_field('description')
    image_url = get_request_field('image_url')
    category_id = get_request_field('category_id')
    # check if new category id exists
    category = db.session.query(Category).filter_by(id=category_id).one()
    if name == '':
        return flex_render(
            'editItem.html',
            name=name, description=description,
            category_id=category_id, image_url=image_url, id=id,
            error='Field "name" is mandatory')
    # update the item
    item.name = name
    item.description = description
    item.image_url = image_url
    item.category = category
    db.session.add(item)
    db.session.commit()
    # show the updated item
    return showItem(id)


# OAuth handling - called when user has logged in
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # code from https://developers.google.com/+/web/signin/server-side-flow
    # Ensure that the request is not a forgery and that the user sending
    # this connect request is the expected user.
    if request.args.get('state', '') != getSyncToken():
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        print ("Invalid state parameter - expected %s, got %s\n"
               % (session['state'], request.args.get('state', '')))
        return response
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # check if user is already logged in
    stored_token = session.get('access_token')
    stored_gplus_id = session.get('gplus_id')
    gplus_id = result['user_id']
    if stored_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Store the access token in the session for later use.
    session['access_token'] = access_token
    session['gplus_id'] = gplus_id
    response = make_response(
        json.dumps('Successfully connected user.'), 200)
    response.headers['Content-Type'] = 'application/json'
    return response


# OAuth handling - called when user wants to logout
@app.route('/gdisconnect')
def gdisconnect():
    access_token = session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Currently not logged in'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # revoke current token
    url = ('https://accounts.google.com/o/oauth2/revoke?token=%s'
           % access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    # I do not chekc the status - either the token is revoked
    # successfully or the token is invalid - in both cases I forget
    # the user
    del session['access_token']
    del session['gplus_id']
    response = make_response(json.dumps('Successfully logged out'), 200)
    response.headers['Content-Type'] = 'application/json'
    return response


# when this script is called from the command line
# vs being imported as a module from some other module
if __name__ == '__main__':
    # check if db file exists - if not create it
    if not os.path.isfile('catalog.db'):
        with app.test_request_context():
            db.create_all()
    # set debugging
    app.debug = True
    # create key for session storage
    app.secret_key = getRandomString()
    # assign my json encoder
    app.json_encoder = MyJSONEncoder
    # add markdown filter
    Markdown(app)
    # start the Flask server on port 8080
    app.run(host='0.0.0.0', port=8080)
