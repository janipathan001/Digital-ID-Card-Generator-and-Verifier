import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
import qrcode
import base64
from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # For session management

# MongoDB Atlas connection
MONGO_URI = 'mongodb+srv://gnana:Gnana1313@database.ryxtcce.mongodb.net/?retryWrites=true&w=majority&appName=Database'
client = MongoClient(MONGO_URI)
db = client['digital_id']
students_col = db['students']
id_cards_col = db['id_cards']

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        rollno = request.form['rollno']
        name = request.form['name']
        class_section = request.form['class']
        branch = request.form['branch']
        password = request.form['password']
        # Check if user already exists
        if students_col.find_one({'rollno': rollno}):
            flash('Roll No already registered. Please login.', 'error')
            return redirect(url_for('signup'))
        students_col.insert_one({
            'rollno': rollno,
            'name': name,
            'class': class_section,
            'branch': branch,
            'password': password
        })
        flash('Signup successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        rollno = request.form['rollno']
        password = request.form['password']
        user = students_col.find_one({'rollno': rollno, 'password': password})
        if user:
            session['rollno'] = user['rollno']
            session['name'] = user['name']
            session['class'] = user['class']
            session['branch'] = user['branch']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Roll No or Password', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'rollno' not in session:
        return redirect(url_for('login'))
    rollno = session['rollno']
    name = session['name']
    class_section = session['class']
    branch = session['branch']
    id_card = id_cards_col.find_one({'rollno': rollno})
    return render_template('dashboard.html', rollno=rollno, name=name, class_section=class_section, branch=branch, id_card=id_card)

@app.route('/generate_id', methods=['GET', 'POST'])
def generate_id():
    if 'rollno' not in session:
        return redirect(url_for('login'))
    rollno = session['rollno']
    name = session['name']
    class_section = session['class']
    branch = session['branch']
    id_card = id_cards_col.find_one({'rollno': rollno})
    if id_card:
        return render_template('generate_id.html', id_card=id_card, already_created=True)
    if request.method == 'POST':
        address = request.form['address']
        phone = request.form['phone']
        email = request.form['email']
        # Generate QR code with all unique details
        qr_data = {
            'rollno': rollno,
            'name': name,
            'class': class_section,
            'branch': branch,
            'address': address,
            'phone': phone,
            'email': email
        }
        import json
        qr = qrcode.make(json.dumps(qr_data))
        qr_buffer = BytesIO()
        qr.save(qr_buffer, format='PNG')
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')
        # Create ID card image (simple template)
        card_img = Image.new('RGB', (400, 250), color=(255, 255, 255))
        qr_img = qrcode.make(json.dumps(qr_data)).resize((100, 100))
        card_img.paste(qr_img, (280, 20))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(card_img)
        draw.text((20, 20), f"Roll No: {rollno}", fill=(0,0,0))
        draw.text((20, 50), f"Name: {name}", fill=(0,0,0))
        draw.text((20, 80), f"Class: {class_section}", fill=(0,0,0))
        draw.text((20, 110), f"Branch: {branch}", fill=(0,0,0))
        draw.text((20, 140), f"Address: {address}", fill=(0,0,0))
        draw.text((20, 170), f"Phone: {phone}", fill=(0,0,0))
        draw.text((20, 200), f"Email: {email}", fill=(0,0,0))
        card_buffer = BytesIO()
        card_img.save(card_buffer, format='PNG')
        card_base64 = base64.b64encode(card_buffer.getvalue()).decode('utf-8')
        # Store in MongoDB
        id_cards_col.insert_one({
            'rollno': rollno,
            'name': name,
            'class': class_section,
            'branch': branch,
            'address': address,
            'phone': phone,
            'email': email,
            'qr_base64': card_base64
        })
        flash('Digital ID Card generated successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('generate_id.html', rollno=rollno, name=name, class_section=class_section, branch=branch, already_created=False)

@app.route('/download_id')
def download_id():
    if 'rollno' not in session:
        return redirect(url_for('login'))
    rollno = session['rollno']
    id_card = id_cards_col.find_one({'rollno': rollno})
    if not id_card:
        flash('Please generate Digital ID Card first', 'error')
        return redirect(url_for('dashboard'))
    card_base64 = id_card['qr_base64']
    card_bytes = base64.b64decode(card_base64)
    return send_file(BytesIO(card_bytes), mimetype='image/png', as_attachment=True, download_name=f'{rollno}_id_card.png')

@app.route('/verify_id', methods=['GET', 'POST'])
def verify_id():
    result = None
    if request.method == 'POST':
        if 'id_image' not in request.files:
            result = 'No file uploaded.'
        else:
            file = request.files['id_image']
            if file.filename == '':
                result = 'No file selected.'
            else:
                img = Image.open(file.stream)
                decoded_objs = decode(img)
                if not decoded_objs:
                    result = '❌ QR Code not detected.'
                else:
                    try:
                        qr_data = decoded_objs[0].data.decode('utf-8')
                        import json
                        qr_json = json.loads(qr_data)
                        required_fields = ['rollno', 'name', 'class', 'branch', 'address', 'phone', 'email']
                        if all(field in qr_json for field in required_fields):
                            # Only allow verification if the QR rollno matches the logged-in user
                            if 'rollno' in session and qr_json['rollno'] == session['rollno']:
                                record = id_cards_col.find_one({
                                    'rollno': qr_json['rollno'],
                                    'name': qr_json['name'],
                                    'class': qr_json['class'],
                                    'branch': qr_json['branch'],
                                    'address': qr_json['address'],
                                    'phone': qr_json['phone'],
                                    'email': qr_json['email']
                                })
                                if record:
                                    result = '✅ ID Card matched!'
                                else:
                                    result = '❌ ID Card not matched.'
                            else:
                                result = '❌ ID Card not matched.'
                        else:
                            result = '❌ Invalid QR data.'
                    except Exception as e:
                        result = '❌ Error decoding QR: ' + str(e)
    return render_template('verify_id.html', result=result)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/public_verify_id', methods=['GET', 'POST'])
def public_verify_id():
    result = None
    if request.method == 'POST':
        if 'id_image' not in request.files:
            result = 'No file uploaded.'
        else:
            file = request.files['id_image']
            if file.filename == '':
                result = 'No file selected.'
            else:
                img = Image.open(file.stream)
                decoded_objs = decode(img)
                if not decoded_objs:
                    result = 'ID card Not valid'
                else:
                    try:
                        qr_data = decoded_objs[0].data.decode('utf-8')
                        import json
                        qr_json = json.loads(qr_data)
                        required_fields = ['rollno', 'name', 'class', 'branch', 'address', 'phone', 'email']
                        if all(field in qr_json for field in required_fields):
                            record = id_cards_col.find_one({
                                'rollno': qr_json['rollno'],
                                'name': qr_json['name'],
                                'class': qr_json['class'],
                                'branch': qr_json['branch'],
                                'address': qr_json['address'],
                                'phone': qr_json['phone'],
                                'email': qr_json['email']
                            })
                            if record:
                                result = 'Valid ID card'
                            else:
                                result = 'ID card Not valid'
                        else:
                            result = 'ID card Not valid'
                    except Exception as e:
                        result = 'ID card Not valid'
    return render_template('public_verify_id.html', result=result)

# ... more routes will be added here ...

if __name__ == '__main__':
    app.run(debug=True) 
