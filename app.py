import os
# import RPi.GPIO as GPIO
from flask import Flask, flash, render_template, redirect, request, Response, jsonify
from flask_socketio import SocketIO, emit
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import os
import base64
import numpy as np
import cv2
from datetime import datetime

load_dotenv()

# Constant
STATIC_FOLDER = 'static'
UPLOAD_FOLDER = "static/uploads/"
BUCKET = "ecoguard-chargebox"

# Flask & MySQL Setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['static_url_path'] = STATIC_FOLDER
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DB")
app.config['SECRET_KEY'] = "ecoguard-chargebox"
mysql = MySQL(app)
socketio = SocketIO(app, cors_allowed_origins='*')

# GPIO Pin Setup
# GPIO.setmode(GPIO.BCM)
# pins = {
#     8 : {
#          'name' : 'GPIO 8',
#         'state' : GPIO.LOW
#     },
#     23 : {
#        'name' : 'GPIO 23',
#        'state' : GPIO.LOW
#     },
#     24 : {
#         'name' : 'GPIO 24',
#         'state' : GPIO.LOW
#     },
#     25 : {
#         'name' : 'GPIO 25',
#         'state' : GPIO.LOW
#     },
# }

# for pin in pins:
#    GPIO.setup(pin, GPIO.OUT)
#    GPIO.output(pin, GPIO.LOW)

# ...
# Socket.IO
# ...

@socketio.on("connect")
def test_connect():
    print("Connected")
    emit("my response", {"data": "Connected"})

@socketio.on("image")
def receive_image(image):
    # Decode the base64-encoded image data
    image = base64_to_image(image)

    # Perform image processing using OpenCV
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    frame_resized = cv2.resize(gray, (640, 360))

    # Encode the processed image as a JPEG-encoded base64 string
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    result, frame_encoded = cv2.imencode(".jpg", frame_resized, encode_param)
    processed_img_data = base64.b64encode(frame_encoded).decode()

    # Prepend the base64-encoded string with the data URL prefix
    b64_src = "data:image/jpg;base64,"
    processed_img_data = b64_src + processed_img_data

    # Save the processed image to the uploads folder with datetime as filename
    # now = datetime.now()
    # filename = now.strftime("%Y%m%d%H%M%S") + ".jpg"
    # cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], filename), frame_resized)

    # Send the processed image back to the client
    emit("processed_image", processed_img_data)

# ...
# Function
# ...

def base64_to_image(base64_string):
    # Extract the base64 encoded binary data from the input string
    base64_data = base64_string.split(",")[1]
    # Decode the base64 data to bytes
    image_bytes = base64.b64decode(base64_data)
    # Convert the bytes to numpy array
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    # Decode the numpy array as an image using OpenCV
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    return image

# ...
# Routing
# ...

# Landing Page
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Back
@app.route('/back/<to>', methods=['GET'])
def back(to=None):
    if to == 'index':
        return redirect('/')

    elif to == 'menu':
        return redirect('/menu')

    elif to == 'locker':
        return redirect('/locker/keep')

    elif to == 'auth_pin':
        return redirect('/auth/pin/')

    elif to == 'auth_pin_confirm':
        return redirect('/auth/pin/confirm/')

    elif to == 'auth_iris':
        return redirect('/auth/iris/')

    elif to == 'waiting':
        return redirect('/waiting/')

    elif to == 'success':
        return redirect('/success/')

    else:
        return redirect('/menu')

# Menu Page
@app.route('/menu', methods=['GET'])
def menu():
    return render_template('menu.html')

# Home: Keep Device & Pick up Device
@app.route('/locker/<action>', methods=['GET'])
def locker(action=None):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers")
    lockers = cursor.fetchall()
    cursor.close()

    locker_list = []

    if action == 'keep':
        for row in lockers:
            status = ''
            anchor_status = True

            if row[3] == None:
                if row[2] == 'AVAILABLE':
                    status = 'Available'
                else:
                    status = 'In Use'
                    anchor_status = False

            else:
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT * FROM users WHERE id = %s", [row[3]])
                user = cursor.fetchone()
                cursor.close()

                if user[6] == 'PENDING':
                    status = 'Available'
                else:
                    status = 'In Use'
                    anchor_status = False

            locker_list.append({
                'id': row[0],
                'code': row[1],
                'status': status,
                'used_by': row[3],
                'created_at': row[4],
                'updated_at': row[5],
                'anchor_status': anchor_status
            })

        return render_template('locker-list.html', locker_list=locker_list)
    
    elif action == 'pickup':
        for row in lockers:
            status = ''
            anchor_status = True
            if row[3] == None:
                status = 'Empty'
                anchor_status = False

            else:
                if row[2] == 'AVAILABLE':
                    status = 'Empty'
                    anchor_status = False
                else:
                    cursor = mysql.connection.cursor()
                    cursor.execute("SELECT * FROM users WHERE id = %s", [row[3]])
                    user = cursor.fetchone()
                    cursor.close()

                    if user[6] == 'PENDING':
                        status = 'Empty'
                        anchor_status = False
                    else:
                        status = 'Ready'

            locker_list.append({
                'id': row[0],
                'code': row[1],
                'status': status,
                'used_by': row[3],
                'created_at': row[4],
                'updated_at': row[5],
                'anchor_status': anchor_status
            })
            
        return render_template('locker-list.html', locker_list=locker_list)
    
    return redirect('/menu')

