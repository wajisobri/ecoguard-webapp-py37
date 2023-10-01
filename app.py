import os
import RPi.GPIO as GPIO
from flask import Flask, flash, render_template, redirect, request, Response, jsonify, url_for, stream_with_context, current_app
from flask_mysqldb import MySQL
from dotenv import load_dotenv
from picamerax import PiCamera
from picamerax.array import PiRGBArray
import imutils
import os
import base64
import numpy as np
import cv2
import time
from datetime import datetime
from modules.extractFeature import extractFeature
from scipy.io import savemat

load_dotenv()

# Constant
STATIC_FOLDER = 'static'
UPLOAD_FOLDER = "static/uploads/"
BUCKET = "ecoguard-chargebox"

# Global
outputFrame = None
streamActive = False

# Flask & MySQL Setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['static_url_path'] = STATIC_FOLDER
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASS")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DB")
app.config['SECRET_KEY'] = "ecoguard-chargebox"
app.config['SERVER_NAME'] = '127.0.0.1:5000'

mysql = MySQL(app)

# GPIO Pin Setup
GPIO.setmode(GPIO.BCM)
pins = {
    27 : {
        'name' : 'GPIO 27',
        'state' : GPIO.LOW
    },
    22 : {
        'name' : 'GPIO 22',
        'state' : GPIO.LOW
    },
    23 : {
        'name' : 'GPIO 23',
        'state' : GPIO.LOW
    },
    24 : {
        'name' : 'GPIO 24',
        'state' : GPIO.LOW
    },
}

for pin in pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# ...
# Function
# ...

def toggle_pin(pin, action):
    if action == 'on':
        GPIO.output(pin, GPIO.HIGH)
        pins[pin]['state'] = GPIO.HIGH
    else:
        GPIO.output(pin, GPIO.LOW)
        pins[pin]['state'] = GPIO.LOW

def base64_to_image(base64_string):
    base64_data = base64_string.split(",")[1]
    image_bytes = base64.b64decode(base64_data)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    return image

