from flask import Flask, Response, jsonify, session, render_template, request, redirect, url_for
import pyrebase
import json
import cv2
from keras.models import model_from_json
import uuid
import numpy as np
import os
import subprocess
import threading
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
    global name

    if 'user' not in session:
        logged_in = False
        user_email = None
        return redirect('/login')
    else:
        logged_in = True
        user_email = session['user']
        check = db.child("users").get()
        di = dict(check.val())
        name = get_name_by_email(user_email,di)
        print(name)

    if request.method == 'POST':
        # Retrieve the user's answers from the form submission

        answers = request.form

        # Calculate the score for each emotion category based on the user's answers
        
        happiness_score = calculate_score(answers, 'happiness')
        sadness_score = calculate_score(answers, 'sadness')
        fear_score = calculate_score(answers, 'fear')
        anger_score = calculate_score(answers, 'anger')


        # Determine the dominant emotion based on the scores
        
        dominant_emotion = determine_dominant_emotion(happiness_score, sadness_score, fear_score, anger_score)
        
        #data to send to Firebase
        quiz_data = {
            'happiness_score': happiness_score,
            'sadness_score': sadness_score,
            'fear_score': fear_score,
            'anger_score': anger_score,
        }
  

        db.child(name).child('quiz').child('data').set(quiz_data)
        db.child(name).child('quiz').child('demo').set(dominant_emotion)
        
            
        # Render the result page with the dominant emotion
        return render_template('results.html', dominant_emotion=dominant_emotion,logged_in=logged_in, user_email=user_email,happiness_score=happiness_score, 
                               sadness_score=sadness_score, 
                               fear_score=fear_score, 
                               anger_score=anger_score,)
    else:
        # Render the quiz HTML page
        # questions = load_quiz_questions()
        return render_template('quiz.html',logged_in=logged_in, user_email=user_email)

def calculate_score(answers, emotion):
    # Define the mapping of options to emotions
    option_to_emotion = {'A': 'happiness', 'B': 'sadness', 'C': 'fear', 'D': 'anger'}
    # Initialize the score for the specified emotion
    score = 0
    # Iterate through the user's answers
    for question_index, answer in answers.items():
        # Extract the selected option for the current question
        option = answer.strip()  # Remove any leading/trailing whitespace
        # Get the emotion corresponding to the selected option
        emotion_for_option = option_to_emotion.get(option)
        if emotion_for_option == emotion:
            score += 1  # Increment the score for the specified emotion
    return score

# Function dominant emotion based on the scores
def determine_dominant_emotion(happiness_score, sadness_score, fear_score, anger_score):
    #dictionary to store the scores for each emotion
    scores = {'happiness': happiness_score, 'sadness': sadness_score, 'fear': fear_score, 'anger': anger_score}
    
    #emotion with the highest score
    dominant_emotion = max(scores, key=scores.get)
    
    return dominant_emotion


# def load_quiz_questions():
#     with open('quiz_questions.json', 'r') as file:
#         quiz_data = json.load(file)
#     return quiz_data['questions']

#Initialize emotion counts
emotion_counts = {'angry': 0,'fear': 0, 'happy': 0, 'neutral': 0, 'sad': 0, 'surprise':0} 
session_id = str(uuid.uuid4())

def start_emotion_recognition():
    global emotion_counts, name
    
    # Load the pre-trained model architecture from JSON file
    json_file = open("./model/emotiondetector.json", "r")
    model_json = json_file.read()
    json_file.close()
    model = model_from_json(model_json)

    # Load the pre-trained model weights
    model.load_weights("./model/emotiondetector.h5")

    # Load the Haar cascade classifier for face detection
    haar_file = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(haar_file)

    # Define labels for emotion classes
    labels = {0: 'angry', 1: 'disgust', 2: 'fear', 3: 'happy', 4: 'neutral', 5: 'sad', 6: 'surprise'}

    # Define a function to extract features from an image
    def extract_features(image):
        feature = np.array(image)
        feature = feature.reshape(1, 48, 48, 1)
        return feature / 255.0

    # Open the webcam (camera)
    webcam = cv2.VideoCapture(0)

    while True:
        # Read a frame from the webcam
        i, im = webcam.read()

        # Convert the frame to grayscale
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)

        # Detect faces in the grayscale frame
        faces = face_cascade.detectMultiScale(im, 1.3, 5)

        try:
            # For each detected face, perform facial emotion recognition
            for (p, q, r, s) in faces:
                # Extract the region of interest (ROI) which contains the face
                image = gray[q:q + s, p:p + r]

                # Draw a rectangle around the detected face
                cv2.rectangle(im, (p, q), (p + r, q + s), (255, 0, 0), 2)

                # Resize the face image to the required input size (48x48)
                image = cv2.resize(image, (48, 48))

                # Extract features from the resized face image
                img = extract_features(image)

                # Make a prediction using the trained model
                pred = model.predict(img)

                # Get the predicted label for emotion
                prediction_label = labels[pred.argmax()]

                # Update the count of detected emotion
                emotion_counts[prediction_label] += 1

                # Display the predicted emotion label near the detected face
                cv2.putText(im, f'Emotion: {prediction_label}', (p - 10, q - 10),
                            cv2.FONT_HERSHEY_COMPLEX_SMALL, 2, (0, 0, 255))

            # Display the frame with annotations in real-time
            cv2.imshow("Real-time Facial Emotion Recognition", im)

            # Break the loop if the 'Esc' key is pressed
            if cv2.waitKey(1) == 27:
                break

        except cv2.error:
            pass

    # Release the webcam and close all OpenCV windows
    webcam.release()
    cv2.destroyAllWindows()