# Pin Input: Keep Device & Pick up Device
@app.route('/auth/pin/<locker_code>', methods=['GET'])
def auth_pin(locker_code=None):
    # get locker list
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers")
    lockers = cursor.fetchall()

    # get locker detail
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    cursor.close()

    # TODO: Check if Locker in Use or Not, Then Redirect to Locker List
    
    locker_list_code = []
    for row in lockers:
        locker_list_code.append(row[1])

    # define anchor can be clicked or not
    anchor_status = True
    if row[3] == None:
        if row[2] == 'AVAILABLE':
            status = 'Available'
        else:
            status = 'In Use'
            anchor_status = False

    else:
        if row[2] == 'AVAILABLE':
            status = 'Empty'
            anchor_status = False
        else:
            status = 'Ready'

    locker_detail = {
        'id': locker[0],
        'code': locker[1],
        'status': status,
        'used_by': locker[3],
        'created_at': locker[4],
        'updated_at': locker[5],
        'anchor_status': anchor_status
    }

    if any(substring in locker_code for substring in locker_list_code):
        return render_template('auth-pin.html', locker_detail=locker_detail)
    
    else:
        return redirect('/menu')

# Pin Input (Validation): Keep Device & Pick up Device
@app.route('/auth/pin/<locker_code>/validate', methods=['POST'])
def auth_pin_validate(locker_code=None):
    if not request.form.get('pin_full'):
        return redirect('/auth/pin/' + locker_code)
    
    if request.form.get('pin_full').find('*') != -1:
        return redirect('/auth/pin/' + locker_code)
    
    # get locker detail
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    cursor.close()

    if locker[3] != None:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", [locker[3]])
        user = cursor.fetchone()
        cursor.close()

        if user[6] == 'PENDING':
            cursor = mysql.connection.cursor()
            cursor.execute("INSERT INTO users (pin, total_fail_pin, total_fail_iris, status) VALUES (%s, %s, %s, %s)", (request.form.get('pin_full'), 0, 0, 'PENDING'))
            mysql.connection.commit() 
            new_user_id = cursor.lastrowid
            cursor.execute("UPDATE lockers SET status = %s, used_by = %s WHERE code = %s", ('INUSE', new_user_id, locker_code))
            mysql.connection.commit()
            cursor.close()

            return redirect('/auth/pin/confirm/' + locker_code)
        
        if user[4] > 5:
            # return with error fail more than 5 times
            return redirect('/auth/pin/' + locker_code)

        if user[1] == request.form.get('pin_full'):
            return redirect('/auth/iris/' + locker_code)
        
        else:
            cursor = mysql.connection.cursor()
            cursor.execute("UPDATE users SET total_fail_pin = %s WHERE id = %s", (user[4] + 1, user[0]))
            mysql.connection.commit()
            cursor.close()
            return redirect('/auth/pin/' + locker_code)

    # insert new data
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO users (pin, total_fail_pin, total_fail_iris, status) VALUES (%s, %s, %s, %s)", (request.form.get('pin_full'), 0, 0, 'PENDING'))
    mysql.connection.commit() 
    new_user_id = cursor.lastrowid
    cursor.execute("UPDATE lockers SET status = %s, used_by = %s WHERE code = %s", ('INUSE', new_user_id, locker_code))
    mysql.connection.commit()
    cursor.close()

    return redirect('/auth/pin/confirm/' + locker_code)

# Confirm Pin Input: Keep Device & Pick up Device
@app.route('/auth/pin/confirm/<locker_code>', methods=['GET'])
def auth_pin_confirm(locker_code=None):
    # get locker list
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers")
    lockers = cursor.fetchall()

    # get locker detail
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    cursor.close()

    # TODO: check if locker in use or not
    
    locker_list_code = []
    for row in lockers:
        locker_list_code.append(row[1])

    # define anchor can be clicked or not
    anchor_status = True
    if row[3] == None:
        if row[2] == 'AVAILABLE':
            status = 'Available'
        else:
            status = 'In Use'
            anchor_status = False

    else:
        if row[2] == 'AVAILABLE':
            status = 'Empty'
            anchor_status = False
        else:
            status = 'Ready'

    locker_detail = {
        'id': locker[0],
        'code': locker[1],
        'status': status,
        'used_by': locker[3],
        'created_at': locker[4],
        'updated_at': locker[5],
        'anchor_status': anchor_status
    }

    if any(substring in locker_code for substring in locker_list_code):
        return render_template('auth-pin-confirm.html', locker_detail=locker_detail)
    
    return redirect('/menu')
    
