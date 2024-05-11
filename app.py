from flask import Flask, Response, jsonify, session, render_template, request, redirect, url_for
import pyrebase
import json
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

config = {
    'apiKey': os.environ.get("FIREBASE_API_KEY"),
    'authDomain': os.environ.get("FIREBASE_AUTH_DOMAIN"),
    'projectId': os.environ.get("FIREBASE_PROJECT_ID"),
    'storageBucket': os.environ.get("FIREBASE_STORAGE_BUCKET"),
    'messagingSenderId': os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
    'appId': os.environ.get("FIREBASE_APP_ID"),
    'databaseURL': os.environ.get("FIREBASE_DATABASE_URL"),

  }

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()
app.secret_key = 'secret'
name = ''
username = ''

@app.route('/', methods=['GET'])
def index():
    if 'user' in session:
        logged_in = True
        user_email = session['user']
    else:
        logged_in = False
        user_email = None
    return render_template('index.html', logged_in=logged_in, user_email=user_email)

@app.route('/signup', methods=['POST', 'GET'])
def signup():
    global name
    if 'user' in session:
        return redirect('/')  # Redirect to homepage if user is already logged in
    if request.method == 'POST':
        name =  request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        db.child('users').child(name).set(email)

        try:
            # Create user with email and password
            user = auth.create_user_with_email_and_password(email, password)
            session['user'] = email
            return redirect('/')  # Redirect to homepage after successful signup
        except:
            return 'Failed to signup'  # Display error message if signup fails
    return render_template('signup.html')

@app.route('/login', methods=['POST', 'GET'])
def login():

    global name
    if 'user' in session:
        return redirect('/')  # Redirect to homepage if user is already logged in
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            # Authenticate user with email and password
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = email
            check = db.child("users").get()
            di = dict(check.val())
            name = get_name_by_email(email,di)
            print(name)
            return redirect('/')  # Redirect to homepage after successful login
        except:
            return 'Failed to login'  # Display error message if login fails
    return render_template('login.html')

def get_name_by_email(email,di):
    for name, email_address in di.items():
        if email_address == email:
            return name
    return None


@app.route('/logout')
def logout():
    session.pop('user')
    return redirect('/')

# Define the route for the quiz
@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    global username

    if 'user' not in session:
        logged_in = False
        user_email = None
        return redirect('/login')
    else:
        logged_in = True
        user_email = session['user']
        check = db.child("users").get()
        dd_users = dict(check.val())
        username = get_name_by_email(user_email,dd_users)
        # print(username)


        return render_template('quiz.html',logged_in=logged_in, user_email=user_email, dd_users=dd_users)


# Route to a page indicating that the game is in progress
@app.route('/game_in_progress', methods=['GET', 'POST'])
def game_in_progress():
    global name

    if 'user' in session:
        logged_in = True
        user_email = session['user']

        name = request.form.get('selected_user')

        cemo = db.child(name).child('cemotion').get()
        dgraph = dict(cemo.val())
        dgraph_json = json.dumps(dgraph)  
        # print(dgraph_json)
        
    else:
        logged_in = False
        user_email = None
        return redirect('/login')
    return render_template('game.html', logged_in=logged_in, user_email=user_email,dgraph_json=dgraph_json)

    
@app.route('/profile', methods=['GET'])
def profile():

    global username
    if 'user' not in session:
        logged_in = False
        user_email = None
        return redirect('/login')
    else:
        logged_in = True
        user_email = session['user']

    return render_template('profile.html',logged_in=logged_in, username = username, user_email=user_email)   

@app.route('/final_report', methods=['GET','POST'])
def final_report():

    global name
    if 'user' not in session:
        logged_in = False
        user_email = None
        return redirect('/login')
    else:
        logged_in = True
        user_email = session['user']
        demo = db.child(name).child('quiz').child('demo').get().val()
        quiz = db.child(name).child('quiz').child('data').get()
        dgraph1 = dict(quiz.val())
        dgraph_json1 = json.dumps(dgraph1)  
        # print(dgraph_json1)

        emopre = db.child(name).child('emotion').get()
        dgraph2 = dict(emopre.val())
        dgraph_json2 = json.dumps(dgraph2)  
        # print(dgraph_json2)

        inemo = db.child(name).child('emotioningame').get()
        dgraph3 = dict(inemo.val())
        dgraph_json3 = json.dumps(dgraph3)  
        # print(dgraph_json3)

        emopost = db.child(name).child('emotionpostgame').get()
        dgraph4 = dict(emopost.val())
        dgraph_json4 = json.dumps(dgraph4)  
        # print(dgraph_json4)


    return render_template('report.html', logged_in=logged_in, name = name, user_email=user_email,dgraph_json1=dgraph_json1,demo=demo,dgraph_json2=dgraph_json2,dgraph_json3=dgraph_json3,dgraph_json4=dgraph_json4)
 

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')