# Add a route to fetch the real-time emotion counts
@app.route('/fetch_emotion_counts')
def fetch_emotion_counts():
    global emotion_counts,name

    db.child(name).child('emotion').set(emotion_counts)
    db.child(name).child('cemotion').set(emotion_counts)
    return jsonify(emotion_counts)

@app.route('/start_game', methods=['POST'])
def start_game():
    global emotion_counts,name

    # Start the real-time facial emotion recognition in a separate thread
    threading.Thread(target=start_emotion_recognition).start()
    
    # Optionally, you can redirect the user to another page or render a template
    return redirect('/game_in_progress')

# Route to a page indicating that the game is in progress
@app.route('/game_in_progress')
def game_in_progress():
    global emotion_counts,name

    if 'user' in session:
        logged_in = True
        user_email = session['user']
    else:
        logged_in = False
        user_email = None
        return redirect('/login')
    return render_template('game.html', logged_in=logged_in, user_email=user_email)


@app.route('/fetch_emotion_counts_in_game')
def fetch_emotion_counts_in_game():
    global emotion_counts,name

    db.child(name).child('emotioningame').set(emotion_counts)
    db.child(name).child('cemotion').set(emotion_counts)
    return jsonify(emotion_counts)

@app.route('/inside_game')
def inside_game():
    global emotion_counts,name

    if 'user' in session:
        logged_in = True
        user_email = session['user']
    else:
        logged_in = False
        user_email = None
    return render_template('midgame.html', logged_in=logged_in, user_email=user_email)

@app.route('/fetch_emotion_counts_post_game')
def fetch_emotion_counts_post_game():
    global emotion_counts,name

    db.child(name).child('emotionpostgame').set(emotion_counts)
    db.child(name).child('cemotion').set(emotion_counts)
    return jsonify(emotion_counts)

@app.route('/post_game')
def post_game():
    global emotion_counts, name
    if 'user' in session:
        logged_in = True
        user_email = session['user']
    else:
        logged_in = False
        user_email = None
    return render_template('postgame.html', logged_in=logged_in, user_email=user_email)

@app.route('/start_gameplay', methods=['POST'])
def start_gameplay():
    try:
        subprocess.Popen(['game\Depression.exe']) #game path
        return 'Game started successfully', 200
    except Exception as e:
        return f'Error starting game: {str(e)}', 500
    
@app.route('/profile', methods=['GET'])
def profile():

    global name
    if 'user' not in session:
        logged_in = False
        user_email = None
        return redirect('/login')
    else:
        logged_in = True
        user_email = session['user']

    return render_template('profile.html',logged_in=logged_in, name = name, user_email=user_email)   

@app.route('/final_report',methods=['GET','POST'])
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
        print(dgraph_json1)

        emopre = db.child(name).child('emotion').get()
        dgraph2 = dict(emopre.val())
        dgraph_json2 = json.dumps(dgraph2)  
        print(dgraph_json2)

        inemo = db.child(name).child('emotioningame').get()
        dgraph3 = dict(inemo.val())
        dgraph_json3 = json.dumps(dgraph3)  
        print(dgraph_json3)

        emopost = db.child(name).child('emotionpostgame').get()
        dgraph4 = dict(emopost.val())
        dgraph_json4 = json.dumps(dgraph4)  
        print(dgraph_json4)


    return render_template('report.html', logged_in=logged_in, name = name, user_email=user_email,dgraph_json1=dgraph_json1,demo=demo,dgraph_json2=dgraph_json2,dgraph_json3=dgraph_json3,dgraph_json4=dgraph_json4)
 

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')