# Confirm Pin Input (Validation): Keep Device & Pick up Device
@app.route('/auth/pin/confirm/<locker_code>/validate', methods=['POST'])
def auth_pin_confirm_validate(locker_code=None):
    if not request.form.get('pin_full'):
        return redirect('/auth/pin/confirm/' + locker_code)
    
    if request.form.get('pin_full').find('*') != -1:
        return redirect('/auth/pin/confirm/' + locker_code)
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    cursor.close()

    if locker[3] != None:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", [locker[3]])
        user = cursor.fetchone()
        cursor.close()

        if user[1] == request.form.get('pin_full'):
            return redirect('/auth/iris/' + locker_code)
        
        else:
            flash(u'Pin is not match', 'error')
            return redirect('/auth/pin/confirm/' + locker_code)

    return redirect('/auth/pin/confirm/' + locker_code)

# Iris Scan: Keep Device & Pick up Device
@app.route('/auth/iris/<locker_code>', methods=['GET'])
def auth_iris(locker_code=None):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers")
    lockers = cursor.fetchall()

    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    cursor.close()

    # TODO: check if Locker in Use or Not, Then Redirect to Locker List
    
    locker_list_code = []
    for row in lockers:
        locker_list_code.append(row[1])

    # define anchor can be clicked or not
    anchor_status = True
    if row[3] == None:
        if row[2] == 'AVAILABLE':
            status = 'Available'
        else:
            status = 'In Use'
            anchor_status = False

    else:
        if row[2] == 'AVAILABLE':
            status = 'Empty'
            anchor_status = False
        else:
            status = 'Ready'

    locker_detail = {
        'id': locker[0],
        'code': locker[1],
        'status': status,
        'used_by': locker[3],
        'created_at': locker[4],
        'updated_at': locker[5],
        'anchor_status': anchor_status
    }

    if any(substring in locker_code for substring in locker_list_code):
        return render_template('auth-iris.html', locker_detail=locker_detail)
    
    return redirect('/menu')
    
# Iris Scan (Validation): Keep Device & Pick up Device
# @app.route('/auth/iris/<locker_code>/validate', methods=['POST'])
# def auth_iris_validate(locker_code=None):
#     if not request.form.get('iris_full'):
#         return redirect('/auth/iris/' + locker_code)
    
#     # get locker detail
#     cursor = mysql.connection.cursor()
#     cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
#     locker = cursor.fetchone()
#     cursor.close()

#     # if locker in use
#     if locker[3] != None:
#         cursor = mysql.connection.cursor()
#         cursor.execute("SELECT * FROM users WHERE id = %s", [locker[3]])
#         user = cursor.fetchone()
#         cursor.close()

#         # check if user iris fail more than 5 times
#         if user[5] > 5:
#             # return error message
#             return redirect('/auth/iris/' + locker_code)
        
#         # TODO: process iris input -> iris image to iris template (encoding)

#         # TODO: process upload iris image and iris template to cloud storage (AWS S3)

#         # TODO: check if iris scan match with template or not
#         processed_iris_input = ""
#         if user[3] == processed_iris_input:
#             return redirect('/waiting/' + locker_code)
        
#         else:
#             cursor = mysql.connection.cursor()
#             cursor.execute("UPDATE users SET total_fail_iris = %s WHERE id = %s", (user[3] + 1, user[0]))
#             mysql.connection.commit()
#             cursor.close()
#             return redirect('/auth/iris/' + locker_code)

#     return redirect('/auth/iris/' + locker_code)

# Get Current Locker State
@app.route('/locker/<locker_code>/state', methods=['GET'])
def locker_state(locker_code=None):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    cursor.close()

    data = {
        'id': locker[0],
        'code': locker[1],
        'status': "",
    }

    if locker[3] == None:
        data['status'] = 'NO_STEP'
    else:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", [locker[3]])
        user = cursor.fetchone()
        cursor.close()

        if user[6] == 'PENDING':
            data['status'] = 'STEP_PIN'
        else:
            data['status'] = 'STEP_IRIS'

    return jsonify(data)

# Waiting: Keep Device & Pick up Device
@app.route('/waiting/<action>', methods=['GET'])
def waiting(action=None):
    return render_template('waiting.html')

# Success: Keep Device & Pick up Device
@app.route('/success/<action>', methods=['GET'])
def success(action=None):
    return render_template('success.html')

if __name__ == '__main__':
    app.run(debug=True)