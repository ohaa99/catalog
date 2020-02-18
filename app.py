from flask import Flask, render_template, request, redirect,jsonify, url_for, flash
from flask import session as login_session
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests



app = Flask(__name__)

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Center, Programm, User

#Connect to Database and create database session
engine = create_engine('sqlite:///trainingCentersGuide.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()
#configure login providers
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                for x in range(32))
    login_session['state'] = state
    return render_template('login.html',STATE=state)

@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print ("access token received %s ") % access_token


    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v4.0/me"
    token = result.split(',')[0].split(':')[1].replace('"', '')

    url = 'https://graph.facebook.com/v4.0/me?access_token=%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"] 
    login_session['access_token'] = token

    # Get user picture
    url = 'https://graph.facebook.com/v2.8/me/picture?access_token=%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("You logged in as %s" % login_session['username'])
    return output


@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id,access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "You have been logged out."

@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showCenters'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showCenters'))



def createUser(login_session):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

#Show all Centers
@app.route('/')
@app.route('/centers/')
def showCenters():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    centers = session.query(Center).order_by(asc(Center.name))
    if 'username' not in login_session:
        return render_template('publiccenters.html', centers = centers)
    else:
        return render_template('centers.html', centers = centers)

#Create a training Center
@app.route('/centers/new/', methods=['GET','POST'])
def newCenter():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newCenter = Center(name = request.form['name'],address = request.form['address'],
                           description = request.form['about'] ,fields = request.form['fields'] ,
                           user_id=login_session['user_id'])
        session.add(newCenter)
        flash('New Center %s Successfully Created' % newCenter.name)
        session.commit()
        return redirect(url_for('showCenters'))
    else:
        return render_template('newcenter.html')

#Edit a training Center
@app.route('/center/<int:center_id>/edit/', methods = ['GET', 'POST'])
def editCenter(center_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    editedCenter = session.query(
        Center).filter_by(id=center_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if editedCenter.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized to edit this CENTER.\
             Please create your own in order to edit.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedCenter.name = request.form['name']
        if request.form['fields']:
            editedCenter.fields = request.form['fields']
        if request.form['about']:
            editedCenter.description = request.form['about']
        if request.form['address']:
            editedCenter.address = request.form['address']
        session.add(editedCenter)
        session.commit()
        flash('The Center Successfully Edited %s' % editedCenter.name)
        return redirect(url_for('showCenters'))
    else:
        return render_template('editcenter.html', center=editedCenter)

# Delete a training Center
@app.route('/center/<int:center_id>/delete/', methods=['GET', 'POST'])
def deleteCenter(center_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    centerToDelete = session.query(
        Center).filter_by(id=center_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if centerToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized to delete this center.\
             Please create your own  in order to delete.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(centerToDelete)
        flash('%s Successfully Deleted' % centerToDelete.name)
        session.commit()
        return redirect(url_for('showCenters', center_id=center_id))
    else:
        return render_template('deletecenter.html', center=centerToDelete)


#Show a Programm 
@app.route('/centers/<int:center_id>/')
@app.route('/centers/<int:center_id>/programm/')
def showProgramm(center_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    center = session.query(Center).filter_by(id=center_id).one()
    creator = getUserInfo(Center.user_id)
    programms = session.query(Programm).filter_by(
        center_id=center_id).all()
    if 'username' not in login_session or creator.id != login_session['user_id']:
        return render_template('publicprogramm.html', programms=programms, center=center, creator=creator)
    else:
        return render_template('programm.html', programms=programms, center=center, creator=creator)
        
        


#Create a new programm
@app.route('/centers/<int:center_id>/programm/new/',methods=['GET','POST'])
def newProgramm(center_id):
    if 'username' not in login_session:
        return redirect('/login')
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    center = session.query(Center).filter_by(id = center_id).one()
    if request.method == 'POST':
        newProgramm = Programm(name = request.form['name'], description = request.form['description'],
         price = request.form['price'],duration = request.form['duration'],
         pType = request.form['pType'],
         center_id = center_id,  user_id=center.user_id)
        session.add(newProgramm)
        session.commit()
        flash(' %s  Successfully Created' % (newProgramm.name))
        return redirect(url_for('showProgramm', center_id = center_id))
    else:
        return render_template('newprogramm.html', center_id = center_id)
        
#Edit a programm
@app.route('/centers/<int:center_id>/programm/<int:programm_id>/edit', methods=['GET','POST'])
def editProgramm(center_id, programm_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    if 'username' not in login_session:
        return redirect('/login')
    editedProgramm = session.query(Programm).filter_by(id=programm_id).one()
    center = session.query(Center).filter_by(id=center_id).one()
    if login_session['user_id'] != center.user_id:
        return "<script>function myFunction() {alert('You are not authorized to edit the programms of this center.\
             Please create your own programm in order to edit items.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedProgramm.name = request.form['name']
        if request.form['description']:
            editedProgramm.description = request.form['description']
        if request.form['price']:
            editedProgramm.price = request.form['price']
        if request.form['duration']:
            editedProgramm.duration = request.form['duration']
        if request.form['pType']:
            editedProgramm.pType = request.form['pType']
        session.add(editedProgramm)
        session.commit()
        flash('This programm has  Successfully Edited')
        return redirect(url_for('showProgramm', center_id=center_id))
    else:
        return render_template('editprogramm.html', center_id=center_id, programm_id=programm_id, programm=editedProgramm)


# Delete a Programm
@app.route('/centers/<int:center_id>/programm/<int:programm_id>/delete', methods=['GET','POST'])
def deleteProgramm(center_id, programm_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    if 'username' not in login_session:
        return redirect('/login')
    center = session.query(Center).filter_by(id=center_id).one()
    programmToDelete = session.query(Programm).filter_by(id=programm_id).one()
    if login_session['user_id'] != center.user_id:
        return "<script>function myFunction() {alert('You are not authorized to delete the programms of this center.\
             Please create your own programm in order to edit items.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(programmToDelete)
        session.commit()
        flash('The programm has Successfully Deleted')
        return redirect(url_for('showProgramm', center_id=center.id))
    else:
        return render_template('deleteprogramm.html', programm=programmToDelete)

  #JSON APIs to view a training center Information
@app.route('/centers/<int:center_id>/programm/JSON')
def centerJSON(center_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    center = session.query(Center).filter_by(id = center_id).one()
    programms = session.query(Programm).filter_by(center_id = center_id).all()
    return jsonify(Programms=[i.serialize for i in programms])


@app.route('/centers/<int:center_id>/programm/<int:programm_id>/JSON')
def programmJSON(center_id, programm_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    theProgramm = session.query(Programm).filter_by(id = programm_id).one()
    return jsonify(Programm = theProgramm.serialize)

@app.route('/centers/JSON')
def centersJSON():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    centers = session.query(Center).all()
    return jsonify(centers= [r.serialize for r in centers])

if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host = '0.0.0.0', port = 5000)


    