def enroll_iris(locker_code, frame):
    print("Start enrolling iris ...")
    
    # Save image to local storage
    timestamp = datetime.now()
    filename = "image_" + timestamp.strftime("%Y%m%d%H%M%S") + ".jpg"
    cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], filename), frame)

    # Update Database
    with app.app_context():
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
        locker = cursor.fetchone()

        cursor.execute("SELECT * FROM users WHERE id = %s", [locker[4]])
        user = cursor.fetchone()

        if user != None:
            # Extract feature
            template, mask, file = extractFeature(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Save extracted feature
            basename = os.path.basename(file)
            out_file = os.path.join(app.config['UPLOAD_FOLDER'], "template_%s.mat" % (basename))
            savemat(out_file, mdict={'template':template, 'mask':mask})

            # TODO: Upload to AWS S3
            
            cursor.execute("UPDATE users SET iris_image = %s, iris_template = %s, status = %s WHERE id = %s", (filename, out_file, 'ACTIVE', user[0]))
            mysql.connection.commit()
            cursor.close()
            print("End enrolling iris [success]...")
            return True
        
        else:
            cursor.close()
            print("End enrolling iris [error]...")
            return False

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

def update_locker_status(code=None):
    print("Start updating locker status ...")
    with app.app_context():
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM lockers WHERE code = %s", [code])
        locker = cursor.fetchone()

        cursor.execute("UPDATE users SET status = %s WHERE id = %s", ('ACTIVE', locker[4]))
        mysql.connection.commit()
        cursor.close()
        
        print("End updating locker status ...")
        return True

# ...
# Routing
# ...

@app.route('/toggle-on/<gpio>', methods=['GET'])
def toggle_on(gpio=None):
    toggle_pin(int(gpio), 'on')
    return "ON"
    
@app.route('/toggle-off/<gpio>', methods=['GET'])
def toggle_off(gpio=None):
    toggle_pin(int(gpio), 'off')
    return "OFF"

# Video Feed
@app.route('/video_feed/<locker_code>', methods=['GET'])
def video_feed(locker_code=None):
    def stream_camera(locker_code=None):
        global outputFrame
        
        # ~ camera = cv2.VideoCapture(0)
        # ~ camera.set(cv2.CAP_PROP_FRAME_WIDTH,1920)
        # ~ camera.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
        # ~ camera.set(cv2.CAP_PROP_FPS, 10)
        camera = PiCamera()
        camera.resolution = (1920, 1080)
        camera.framerate = 30
        camera.awb_mode = 'greyworld'
        rawCapture = PiRGBArray(camera, size=(1920, 1080))
        
        time.sleep(0.1)
        
        i = 0
        for rawFrame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
            print("Read Camera Frame " + str(i))
            # ~ ret, frame = camera.read()
            frame = rawFrame.array
            
            time.sleep(0.1)
            # ~ gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # ~ gray = cv2.GaussianBlur(gray, (7, 7), 0)
            
            h, w = frame.shape[:-1]
            center_x, center_y = w // 2, h // 2
            zoom_factor = 1.5
            roi_width, roi_height = int(w / zoom_factor), int(h / zoom_factor)
            roi_x = center_x - roi_width // 2
            roi_y = center_y - roi_height // 2
            roi = frame[roi_y:roi_y + roi_height, roi_x:roi_x + roi_width]
            
            timestamp = datetime.now()
            # ~ cv2.putText(frame, timestamp.strftime("%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
            
            # filename = timestamp.strftime("%Y%m%d%H%M%S") + ".jpg"
            # cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], filename), gray)
                
            (flag, encodedImage) = cv2.imencode(".jpg", roi)
            
            i += 1
            rawCapture.truncate()
            rawCapture.seek(0)
            
            if not flag:
                continue
            
            yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
            
            if i == 29:
                outputFrame = roi.copy()
                break;

        # bypass authentication after 30 frame
        camera.close() 
        enroll = enroll_iris(locker_code, outputFrame)
        enroll = True
        
        if enroll == True:
            update_locker_status(locker_code)
    
    return Response(stream_with_context(stream_camera(locker_code)), mimetype = "multipart/x-mixed-replace; boundary=frame")

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

            # locker.used_by is null
            if row[4] == None:
                # locker.status is available or waiting
                if row[2] == 'AVAILABLE' or row[2] == 'WAITING':
                    status = 'Available'

                # locker.status is inuse
                else:
                    status = 'In Use'
                    anchor_status = False

            # locker.used_by is not null
            else:
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT * FROM users WHERE id = %s", [row[4]])
                user = cursor.fetchone()
                cursor.close()

                # user is not found
                if user == None:
                    status = 'Available'

                # user is found
                else:      
                    # user.status is pending or inactive
                    if user[6] == 'PENDING' or user[6] == 'INACTIVE':
                        status = 'Available'

                    # user.status is active
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

            # locker.used_by is null
            if row[4] == None:
                status = 'Empty'
                anchor_status = False

            # locker.used_by is not null
            else:
                # locker.status is available or waiting
                if row[2] == 'AVAILABLE' or row[2] == 'WAITING':
                    status = 'Empty'
                    anchor_status = False

                # locker.status is inuse
                else:
                    cursor = mysql.connection.cursor()
                    cursor.execute("SELECT * FROM users WHERE id = %s", [row[4]])
                    user = cursor.fetchone()
                    cursor.close()

                    # user is not found
                    if user == None:
                        status = 'Empty'
                        anchor_status = False

                    # user is found
                    else:
                        # user.status is pending
                        if user[6] == 'PENDING':
                            status = 'Empty'
                            anchor_status = False
                        
                        # user.status is active or inactive
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

    # locker.used_by is null
    if row[4] == None:
        # locker.status is available or waiting
        if row[2] == 'AVAILABLE' or row[2] == 'WAITING':
            status = 'Available'

        # locker.status is inuse
        else:
            status = 'In Use'
            anchor_status = False

    # locker.used_by is not null
    else:
        # locker.status is available or waiting
        if row[2] == 'AVAILABLE' or row[2] == 'WAITING':
            status = 'Empty'
            anchor_status = False
        
        # locker.status is inuse
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
    # check if pin input is empty or not
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

        if user != None:
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
    cursor.execute("INSERT INTO users (pin, total_fail_pin, total_fail_iris, status) VALUES (%s, %s, %s, %s)", (request.form.get('pin_full'), 0, 0, 'INACTIVE'))
    mysql.connection.commit() 
    new_user_id = cursor.lastrowid
    cursor.execute("UPDATE lockers SET status = %s, used_by = %s WHERE code = %s", ('WAITING', new_user_id, locker_code))
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

    if locker[4] != None:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", [locker[4]])
        user = cursor.fetchone()
        cursor.close()
        
        if user == None:
            print("User not found")
            
        print(user[1])
        print(request.form.get('pin_full'));

        if user[1] == request.form.get('pin_full'):
            # update user status
            cursor = mysql.connection.cursor()
            cursor.execute("UPDATE users SET status = %s WHERE id = %s", ('PENDING', user[0]))
            mysql.connection.commit()

            # insert auth logs
            cursor.execute("INSERT INTO auth_logs (user_id, locker_id, auth_type, action, status) VALUES (%s, %s, %s, %s, %s)", (user[0], locker[0], 'PIN', 'KEEP', 'VALID'))
            mysql.connection.commit()
            cursor.close()

            return redirect('/auth/iris/' + locker_code)
        
        else:
            cursor = mysql.connection.cursor()
            # insert auth logs
            cursor.execute("INSERT INTO auth_logs (user_id, locker_id, auth_type, action, status) VALUES (%s, %s, %s, %s, %s)", (user[0], locker[0], 'PIN', 'KEEP', 'INVALID'))
            mysql.connection.commit()
            cursor.close()

            flash(u'Pin is not match', 'error')
            return redirect('/auth/pin/confirm/' + locker_code)

    flash(u'Locker is in use', 'error')
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
    
@app.route('/auth/iris/<locker_code>/validate', methods=['POST'])
def auth_iris_validate(locker_code=None):
    return redirect(url_for('auth_iris_confirm', locker_code=locker_code))

@app.route('/auth/iris/confirm/<locker_code>', methods=['GET'])
def auth_iris_confirm(locker_code=None):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()

    cursor.execute("SELECT * FROM users WHERE id = %s", [locker[4]])
    user = cursor.fetchone()

    cursor.close()

    locker_detail = {
        'id': locker[0],
        'code': locker[1],
        'status': locker[2],
        'used_by': locker[3],
        'created_at': locker[4],
        'updated_at': locker[5],
        'anchor_status': locker[6]
    }

    user_detail = {
        'id': user[0],
        'pin': user[1],
        'iris_image': user[2],
        'iris_template': user[3],
        'total_fail_pin': user[4],
        'total_fail_iris': user[5],
        'status': user[6],
        'created_at': user[7],
        'updated_at': user[8]
    }

    if user[2] == None:
        user_detail['iris_image'] = ''

    if user[3] == None:
        user_detail['iris_template'] = ''

    return render_template('auth-iris-confirm.html', locker_detail=locker_detail, user_detail=user_detail)
    
# Iris Scan (Validation): Keep Device & Pick up Device
@app.route('/auth/iris/confirm/<locker_code>/validate', methods=['POST'])
def auth_iris_confirm_validate(locker_code=None):
    if not request.form.get('auth_action'):
        return redirect('/auth/iris/confirm/' + locker_code)

    if request.form.get('auth_action') == "re-capture":
        return redirect('/auth/iris/' + locker_code)
        
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    
    # TODO: Open Lock of Locker using GPIO
    GPIO.output(locker[5], GPIO.HIGH)

    # TODO: Redirect to Waiting Page
    # ~ url_for('waiting', action='keep', locker_code=locker_code)
    return redirect('/waiting/keep/' + locker_code)

# Waiting: Keep Device & Pick up Device
@app.route('/waiting/<locker_action>/<locker_code>', methods=['GET'])
def waiting(locker_action='keep', locker_code=None):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    cursor.close()

    locker_detail = {
        'id': locker[0],
        'code': locker[1],
        'status': locker[2],
        'used_by': locker[3],
        'created_at': locker[4],
        'updated_at': locker[5],
        'anchor_status': locker[6]
    }
    
    message = ''
    if locker_action == 'keep':
        message = 'Locker ' + locker_code + ' is now unlocked, please keep your device as soon as possible'
    else:
        message = 'Locker ' + locker_code + ' is now unlocked, please pick up your device as soon as possible'

    return render_template('waiting.html', message=message, locker_action=locker_action, locker_detail=locker_detail)

@app.route('/waiting/<action>/<locker_code>/validate', methods=['POST'])
def waiting_validate(action=None, locker_code=None):
    if not request.form.get('confirm_action'):
        return redirect('/waiting/' + action + '/' + locker_code)

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM lockers WHERE code = %s", [locker_code])
    locker = cursor.fetchone()
    cursor.close()

    if request.form.get('confirm_action') == "cancel":
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", [locker[4]])
        user = cursor.fetchone()
        cursor.close()
        
        # TODO: Set user to inactive
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET status = %s WHERE id = %s", ('INACTIVE', user[0]))
        mysql.connection.commit()
        
        # TODO: Set locker status to available, used_by to empty
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE lockers SET status = %s WHERE code = %s", ('AVAILABLE', locker_code))
        mysql.connection.commit()
        cursor.close()
        
        return redirect('/auth/iris/' + locker_code)
    
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE lockers SET status = %s WHERE code = %s", ('INUSE', locker_code))
    mysql.connection.commit()
    cursor.close()
    
    # TODO: Close Lock of Locker using GPIO
    GPIO.output(locker[5], GPIO.LOW)

    # TODO: Redirect to Success Page
    return redirect('/success/' + action + "/" + locker_code)

# Success: Keep Device & Pick up Device
@app.route('/success/<action>/<locker_code>', methods=['GET'])
def success(action=None, locker_code=None):
    message = ''
    if action == 'keep':
        message = 'Locker ' + locker_code + ' is now locked, your device is safe now'
    else:
        message = 'Thanks for using our service, please come again'

    return render_template('success.html', message=message)

if __name__ == '__main__':
    app.run(debug=True)
