from time import time
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
import mysql.connector
import webbrowser
import calendar
import re
from datetime import date, datetime, timedelta
import json
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO
from datetime import datetime

try:
    import tensorflow as tf
    import cv2
    from cv2 import cvtColor, COLOR_BGR2RGB
    from tensorflow import keras
    from keras.utils import load_img, img_to_array
    import matplotlib as plt
    import matplotlib.pyplot as plt
except Exception:
    tf = None
    cv2 = None
    cvtColor = None
    COLOR_BGR2RGB = None
    keras = None
    load_img = None
    img_to_array = None
    plt = None
    matplotlib = None

import os
import base64
from urllib.parse import urlparse, unquote, parse_qs


app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', '09319bcf8f178797da4aa5feaa371018')  # Needed for flash messages and sessions

def build_db_config():
    def parse_connection_string(value):
        if not value or '://' not in value:
            return None
        try:
            parsed = urlparse(value)
        except Exception:
            return None
        if parsed.scheme not in {'mysql', 'mysql+mysqlconnector', 'mysql+pymysql'} and not parsed.scheme.startswith('mysql'):
            return None
        query = parse_qs(parsed.query)
        ssl_mode = (query.get('ssl_mode', [os.getenv('DB_SSL_MODE', 'preferred')])[0] or 'preferred').lower()
        return {
            'host': parsed.hostname or os.getenv('DB_HOST', 'localhost'),
            'port': parsed.port or int(os.getenv('DB_PORT', '3306')),
            'user': unquote(parsed.username or os.getenv('DB_USER', 'root')),
            'password': unquote(parsed.password or os.getenv('DB_PASSWORD', 'test1234')),
            'database': parsed.path.lstrip('/') or os.getenv('DB_NAME', 'DeepChest'),
            'ssl_disabled': ssl_mode == 'disabled'
        }

    for value in [os.getenv('DATABASE_URL'), os.getenv('DB_URL'), os.getenv('DB_HOST')]:
        parsed_config = parse_connection_string(value)
        if parsed_config:
            return parsed_config

    ssl_mode = os.getenv('DB_SSL_MODE', 'preferred').lower()
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', 'test1234'),
        'database': os.getenv('DB_NAME', 'DeepChest')
    }
    if ssl_mode == 'required':
        db_config['ssl_disabled'] = False
    elif ssl_mode == 'disabled':
        db_config['ssl_disabled'] = True
    else:
        db_config['ssl_disabled'] = False
    return db_config


db_config = build_db_config()

# Configures Route for the home page
@app.route('/')
def home():
    return render_template('index.html', username=session.get('username'))

@app.route('/health')
def health():
    return jsonify(status='ok')

@app.route('/health/db')
def health_db():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify(status='ok', database=db_config.get('database'))
    except Exception as exc:
        return jsonify(status='error', error=str(exc)), 500

# Configures Route for the login page 
@app.route('/login', methods=['GET', 'POST'])
#function to handle login logic such as verifying user credentials and redirecting based on user type
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        # Query to check if user exists
        cursor.execute(
            "SELECT * FROM login WHERE username=%s AND password=%s",
            (username, password)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            # Set session variables
            session['user_id'] = user['USERID']
            session['username'] = user['username']
            session['userType'] = user['userType']
            session['clinicID'] = user['clinicID']

            # Redirect based on user type
            if user['userType'] == 'patient':
                  conn = mysql.connector.connect(**db_config)
                  cursor = conn.cursor(dictionary=True)
                  cursor.execute("SELECT firstName, lastName FROM patient WHERE USERID = %s", (user['USERID'],))
                  patient = cursor.fetchone()
                  cursor.close()
                  conn.close()
                  if patient:
                      session['firstName'] = patient['firstName']
                      session['lastName'] = patient['lastName']
                  else:
                      session['firstName'] = user['username']
                      session['lastName'] = ""
                  return redirect(url_for('patient_home'))
            elif user['userType'] == 'doctor':
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT firstName, lastName FROM doctor WHERE USERID = %s", (user['USERID'],))
                doctor = cursor.fetchone()
                cursor.close()
                conn.close()
                session['firstName'] = doctor['firstName']
                session['lastName'] =  doctor['lastName']
                return redirect(url_for('doctor_home'))
            elif user['userType'] == 'clinicadmin':
                return redirect(url_for('admin_home'))
            else:
                flash('Unknown user type')
                return redirect(url_for('login'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))
    return render_template('login.html')

#Route for signing up clinics
@app.route('/clinic_signup', methods=['GET', 'POST'])
def clinic_signup():
    if request.method == 'POST':
        # Get form data
        username = request.form.get('Username')
        password = request.form.get('password')
        email = request.form.get('email')
        phone = request.form.get('phoneNumber')
        clinicName = request.form.get('clinicName')
        clinicEmail = request.form.get('clinicEmail')
        address = request.form.get('address')
        city = request.form.get('city')
        province = request.form.get('province')
        postal_code = request.form.get('postalCode')
        
        # Validate required fields
        if not all([username, password, email, phone, clinicName, clinicEmail, address, city, province, postal_code]):
            flash('All fields are required.', 'danger')
            return render_template('clinic_signup.html')
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        try:
            # Check if username already exists
            cursor.execute("SELECT * FROM login WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists. Please choose a different username.', 'danger')
                cursor.close()
                conn.close()
                return render_template('clinic_signup.html')
            
            # Insert into clinic table
            cursor.execute("""
                INSERT INTO clinic (clinicName, address, city, province, postalCode) 
                VALUES (%s, %s, %s, %s, %s)
            """, (clinicName, address, city, province, postal_code))
            
            # Get the newly created clinicID
            clinic_id = cursor.lastrowid
            
            # Insert into login table
            cursor.execute("""
                INSERT INTO login (username, password, userType, clinicID) 
                VALUES (%s, %s, 'clinicadmin', %s)
            """, (username, password, clinic_id))
            
            # Get the newly created USERID
            user_id = cursor.lastrowid
            
            # Insert into clinicadmin table
            cursor.execute("""
                INSERT INTO clinicadmin (USERID, clinicID, email) 
                VALUES (%s, %s,%s)
            """, (user_id, clinic_id,clinicEmail))
            
            conn.commit()
            flash('Clinic registered successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
            
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Database error: {err}', 'danger')
            return render_template('clinic_signup.html')
        
        finally:
            cursor.close()
            conn.close()
    
    # GET request - show the form
    return render_template('clinic_signup.html')

#Route for signing up new users(Incomplete, just a placeholder)
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    import mysql.connector
    clinics = []
    doctors = []
    if request.method == 'POST':
        # Get form data
        clinicID = request.form.get('clinicID')
        doctorID = request.form.get('doctorID')
        firstName = request.form.get('firstName')
        lastName = request.form.get('lastName')
        email = request.form.get('email')
        phoneNumber = request.form.get('phoneNumber')
        password = request.form.get('password')
        birthday = request.form.get('birthday')
        address = request.form.get('address')
        city = request.form.get('city')
        province = request.form.get('province')
        postalCode = request.form.get('postalCode')
        insurance = request.form.get('insurance')
        notifications_enabled = request.form.get('notifications_enabled', '0')
        notification_email = email if notifications_enabled == '1' else None
        username = email  # Or generate a username as needed
        childID = None  # Assuming childID is optional or can be set later

        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Insert into login table (assuming userType is 'patient')
        cursor.execute(
            "INSERT INTO login (USERID, username, password, userType, clinicID) VALUES (%s, %s, %s, %s, %s)",
            (None, username, password, 'patient', clinicID)
        )
        # Get the USERID of the newly inserted user
        conn.commit()
        cursor.execute("SELECT USERID FROM login WHERE username=%s", (username,))
        user = cursor.fetchone()
        user_id = user[0] if user else None

        # Insert into patient table (if you have one)
        # Uncomment and adjust the following if you have a patient table:
        cursor.execute(
           "INSERT INTO `patient` (`firstName`, `lastName`,`dateofbirth`, `USERID`, `address`, `city`, `province`, `postalCode`, `phone`, `email`,`insurance`,`doctorID`,`childID`,`clinicID`,`notifications_enabled`,`notification_email`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s,%s,%s,%s)",
            (firstName, lastName, birthday, user_id, address, city, province, postalCode, phoneNumber, email, insurance, doctorID, childID, clinicID, notifications_enabled, notification_email)
         )

        conn.commit()
        cursor.close()
        conn.close()

        flash('Account created successfully! Please log in.')
        return redirect(url_for('login'))
    else:
        # Fetch clinics from the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT clinicID, city, province FROM clinic")
        clinics = cursor.fetchall()
        # Fetch doctors from the database
        cursor.execute("SELECT USERID, firstName, lastName, clinicID FROM doctor")
        doctors = cursor.fetchall()
        cursor.close()
        conn.close()
    return render_template('signup.html', clinics=clinics, doctors=doctors)


#Routes for each of the user types to their respective home pages. Used above in login route
@app.route('/patient_home')
def patient_home():
    if session.get('userType') == 'patient':
        return render_template(
            'patient/patienthome.html',
            firstName=session.get('firstName'),
            lastName=session.get('lastName'),
            user_id=session.get('user_id')
        )
    return redirect(url_for('login'))

# Patient Appointments Page
@app.route('/patient/appointments')
def patient_appointments():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))
    user_id = session.get('user_id')

    # Fetch all appointments for this patient
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.apptID, a.appointment_date, a.appointment_time, d.firstName AS doctorFirstName, d.lastName AS doctorLastName, a.symptoms
        FROM appointments a
        JOIN doctor d ON a.doctorID = d.USERID
        WHERE a.patientID = %s
        ORDER BY a.appointment_date, a.appointment_time
    """, (user_id,))
    appointments = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'patient/p_appointments.html',
        appointments=appointments
    )

# Handle the selection of an appointment to edit
@app.route('/patient/edit-appointments', methods=['POST'])
def patient_edit_appointments():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))
    appointment_id = request.form.get('appointment_id')
    if not appointment_id:
        flash('Please select an appointment to edit.')
        return redirect(url_for('patient_appointments'))
    try:
        appointment_id = int(appointment_id)
    except ValueError:
        flash('Invalid appointment selected.')
        return redirect(url_for('patient_appointments'))
    return redirect(url_for('patient_manage_appointment', appointment_id=appointment_id))

# Handle appointment cancellation
@app.route('/patient/cancel-appointment', methods=['POST'])
def patient_cancel_appointment():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))
    
    appointment_id = request.form.get('appointment_id')
    user_id = session.get('user_id')
    
    if not appointment_id:
        flash('No appointment selected.', 'error')
        return redirect(url_for('patient_appointments'))
    
    try:
        appointment_id = int(appointment_id)
    except ValueError:
        flash('Invalid appointment ID.', 'error')
        return redirect(url_for('patient_appointments'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # Verify the appointment belongs to this patient before deleting
    cursor.execute("SELECT apptID FROM appointments WHERE apptID = %s AND patientID = %s", (appointment_id, user_id))
    appointment = cursor.fetchone()
    
    if not appointment:
        flash('Appointment not found or you do not have permission to cancel it.', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('patient_appointments'))
    
    try:
        cursor.execute("DELETE FROM appointments WHERE apptID = %s", (appointment_id,))
        conn.commit()
        flash('Appointment cancelled successfully.', 'success')
    except mysql.connector.Error as e:
        flash(f'Error cancelling appointment: {e}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('patient_appointments'))

# Show the manage/edit appointment page
@app.route('/patient/manage-appointment/<int:appointment_id>', methods=['GET', 'POST'])
def patient_manage_appointment(appointment_id):
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    # Fetch the appointment for this patient
    cursor.execute("""
        SELECT a.apptID, a.appointment_date, a.appointment_time, a.symptoms,
               a.doctorID AS doctorID,
               d.firstName AS doctorFirstName, d.lastName AS doctorLastName
        FROM appointments a
        JOIN doctor d ON a.doctorID = d.USERID
        WHERE a.apptID = %s AND a.patientID = %s
    """, (appointment_id, user_id))
    appointment = cursor.fetchone()

    if not appointment:
        cursor.close()
        conn.close()
        flash("Appointment not found.", "danger")
        return redirect(url_for('patient_appointments'))

    if request.method == 'POST':
        # Update date/time/symptoms. Validate conflicts for the assigned doctor.
        new_symptoms = request.form.get('symptoms')
        new_date = request.form.get('appointment_date')
        new_time = request.form.get('appointment_time')

        # Normalize time format if needed (allow HH:MM)
        if new_time and len(new_time) == 5:
            new_time = new_time + ':00'

        # If doctorID exists, check for conflicts excluding this appointment
        doctor_id = None
        try:
            # appointment may be dict-like
            doctor_id = appointment.get('doctorID') if isinstance(appointment, dict) else appointment[ 'doctorID' ] if appointment else None
        except Exception:
            doctor_id = None

        if doctor_id and new_date and new_time:
            cursor.execute("SELECT apptID FROM appointments WHERE doctorID = %s AND appointment_date = %s AND appointment_time = %s AND apptID != %s", (doctor_id, new_date, new_time, appointment_id))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                flash('Selected time slot is not available for your doctor. Please choose another time.')
                return redirect(url_for('patient_manage_appointment', appointment_id=appointment_id))

        # Perform update (only fields provided)
        try:
            cursor.execute("""
                UPDATE appointments SET appointment_date = %s, appointment_time = %s, symptoms = %s
                WHERE apptID = %s AND patientID = %s
            """, (new_date, new_time, new_symptoms, appointment_id, user_id))
            conn.commit()
            flash('Appointment updated successfully!')
            cursor.close()
            conn.close()
            return redirect(url_for('patient_appointments'))
        except mysql.connector.Error as e:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('Database error: ' + str(e))
            return redirect(url_for('patient_manage_appointment', appointment_id=appointment_id))

    cursor.close()
    conn.close()

    # Normalize appointment fields so they are JSON-serializable for the template
    appt_for_template = {}
    if isinstance(appointment, dict):
        for k, v in appointment.items():
            # Dates -> YYYY-MM-DD
            if k in ('appointment_date', 'reportDate') and hasattr(v, 'strftime'):
                try:
                    appt_for_template[k] = v.strftime('%Y-%m-%d')
                except Exception:
                    appt_for_template[k] = str(v)
            # Times: could be time or timedelta depending on driver
            elif k == 'appointment_time':
                if v is None:
                    appt_for_template[k] = None
                else:
                    # datetime.time
                    if hasattr(v, 'strftime'):
                        appt_for_template[k] = v.strftime('%H:%M:%S')
                    # timedelta (mysql sometimes returns TIME as timedelta)
                    elif hasattr(v, 'total_seconds'):
                        secs = int(v.total_seconds())
                        hh = secs // 3600
                        mm = (secs % 3600) // 60
                        ss = secs % 60
                        appt_for_template[k] = f"{hh:02d}:{mm:02d}:{ss:02d}"
                    else:
                        appt_for_template[k] = str(v)
            else:
                appt_for_template[k] = v
    else:
        # Fallback: just pass the original object (template will likely fail if not serializable)
        appt_for_template = appointment

    return render_template('patient/p_manageappointments.html', appointment=appt_for_template)

@app.route('/patient/book-appointment', methods=['GET', 'POST'])
def patient_book_appointment():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    if request.method == 'POST':
        # Collect form inputs
        appointment_date = request.form.get('appointment_date')  # expected YYYY-MM-DD
        appointment_time = request.form.get('appointment_time')  # expected HH:MM:SS
        symptoms = request.form.get('symptoms')

        if not appointment_date or not appointment_time:
            flash('Please select a date and time for your appointment.')
            return redirect(url_for('patient_book_appointment'))

        # Normalize time (allow HH:MM or HH:MM:SS)
        if len(appointment_time) == 5:
            appointment_time = appointment_time + ':00'

        # Fetch patient's doctor and clinic
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT doctorID, clinicID FROM patient WHERE USERID = %s", (user_id,))
        prow = cursor.fetchone()
        doctor_id = None
        clinic_id = None
        if prow:
            try:
                doctor_id = prow[0]
                clinic_id = prow[1]
            except Exception:
                # handle dict cursor vs tuple
                doctor_id = prow.get('doctorID') if isinstance(prow, dict) else None
                clinic_id = prow.get('clinicID') if isinstance(prow, dict) else None

        # If no doctor assigned, we still allow booking without doctor (doctorID NULL)

        # Check for conflict (same doctor, same date/time)
        if doctor_id:
            cursor.execute("SELECT apptID FROM appointments WHERE doctorID = %s AND appointment_date = %s AND appointment_time = %s", (doctor_id, appointment_date, appointment_time))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                flash('Selected time slot is not available. Please choose another time.')
                return redirect(url_for('patient_book_appointment'))

        # Insert appointment
        try:
            cursor.execute("INSERT INTO appointments (patientID, appointment_date, appointment_time, doctorID, clinicID, symptoms) VALUES (%s, %s, %s, %s, %s, %s)", (user_id, appointment_date, appointment_time, doctor_id, clinic_id, symptoms))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Appointment booked successfully!')
            create_notification(patient_id=user_id, doctor_id=doctor_id, event_type="APPOINTMENT_BOOKED")
            return redirect(url_for('patient_appointments'))
        except mysql.connector.Error as e:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('Database error: ' + str(e))
            return redirect(url_for('patient_book_appointment'))

    # GET: render calendar with patient's existing appointment dates
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT appointment_date FROM appointments WHERE patientID = %s", (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    existing_dates = []
    for r in rows:
        try:
            d = r[0]
        except Exception:
            d = r.get('appointment_date') if isinstance(r, dict) else None
        if d:
            # format to YYYY-MM-DD
            if hasattr(d, 'strftime'):
                existing_dates.append(d.strftime('%Y-%m-%d'))
            else:
                existing_dates.append(str(d))

    return render_template('patient/p_bookappointment.html', existing_appointments=existing_dates)


@app.route('/patient/booked_times')
def patient_booked_times():
    # Returns comma-separated list of times already booked for the patient's doctor on a date
    if session.get('userType') != 'patient':
        return '', 401
    user_id = session.get('user_id')
    date_q = request.args.get('date')
    if not date_q:
        return '', 400
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    # get doctor for this patient
    cursor.execute("SELECT doctorID FROM patient WHERE USERID = %s", (user_id,))
    prow = cursor.fetchone()
    doctor_id = None
    if prow:
        try:
            doctor_id = prow[0]
        except Exception:
            doctor_id = prow.get('doctorID') if isinstance(prow, dict) else None
    if not doctor_id:
        cursor.close()
        conn.close()
        return ''
    cursor.execute("SELECT appointment_time FROM appointments WHERE doctorID = %s AND appointment_date = %s", (doctor_id, date_q))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    times = [r[0].strftime('%H:%M:%S') if hasattr(r[0], 'strftime') else str(r[0]) for r in rows]
    return ','.join(times)

@app.route('/admin/booked_times')
def admin_booked_times():
    # Returns comma-separated list of times already booked for a specific doctor on a date
    if session.get('userType') != 'clinicadmin':
        return '', 401
    doctor_id = request.args.get('doctor_id')
    date_q = request.args.get('date')
    if not doctor_id or not date_q:
        return '', 400
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT appointment_time FROM appointments WHERE doctorID = %s AND appointment_date = %s", (doctor_id, date_q))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    times = [r[0].strftime('%H:%M:%S') if hasattr(r[0], 'strftime') else str(r[0]) for r in rows]
    return ','.join(times)

#Patient Reports Page
@app.route('/patient/reports')
def patient_reports():
    if session.get('userType') == 'patient':
        user_id = session.get('user_id')
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.reportID,r.files, r.reportDate, r.doctorID,
                   d.firstName AS doctorFirstName, d.lastName AS doctorLastName
            FROM Reports r
            JOIN doctor d ON r.doctorID = d.USERID
            WHERE r.patientID = %s
            ORDER BY r.reportDate DESC
        """, (user_id,))
        reports = cursor.fetchall()
        cursor.close()
        conn.close()
        for r in reports:
            if isinstance(r['reportDate'], str):
                try:
                    r['reportDate'] = datetime.strptime(r['reportDate'], '%Y-%m-%d')
                except Exception:
                    pass
        return render_template(
            'patient/myreports.html',
            user_id=user_id,
            reports=reports
        )
    return redirect(url_for('login'))

@app.route('/patient/search_reports', methods=['GET'])
def search_reports():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    query = request.args.get('query', '').strip()

    #month_name support
    month_map = {month.lower(): index for index, month in enumerate(calendar.month_name) if month}
    query_lower = query.lower()
    month_num = None
    year_num = None
    for name, num in month_map.items():
        if name in query_lower:
            month_num = num
            match = re.search(rf"{name}\s+(\d{{4}})", query_lower)
            if match:
                year_num = int(match.group(1))
            else:
                match = re.search(rf"(\d{{4}})\s+{name}", query_lower)
                if match:
                   year_num = int(match.group(1))
            break

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    if month_num and year_num:
        cursor.execute("""
            SELECT r.reportID,r.files, r.reportDate, r.doctorID,
                   d.firstName AS doctorFirstName, d.lastName AS doctorLastName
            FROM Reports r
            JOIN doctor d ON r.doctorID = d.USERID
            WHERE r.patientID = %s AND MONTH(r.reportDate) = %s AND YEAR(r.reportDate) = %s
            ORDER BY r.reportDate DESC
        """, (user_id, month_num, year_num))
    elif month_num:
        cursor.execute("""
            SELECT r.reportID,r.files, r.reportDate, r.doctorID,
                   d.firstName AS doctorFirstName, d.lastName AS doctorLastName
            FROM Reports r
            JOIN doctor d ON r.doctorID = d.USERID
            WHERE r.patientID = %s AND MONTH(r.reportDate) = %s
            ORDER BY r.reportDate DESC
        """, (user_id, month_num))
    else:
        cursor.execute("""
            SELECT r.reportID,r.files, r.reportDate, r.doctorID,
                   d.firstName AS doctorFirstName, d.lastName AS doctorLastName
            FROM Reports r
            JOIN doctor d ON r.doctorID = d.USERID
            WHERE r.patientID = %s AND (
                CAST(r.reportID AS CHAR) LIKE %s
                OR r.reportDate LIKE %s
                OR d.firstName LIKE %s
                OR d.lastName LIKE %s
            )
            ORDER BY r.reportDate DESC
        """, (user_id, f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
    reports = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        'patient/myreports.html',
        user_id=user_id,
        reports=reports
    )

# Report details page for patients
@app.route('/patient/report_details')
def patient_report_details():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))
    report_id = request.args.get('reportID')
    user_id = session.get('user_id')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.*, d.firstName AS doctorFirstName, d.lastName AS doctorLastName
        FROM Reports r
        JOIN doctor d ON r.doctorID = d.USERID
    WHERE r.reportID = %s AND r.patientID = %s
    """, (report_id, user_id))
    report = cursor.fetchone()
    cursor.close()
    conn.close()
    if not report:
        flash("Report not found.", "danger")
        return redirect(url_for('patient_reports'))
    return render_template('patient/reportdetails.html', report=report)

# Patient Messages Page (GET: show form, POST: send/save message)
@app.route('/patient/messages', methods=['GET', 'POST'])
def patient_messages():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))

    # Automatically delete expired messages
    expired_count = delete_expired_messages()
    if expired_count > 0:
        flash(f"Automatically removed {expired_count} expired message(s).", "info")

    user_id = session.get('user_id')

    # Get DB connection and fetch doctors for the select box
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        clinic_id = session.get('clinicID')
        if clinic_id:
            cursor.execute('SELECT USERID, firstName, lastName FROM doctor WHERE clinicID = %s', (clinic_id,))
        else:
            cursor.execute('SELECT USERID, firstName, lastName FROM doctor')
        doctors = cursor.fetchall()

        if request.method == 'POST':
            doctor_id = request.form.get('doctorID')
            subject = (request.form.get('subject') or '').strip()
            body = (request.form.get('body') or '').strip()

            # Basic validation
            if not doctor_id:
                flash('Please select a doctor to send the message to.', 'error')
                return render_template('patient/messages.html', doctors=doctors)
            if not subject:
                flash('Please provide a subject for the message.', 'error')
                return render_template('patient/messages.html', doctors=doctors)
            if not body:
                flash('Please write a message.', 'error')
                return render_template('patient/messages.html', doctors=doctors)

            try:
                ins = conn.cursor()
                # messages table schema: (messageID, patientID, doctorID, content, time_sent)
                # There is no separate subject column; store subject+body together in content
                content = f"Subject: {subject}\n\n{body}"
                ins.execute(
                    'INSERT INTO messages (patientID, doctorID, content) VALUES (%s, %s, %s)',
                    (user_id, doctor_id, content)
                )
                conn.commit()
                flash('Message sent successfully.', 'success')
                create_notification(doctor_id=doctor_id, patient_id=user_id, event_type="NEW_MESSAGE")
                ins.close()
                cursor.close()
                conn.close()
                return redirect(url_for('patient_messages'))
            except mysql.connector.Error as e:
                conn.rollback()
                flash('Failed to send message: {}'.format(str(e)), 'error')
                return render_template('patient/messages.html', doctors=doctors)

        # GET
        cursor.close()
        conn.close()
        return render_template('patient/messages.html', doctors=doctors)

    except mysql.connector.Error as err:
        flash('Database error: {}'.format(err), 'error')
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return render_template('patient/messages.html', doctors=[])


# Patient Manage Account Page (GET: pre-fill, POST: update)
@app.route('/patient/account', methods=['GET', 'POST'])
def patient_account():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        # Get updated form data
        firstName = request.form.get('firstName')
        lastName = request.form.get('lastName')
        email = request.form.get('email')
        phoneNumber = request.form.get('phoneNumber')
        password = request.form.get('password')
        birthday = request.form.get('birthday')
        address = request.form.get('address')
        city = request.form.get('city')
        province = request.form.get('province')
        postalCode = request.form.get('postalCode')
        insurance = request.form.get('insurance')
        notifications_enabled = request.form.get('notifications_enabled', '0')
        notification_email = email if notifications_enabled == '1' else None
        # Update patient table
        cursor.execute("""
            UPDATE patient SET firstName=%s, lastName=%s, dateofbirth=%s, address=%s, city=%s, province=%s, postalCode=%s, phone=%s, email=%s, insurance=%s, notifications_enabled=%s, notification_email=%s WHERE USERID=%s
        """, (firstName, lastName, birthday, address, city, province, postalCode, phoneNumber, email, insurance, notifications_enabled, notification_email, user_id))
        # Update login table (password and email/username)
        cursor.execute("""
            UPDATE login SET username=%s, password=%s WHERE USERID=%s
        """, (email, password, user_id))
        conn.commit()
        flash('Account updated successfully!')
        create_notification(patient_id=user_id, event_type="ACCOUNT_UPDATED")
        # Re-fetch updated info for display
    cursor.execute("SELECT * FROM patient WHERE USERID = %s", (user_id,))
    patient = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('patient/p_modifyaccount.html', patient=patient)

# Add Child Page for Patient (GET shows form, POST creates child)
@app.route('/patient/add-child', methods=['GET', 'POST'])
def add_child():
    if session.get('userType') != 'patient':
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    if request.method == 'POST':
        # Handle child creation (merged POST logic)
        parent_id = session.get('user_id')

        # Collect form data
        clinicID = request.form.get('clinicID') or request.form.get('clinic') or session.get('clinicID')
        doctorID = request.form.get('doctorID') or session.get('doctorID') or None
        firstName = request.form.get('firstName', '').strip()
        lastName = request.form.get('lastName', '').strip()
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip() or email
        phoneNumber = request.form.get('phoneNumber', '').strip()
        password = request.form.get('password', '').strip()
        birthday = request.form.get('birthday', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        province = request.form.get('province', '').strip()
        postalCode = request.form.get('postalCode', '').strip()
        insurance = request.form.get('insurance', '').strip()

        # Basic validation
        if not firstName or not lastName or not password:
            flash('Please provide at minimum first name, last name and password for the child.')
            return redirect(url_for('add_child'))

        # Compute age when birthday provided
        age = None
        if birthday:
            try:
                dob = datetime.strptime(birthday, '%Y-%m-%d').date()
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            except Exception:
                dob = None
                age = None
        else:
            dob = None

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Ensure parent has an email on file
        cursor.execute("SELECT email FROM patient WHERE USERID = %s", (parent_id,))
        parent_row = cursor.fetchone()
        parent_email = None
        if parent_row:
            try:
                parent_email = parent_row[0]
            except Exception:
                parent_email = parent_row.get('email') if isinstance(parent_row, dict) else None

        if not parent_email and not session.get('email'):
            cursor.close()
            conn.close()
            flash('Please add your email to your account before registering a child.')
            return redirect(url_for('patient_account'))

        try:
            # Check if email already exists in patient table
            if email:
                cursor.execute("SELECT USERID FROM patient WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('Email is already in use. Choose a different email.')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('add_child'))

            # Insert into login table for the child
            cursor.execute(
                "INSERT INTO login (username, password, userType, clinicID) VALUES (%s, %s, %s, %s)",
                (username, password, 'patient', clinicID)
            )
            child_userid = cursor.lastrowid

            # Insert into patient table for the child
            cursor.execute(
                "INSERT INTO patient (firstName, lastName, age, dateofbirth, USERID, address, city, province, postalCode, phone, email, insurance, doctorID, childID, clinicID) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (firstName, lastName, age, dob, child_userid, address, city, province, postalCode, phoneNumber, email, insurance, doctorID or None, None, clinicID)
            )

            # Create a childLink row linking to the parent
            cursor.execute("INSERT INTO childLink (parentID) VALUES (%s)", (parent_id,))
            link_id = cursor.lastrowid

            # Create a child row referencing the link and parent
            cursor.execute("INSERT INTO child (linkID, parentID) VALUES (%s, %s)", (link_id, parent_id))
            child_id = cursor.lastrowid

            # Update the child's patient row to store the childID (if desired by schema)
            cursor.execute("UPDATE patient SET childID = %s WHERE USERID = %s", (str(child_id), child_userid))

            conn.commit()
            flash('Child account created successfully!')
            cursor.close()
            conn.close()
            return redirect(url_for('patient_home'))
        except mysql.connector.Error as e:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('Database error: ' + str(e))
            return redirect(url_for('add_child'))

    # GET: show form
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # Fetch patient info
    cursor.execute("SELECT * FROM patient WHERE USERID = %s", (user_id,))
    patient = cursor.fetchone()

    # Determine clinicID and doctorID (prefer patient table values)
    clinic_id = None
    doctor_id = None
    if patient:
        clinic_id = patient.get('clinicID')
        doctor_id = patient.get('doctorID')

    # Fallback to session values if DB values missing
    if not clinic_id:
        clinic_id = session.get('clinicID')
    if not doctor_id:
        doctor_id = session.get('doctorID')

    # Fetch clinic info
    clinic = None
    if clinic_id:
        cursor.execute("SELECT * FROM clinic WHERE clinicID = %s", (clinic_id,))
        clinic = cursor.fetchone()

    # Fetch doctor info
    doctor = None
    if doctor_id:
        cursor.execute("SELECT * FROM doctor WHERE USERID = %s", (doctor_id,))
        doctor = cursor.fetchone()

    cursor.close()
    conn.close()

    # Render template with DB-provided objects (may be None)
    return render_template('patient/add-child.html', patient=patient, doctor=doctor, clinic=clinic)




# Doctor Home Page
@app.route('/doctor_home')
def doctor_home():
    if session.get('userType') == 'doctor':
        return render_template('doctor/doctorhome.html', firstName=session.get('firstName'), lastName=session.get('lastName'))
    return redirect(url_for('login'))

# Doctor Appointments Page
# Doctor Appointments List
@app.route('/doctor/appointments')
def doctor_appointments():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # Join appointments with patient info
    cursor.execute("""
        SELECT a.apptID, a.appointment_date, a.appointment_time, a.symptoms,
               p.firstName, p.lastName
        FROM appointments a
        JOIN patient p ON a.patientID = p.USERID
        ORDER BY a.appointment_date, a.appointment_time
    """)
    appointments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('doctor/doctor_appointments.html',
                           appointments=appointments,
                           username=session.get('username'))


# Doctor Appointment Detail Page
@app.route('/doctor/appointments/detail')
def doctor_appointments_detail():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))

    apptID = request.args.get('apptID')
    if not apptID:
        flash("No appointment selected.")
        return redirect(url_for('doctor_appointments'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # Get full appointment + patient info
    cursor.execute("""
        SELECT a.apptID, a.appointment_date, a.appointment_time, a.symptoms,
               p.firstName, p.lastName, p.dateofbirth, p.phone, p.email
        FROM appointments a
        JOIN patient p ON a.patientID = p.USERID
        WHERE a.apptID = %s
    """, (apptID,))
    appointment = cursor.fetchone()

    cursor.close()
    conn.close()

    if not appointment:
        flash("Appointment not found.")
        return redirect(url_for('doctor_appointments'))

    return render_template('doctor/doctor_appointment_detail.html',
                           appointment=appointment,
                           username=session.get('username'))


@app.route('/doctor/search_appointments', methods=['GET'])
def search_appointments():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))

    # Get search text from the input field
    search_term = request.args.get('query', '').strip()

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    if search_term:
        cursor.execute("""
            SELECT a.apptID, a.appointment_date, a.appointment_time, a.symptoms,
                   p.firstName, p.lastName
            FROM appointments a
            JOIN patient p ON a.patientID = p.USERID
            WHERE p.firstName LIKE %s
               OR p.lastName LIKE %s
               OR a.symptoms LIKE %s
               OR a.appointment_date LIKE %s
            ORDER BY a.appointment_date, a.appointment_time
        """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
    else:
        # If no search term, show all appointments
        cursor.execute("""
            SELECT a.apptID, a.appointment_date, a.appointment_time, a.symptoms,
                   p.firstName, p.lastName
            FROM appointments a
            JOIN patient p ON a.patientID = p.USERID
            ORDER BY a.appointment_date, a.appointment_time
        """)

    appointments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('doctor/doctor_appointments.html',
                           appointments=appointments,
                           username=session.get('username'),
                           query=search_term)



# Database connection helper
def get_db_connection():
    """Create and return a new MySQL database connection."""
    return mysql.connector.connect(**db_config)


# Doctor Patients Page
@app.route('/doctor/patients')
def doctor_patients():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')
    doctor_username = session.get('username')

    if not doctor_id:
        return "Doctor not found", 404

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.firstName, p.lastName, p.age, p.dateofbirth, p.phone, p.email,
               p.address, p.city, p.province, p.postalCode, p.insurance
        FROM patient p
        WHERE p.doctorID = %s
    """, (doctor_id,))

    patients = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('doctor/doctor_patients.html',
                           username=doctor_username,
                           patients=patients)


# Doctor Search Patients Route
@app.route('/doctor/search_patients', methods=['GET'])
def doctor_search_patients():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')
    doctor_username = session.get('username')

    if not doctor_id:
        return "Doctor not found", 404

    # Get search query and normalize
    query = request.args.get('query', '').strip()
    search_query = f"%{query.lower()}%"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if query:
        # Case-insensitive search with trimmed fields
        cursor.execute("""
            SELECT p.firstName, p.lastName, p.age, p.dateofbirth, p.phone, p.email,
                   p.address, p.city, p.province, p.postalCode, p.insurance
            FROM patient p
            WHERE p.doctorID = %s AND (
                LOWER(TRIM(p.firstName)) LIKE %s OR
                LOWER(TRIM(p.lastName)) LIKE %s OR
                LOWER(TRIM(p.email)) LIKE %s OR
                LOWER(TRIM(p.phone)) LIKE %s OR
                LOWER(TRIM(p.city)) LIKE %s
            )
            ORDER BY p.lastName, p.firstName
        """, (doctor_id, search_query, search_query, search_query, search_query, search_query))
    else:
        # If no query, return all patients for this doctor
        cursor.execute("""
            SELECT p.firstName, p.lastName, p.age, p.dateofbirth, p.phone, p.email,
                   p.address, p.city, p.province, p.postalCode, p.insurance
            FROM patient p
            WHERE p.doctorID = %s
            ORDER BY p.lastName, p.firstName
        """, (doctor_id,))

    patients = cursor.fetchall()
    cursor.close()
    conn.close()

    # Render template with results and original query
    return render_template(
        'doctor/doctor_patients.html',
        username=doctor_username,
        patients=patients,
        query=query
    )



# Doctor Reports Page
@app.route('/doctor/reports')
def doctor_reports():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # Pull all reports for this doctor, join patient info
    cursor.execute("""
        SELECT r.reportID, r.files, p.firstName, p.lastName, r.reportDate
        FROM Reports r
        JOIN patient p ON r.patientID = p.USERID
        WHERE r.doctorID = %s
    """, (doctor_id,))

    reports = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'doctor/doctor_reports.html',
        username=session.get('username'),
        reports=reports
    )


@app.route('/view_report/<int:report_id>')
def view_report(report_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    
    user_type = session.get('userType')
    user_id = session.get('user_id')
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Fetch report based on user type
    if user_type == 'patient':
        cursor.execute("SELECT files FROM Reports WHERE reportID = %s AND patientID = %s", (report_id, user_id))
    elif user_type == 'doctor':
        cursor.execute("SELECT files FROM Reports WHERE reportID = %s AND doctorID = %s", (report_id, user_id))
    elif user_type == 'clinicadmin':
        clinic_id = session.get('clinicID')
        cursor.execute("""
            SELECT r.files FROM Reports r
            JOIN patient p ON r.patientID = p.USERID
            WHERE r.reportID = %s AND p.clinicID = %s
        """, (report_id, clinic_id))
    else:
        cursor.close()
        conn.close()
        return "Unauthorized", 403
    
    report = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not report or not report['files']:
        return "Report not found", 404
    
    pdf_bytes = report['files']
    
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"report_{report_id}.pdf"
    )

@app.route('/doctor/search_reports', methods=['GET'])
def doctor_search_reports():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    query = request.args.get('query', '').strip()

    # Month name support
    month_map = {month.lower(): index for index, month in enumerate(calendar.month_name) if month}
    query_lower = query.lower()
    month_num = None
    year_num = None
    for name, num in month_map.items():
        if name in query_lower:
            month_num = num
            match = re.search(rf"{name}\s+(\d{{4}})", query_lower)
            if match:
                year_num = int(match.group(1))
            else:
                match = re.search(rf"(\d{{4}})\s+{name}", query_lower)
                if match:
                    year_num = int(match.group(1))
            break

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # If user typed "March 2024" or similar
    if month_num and year_num:
        cursor.execute("""
            SELECT r.reportID, r.reportDate, r.files,
                   p.firstName AS patientFirstName, p.lastName AS patientLastName
            FROM Reports r
            JOIN patient p ON r.patientID = p.USERID
            WHERE r.doctorID = %s AND MONTH(r.reportDate) = %s AND YEAR(r.reportDate) = %s
            ORDER BY r.reportDate DESC
        """, (user_id, month_num, year_num))

    # If user typed just "March"
    elif month_num:
        cursor.execute("""
            SELECT r.reportID, r.reportDate, r.files,
                   p.firstName AS patientFirstName, p.lastName AS patientLastName
            FROM Reports r
            JOIN patient p ON r.patientID = p.USERID
            WHERE r.doctorID = %s AND MONTH(r.reportDate) = %s
            ORDER BY r.reportDate DESC
        """, (user_id, month_num))

    # Generic keyword search (report ID, date, patient name)
    else:
        cursor.execute("""
            SELECT r.reportID, r.reportDate, r.files,
                   p.firstName AS patientFirstName, p.lastName AS patientLastName
            FROM Reports r
            JOIN patient p ON r.patientID = p.USERID
            WHERE r.doctorID = %s AND (
                CAST(r.reportID AS CHAR) LIKE %s
                OR r.reportDate LIKE %s
                OR p.firstName LIKE %s
                OR p.lastName LIKE %s
            )
            ORDER BY r.reportDate DESC
        """, (user_id, f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))

    reports = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'doctor/doctor_reports.html',
        username=session.get('username'),
        reports=reports
    )

#AI Grad-CAM logic
model_path = "model_1.keras"
class_names = ["COVID19","NORMAL","PNEUMONIA","TUBERCOLOSIS"]
model = None
grad_model = None


def load_ai_model():
    global model, grad_model
    if model is not None and grad_model is not None:
        return True
    if tf is None or keras is None or cv2 is None:
        return False
    if not os.path.exists(model_path):
        return False
    try:
        model = tf.keras.models.load_model(model_path)
        input_tensor = keras.Input(shape=(224, 224, 3))
        x = input_tensor
        last_conv_output = None
        for layer in model.layers:
            x = layer(x)
            if layer.name == "last_conv":
                last_conv_output = x
        predictions = x
        grad_model = keras.Model(inputs=input_tensor, outputs=[last_conv_output, predictions])
        return True
    except Exception:
        return False

load_ai_model()

def preprocess_input(file_storage):
    if load_img is None or img_to_array is None:
        raise RuntimeError("AI dependencies are not available")
    file_storage.seek(0)
    img = load_img(file_storage, target_size=(224,224))
    img_array = img_to_array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    img_uint8 = img_to_array(img).astype("uint8")
    return img_array, img_uint8


def make_gradcam_heatmap(img_array):
    if tf is None or grad_model is None:
        raise RuntimeError("AI model is not available")
    img_tensor = tf.convert_to_tensor(img_array, dtype=tf.float32)
    
    with tf.GradientTape() as tape:
        conv_outputs, preds = grad_model(img_tensor, training=False)
        
        preds = preds[0]             
        top_index = tf.argmax(preds)  
        class_channel = preds[top_index]

    # This is the gradient of the output neuron (top predicted or chosen)
    grads = tape.gradient(class_channel, conv_outputs)[0]

    # This is a vector where each entry is the mean intensity of the gradient
    # over a specific feature map channel
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1))

    # We multiply each channel in the feature map array
    conv_outputs = conv_outputs
    heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)

    # normalize the heatmap 0-1
    heatmap = tf.maximum(heatmap, 0) / tf.math.reduce_max(heatmap)
    return heatmap.numpy(), preds.numpy()

def gradcam_overlay(img_uint8, heatmap):
    if cv2 is None:
        raise RuntimeError("OpenCV is not available")
    h,w,_=img_uint8.shape
    heatmap_resized = cv2.resize(heatmap, (w,h))
    heatmap_color = cv2.applyColorMap(
        np.uint8(255*heatmap_resized),
        cv2.COLORMAP_JET
    )
    img_bgr = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2BGR)
    overlay = cv2.addWeighted(img_bgr, 0.6, heatmap_color, 0.4, 0)
    return overlay

def overlay_png(overlay_bgr):
    overlay_rgb = cv2.cvtColor(overlay_bgr, cv2.COLOR_RGB2BGR)
    pil_img = keras.utils.array_to_img(overlay_bgr)
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

def predict2(xray_bytes):
    if not load_ai_model():
        raise RuntimeError("AI model is not available")
    file_like = BytesIO(xray_bytes)

    img_array, img_uint8 = preprocess_input(file_like)

    heatmap, preds = make_gradcam_heatmap(img_array)

    pred_idx = int(np.argmax(preds))
    predicted_label = class_names[pred_idx]
    predicted_prob = float(preds[pred_idx] * 100.0)

    h, w, _ = img_uint8.shape
    heatmap_resized = cv2.resize(heatmap, (w, h))
    heatmap_color = cv2.applyColorMap(
        np.uint8(255 * heatmap_resized),
        cv2.COLORMAP_JET
    )
    img_bgr = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2BGR)
    overlay_bgr = cv2.addWeighted(img_bgr, 0.6, heatmap_color, 0.4, 0)

    # convert overlay to PNG bytes
    overlay_rgb = cv2.cvtColor(overlay_bgr, cv2.COLOR_BGR2RGB)
    pil_img = keras.utils.array_to_img(overlay_rgb)
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    gradcam_png = buf.read()

    probs = list(zip(class_names, [float(p * 100.0) for p in preds]))

    return {
        "label": predicted_label,
        "prob": predicted_prob,
        "probs": probs,
        "gradcam_png": gradcam_png,
    }

def display_gradcam(img_path, model, last_conv_layer_name="last_conv"):
    #img array
    img_array = preprocess_input(img_path)
    
    # Load the original image
    img = keras.utils.load_img(img_path, target_size=(224,224))
    img = keras.utils.img_to_array(img).astype("uint8")

    # Rescale heatmap to a range 0-255
    heatmap, preds = make_gradcam_heatmap(img_array, model, last_conv_layer_name)

  # Predicted class + probability
    pred_idx = int(np.argmax(preds))
    pred_name = class_names[pred_idx]
    pred_prob = float(preds[pred_idx]) * 100

    # colormap
    heatmap_resized = cv2.resize(heatmap, (img.shape[1], img.shape[0]))
    heatmap_color = cv2.applyColorMap(
        np.uint8(255 * heatmap_resized),
        cv2.COLORMAP_JET
    )
    overlay = cv2.addWeighted(img, 0.6, heatmap_color, 0.4, 0)
    #show
    plt.figure(figsize=(6, 6))
    plt.imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    plt.axis("off")
    plt.title(f"{pred_name} ({pred_prob:.1f}%)")
    plt.show()

#get the x-ray from database method
def get_xray(xray_id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT "
    )
def predict(file):
    img = load_img(file, target_size=(224,224))
    img_array = preprocess_input(file)

    heatmap, preds = make_gradcam_heatmap(img_array, model, last_conv_layer_name="last_conv")

    #interpreting the predictions
    predicted_idx = int(np.argmax(preds))
    predicted_label = class_names[predicted_idx]
    predicted_prob = float(preds[predicted_idx]*100)

    #Probs for website 
    probs = list(zip(class_names, preds))

    #Grad-CAM
    grad_cam = display_gradcam(file, model, last_conv_layer_name="last_conv")

    return grad_cam, predicted_label, predicted_prob, probs

#get x-ray bytes
def get_xray(xray_id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    for table_name in ['xrays', 'Xrays']:
        try:
            cursor.execute(f"SELECT files FROM {table_name} WHERE xrayID = %s", (xray_id,))
            row = cursor.fetchone()
            if row:
                cursor.close()
                conn.close()
                return row[0]
        except Exception:
            continue
    cursor.close()
    conn.close()
    return None

def generate_report(patient, doctor_note, xray_bytes, ai_prediction=None, pdf_title=None, clinic=None):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

   
    if pdf_title:
        c.setTitle(pdf_title)

    # title
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(page_width / 2, page_height - 60, "Chest X-Ray Diagnostic Report")

    # Clinic information (if provided)
    y = page_height - 85
    if clinic:
        c.setFont("Helvetica", 11)
        clinic_info = f"{clinic['clinicName']}"
        c.drawCentredString(page_width / 2, y, clinic_info)
        y -= 12
        address_info = f"{clinic['city']}, {clinic['province']} {clinic['postalCode']}"
        c.drawCentredString(page_width / 2, y, address_info)
        y -= 18
    else:
        y -= 15

    #patient info
    line_h = 14

    def draw_meta(label, value):
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(160, y, str(value))
        y -= line_h

    draw_meta("Patient Name", f"{patient['firstName']} {patient['lastName']}")
    draw_meta("Patient Symptoms", patient['symptom'])
    draw_meta("Date", datetime.now().strftime('%Y-%m-%d'))
    draw_meta("Doctor", f"{session.get('firstName')} {session.get('lastName')}")

    # seperate line
    y -= 6
    c.setLineWidth(0.5)
    c.line(50, y, page_width - 50, y)
    y -= 18

    # AI Diagnosis section
    if ai_prediction:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "AI-Assisted Diagnosis:")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(50, y, f"Predicted Condition: {ai_prediction['label']}")
        y -= 14
        c.drawString(50, y, f"Confidence: {ai_prediction['prob']:.1f}%")
        y -= 14
        c.setFont("Helvetica", 11)
        c.drawString(50, y, "All Probabilities:")
        y -= 12
        for condition, prob in ai_prediction['probs']:
            c.drawString(70, y, f"{condition}: {prob:.1f}%")
            y -= 12
        y -= 6
        c.setLineWidth(0.5)
        c.line(50, y, page_width - 50, y)
        y -= 18

    # Doctor notes
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Doctor Notes:")
    y -= 16

    text = c.beginText(50, y)
    text.setFont("Helvetica", 11)
    text.setLeading(14)
    text.textLines(doctor_note)
    c.drawText(text)

    # Reserve vertical space for notes (avoid overlapping the X-ray)
    y_for_image = page_height * 0.20  # lower position on page

    # ===== X-ray image =====
    try:
        img_buffer = BytesIO(xray_bytes)
        xray_img = ImageReader(img_buffer)

        img_w, img_h = xray_img.getSize()
        max_w = page_width * 0.45
        max_h = page_height * 0.30
        scale = min(max_w / img_w, max_h / img_h)

        draw_w = img_w * scale
        draw_h = img_h * scale

        # center image horizontally
        x_pos = (page_width - draw_w) / 2
        y_pos = y_for_image

        c.drawImage(xray_img, x_pos, y_pos, width=draw_w, height=draw_h)

    except Exception as e:
        print("Error adding X-ray to PDF:", e)

    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# Doctor AI Diagnosis Page

@app.route('/doctor/report_generation', methods=['GET','POST'])
def doctor_report_generation():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))
    
    report_expiry_date = datetime.now() + timedelta(days=10)
    patient_name = request.form.get('patient_name')
    doctor_id = session.get('user_id')
    doctor_note = request.form.get('doctor_note', 'No additional notes provided.')
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    report_date = datetime.now()

    #get patient
    cursor.execute("SELECT USERID, clinicID FROM patient WHERE CONCAT(firstName, ' ', lastName) = %s", (patient_name,))
    patient_row = cursor.fetchone()
    patient_id = patient_row[0]
    clinic_id = patient_row[1]

    #get symptoms
    cursor.execute("SELECT symptoms FROM appointments WHERE patientID = %s ORDER BY appointment_date DESC, appointment_time DESC LIMIT 1", (patient_id,))
    patient_symptoms = cursor.fetchone()[0] or 'N/A'
    
    #get clinic information
    clinic = None
    if clinic_id:
        cursor.execute("SELECT clinicName, city, province, postalCode FROM clinic WHERE clinicID = %s", (clinic_id,))
        clinic_row = cursor.fetchone()
        if clinic_row:
            clinic = {
                'clinicName': clinic_row[0],
                'city': clinic_row[1],
                'province': clinic_row[2],
                'postalCode': clinic_row[3]
            }
    
    #get x-ray
    xray_bytes = None
    for table_name in ['xrays', 'Xrays']:
        try:
            cursor.execute(f"SELECT files FROM {table_name} WHERE patientID = %s ORDER BY date DESC LIMIT 1", (patient_id,))
            file = cursor.fetchone()
            if file:
                xray_bytes = file[0]
                break
        except Exception:
            continue

    if xray_bytes is None:
        cursor.close()
        conn.close()
        flash('No x-ray record found for that patient.')
        return redirect(url_for('doctor_ai_diagnosis'))

    # Generate AI prediction
    ai_prediction = None
    try:
        ai_prediction = predict2(xray_bytes)
    except Exception as e:
        print(f"Error generating AI prediction: {e}")

    report_pdf = generate_report(
        patient={'firstName': patient_name.split(' ')[0], 'lastName': patient_name.split(' ')[1], 'symptom': patient_symptoms},
        doctor_note=doctor_note,
        xray_bytes=xray_bytes,
        ai_prediction=ai_prediction,
        pdf_title=f"Diagnostic Report: {patient_name} {report_date.strftime('%Y-%m-%d')}",
        clinic=clinic
    )
    #save report to database
    cursor.execute("INSERT INTO Reports (patientID, doctorID, reportDate, expiryDate, files) VALUES (%s, %s, %s, %s, %s)",
                       (patient_id, doctor_id, report_date, report_expiry_date, report_pdf))
    conn.commit()  # Commit the transaction to save the report
    
    # Get the reportID of the newly inserted report
    report_id = cursor.lastrowid
    
    cursor.close()
    conn.close()

    #open report
    filename = f"report_{patient_id}_{report_date.strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        BytesIO(report_pdf),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=filename
        )


@app.route('/doctor/ai_diagnosis', methods=['GET', 'POST'])
def doctor_ai_diagnosis():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))

    prediction = None
    gradcam_b64 = None
    patient_name = request.form.get('patient_name')
    doctor_id = session.get('user_id')
    expiry_date = datetime.now() + timedelta(days=10)
    
    if request.method == 'POST':
        if 'xray' not in request.files:
            flash('No file uploaded.')
            return redirect(request.url)

        file = request.files['xray']
        xray_bytes = file.read()

        if file.filename == '':
            flash('No selected file.')
            return redirect(request.url)
        else:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("SELECT USERID FROM patient WHERE CONCAT(firstName, ' ', lastName) = %s", (patient_name,))
            patient_row = cursor.fetchone()
            patient_id = patient_row[0] if patient_row else None
            if not patient_id:
                cursor.close()
                conn.close()
                flash('Patient not found.')
                return redirect(request.url)

            else:
                for table_name in ['xrays', 'Xrays']:
                    try:
                        cursor.execute(f"""
                           INSERT INTO {table_name} (patientID, doctorID, date, expires_at, files) VALUES (%s, %s, %s, %s, %s)""",
                           (patient_id, doctor_id, datetime.now(), expiry_date, xray_bytes))
                        break
                    except Exception:
                        continue
                else:
                    cursor.close()
                    conn.close()
                    raise RuntimeError('No compatible x-ray table exists in the database')

                conn.commit()
                cursor.close()
                conn.close()
                pred_result = predict2(xray_bytes)
                prediction = pred_result
                gradcam_b64 = base64.b64encode(pred_result["gradcam_png"]).decode('utf-8')

    return render_template(
        'doctor/doctor_ai_diagnosis.html',
        username=session.get('username'),
        patient_name=patient_name,
        prediction=prediction,
        gradcam_b64=gradcam_b64
    )

#request to modify doctor account details
@app.route('/doctor/account', methods=['GET', 'POST'])
def doctor_account():
    if session.get('userType') != 'doctor':
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # Always fetch current info to display
    cursor.execute("SELECT * FROM doctor WHERE USERID = %s", (user_id,))
    doctor = cursor.fetchone()

    if request.method == 'POST':
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        email = request.form.get('email')
        phone = request.form.get('phoneNumber')

        # Instead of updating the doctor table, insert a request
        cursor.execute("""
            INSERT INTO account_update_requests (
                doctorID, requested_firstName, requested_lastName, 
                requested_email, requested_phone
            ) VALUES (%s, %s, %s, %s, %s)
        """, (user_id, first_name, last_name, email, phone))
        conn.commit()

        cursor.close()
        conn.close()

        flash("Your update request has been sent to the admin for approval.", "info")
        return render_template('doctor/doctor_modifyaccount.html', doctor=doctor)

    cursor.close()
    conn.close()

    return render_template('doctor/doctor_modifyaccount.html', doctor=doctor)

def create_notification(patient_id=None, doctor_id=None, event_type="", related_id=None):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO notifications (patientID, doctorID, event_type, relatedID, notification_status)
            VALUES (%s, %s, %s, %s, %s)
        """, (patient_id, doctor_id, event_type, related_id, 0))      # 0 = not yet sent

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("Notification insert error:", str(e))


def send_notifications():
    """
    Retrieves pending notifications and processes them.
    Actual email sending logic is a placeholder for SES or any other service.
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Fetch all pending notifications
        cursor.execute("""
            SELECT n.notificationID, n.patientID, n.doctorID, n.event_type, n.relatedID,
                   p.email AS patient_email, d.email AS doctor_email
            FROM notifications n
            LEFT JOIN patient p ON n.patientID = p.USERID
            LEFT JOIN doctor d ON n.doctorID = d.USERID
            WHERE n.notification_status = FALSE
        """)
        notifications = cursor.fetchall()

        for n in notifications:
            print(f"[{datetime.now()}] Notification ID: {n['notificationID']}")
            print(f"  Event: {n['event_type']}, Related ID: {n['relatedID']}")
            if n['patient_email']:
                print(f"  Patient: {n['patient_email']}")
            if n['doctor_email']:
                print(f"  Doctor: {n['doctor_email']}")

            # send email via SES here
            send_email(
                to_address=n['patient_email'] or n['doctor_email'], subject=get_notification_text(n['event_type']), body="You have a new notification.")

            # Mark notification as sent
            cursor.execute("""
                UPDATE notifications
                SET notification_status = TRUE, created_at = NOW()
                WHERE notificationID = %s
            """, (n['notificationID'],))
            conn.commit()

        cursor.close()
        conn.close()
        print(f"Processed {len(notifications)} pending notifications.")

    except mysql.connector.Error as e:
        print("Database error:", e)
        try:
            cursor.close()
            conn.close()
        except:
            pass

def send_email(to_address, subject, body):
    """
    Placeholder function to send email via AWS SES
    """
    print(f"Sending email to {to_address} with subject '{subject}'")
    print("Email body:")
    print(body)
    # Implement actual email sending logic here



# Add Report Route (doctor adds a new report)
@app.route('/add-report', methods=['POST'])
def add_report():
    data = request.json

    patient_id = data.get('patient_id')
    doctor_id = data.get('doctor_id')

    if not patient_id or not doctor_id:
        return jsonify({"error": "patient_id and doctor_id are required"}), 400

    report_date = data.get('report_date', str(date.today()))
    files = data.get('files', None)

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    query = """
    INSERT INTO Reports (patientID, doctorID, reportDate, files)
    VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (patient_id, doctor_id, report_date, files))
    conn.commit()
    cursor.close()
    conn.close()

    create_notification(patient_id=patient_id, doctor_id=doctor_id, event_type="REPORT_READY")
    create_notification(doctor_id=doctor_id, patient_id=patient_id, event_type="REPORT_SENT_CONFIRMATION")



def get_notification_text(event_type):
    lookup = {
        "ACCOUNT_APPROVED": "Your doctor account modification request has been approved.",
        "REPORT_READY": "Your medical report is now available.",
        "REPORT_DELETED": "A medical report linked to your account has been deleted by admin.",
        "REPORT_SENT": "A report has been successfully sent to a patient.",
        "APPOINTMENT_BOOKED": "A new appointment has been booked.",
    }
    return lookup.get(event_type, "You have a new notification.")


# Clinic Admin Home Page
@app.route('/admin_home')
def admin_home():
    if session.get('userType') == 'clinicadmin':
        return render_template('clinic_admin/adminhome.html', firstName=session.get('firstName'), lastName=session.get('lastName'))
    return redirect(url_for('login'))

@app.route('/admin/appointments')
def admin_appointments():
    if session.get('userType') != 'clinicadmin':
       return redirect(url_for('login'))
    
    clinic_id = session.get('clinicID')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    #Join appointments with patient and doctor info filtered by clinic
    cursor.execute("""
        SELECT a.apptID, a.appointment_date, a.appointment_time, a.symptoms, 
               p.firstName, p.lastName,
               d.firstName AS doctorFirstName, d.lastName AS doctorLastName
        FROM appointments a
        JOIN patient p ON a.patientID = p.USERID
        LEFT JOIN doctor d ON a.doctorID = d.USERID
        WHERE a.clinicID = %s
        ORDER BY a.appointment_date, a.appointment_time 
    """, (clinic_id,))
    appointments = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('/clinic_admin/AppointmentAdmin.html',
                           appointments=appointments,
                           username=session.get('username'))

# Handle the selection of an appointment to edit (admin)
@app.route('/admin/edit-appointments', methods=['POST'])
def admin_edit_appointments():
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    appointment_id = request.form.get('appointment_id')
    if not appointment_id:
        flash('Please select an appointment to edit.')
        return redirect(url_for('admin_appointments'))
    try:
        appointment_id = int(appointment_id)
    except ValueError:
        flash('Invalid appointment selected.')
        return redirect(url_for('admin_appointments'))
    return redirect(url_for('admin_manage_appointment', appointment_id=appointment_id))

# Show the manage/edit appointment page (admin)
@app.route('/admin/manage-appointment/<int:appointment_id>', methods=['GET', 'POST'])
def admin_manage_appointment(appointment_id):
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    clinic_id = session.get('clinicID')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    # Fetch the appointment for this clinic
    cursor.execute("""
        SELECT a.apptID, a.appointment_date, a.appointment_time, a.symptoms,
               a.doctorID AS doctorID, a.patientID,
               d.firstName AS doctorFirstName, d.lastName AS doctorLastName,
               p.firstName AS patientFirstName, p.lastName AS patientLastName
        FROM appointments a
        JOIN patient p ON a.patientID = p.USERID
        LEFT JOIN doctor d ON a.doctorID = d.USERID
        WHERE a.apptID = %s AND a.clinicID = %s
    """, (appointment_id, clinic_id))
    appointment = cursor.fetchone()

    if not appointment:
        cursor.close()
        conn.close()
        flash("Appointment not found.", "danger")
        return redirect(url_for('admin_appointments'))

    if request.method == 'POST':
        # Update date/time/symptoms
        new_symptoms = request.form.get('symptoms')
        new_date = request.form.get('appointment_date')
        new_time = request.form.get('appointment_time')

        # Normalize time format if needed (allow HH:MM)
        if new_time and len(new_time) == 5:
            new_time = new_time + ':00'

        # If doctorID exists, check for conflicts excluding this appointment
        doctor_id = appointment.get('doctorID') if isinstance(appointment, dict) else None

        if doctor_id and new_date and new_time:
            cursor.execute("SELECT apptID FROM appointments WHERE doctorID = %s AND appointment_date = %s AND appointment_time = %s AND apptID != %s", (doctor_id, new_date, new_time, appointment_id))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                flash('Selected time slot is not available for this doctor. Please choose another time.')
                return redirect(url_for('admin_manage_appointment', appointment_id=appointment_id))

        # Perform update
        try:
            cursor.execute("""
                UPDATE appointments SET appointment_date = %s, appointment_time = %s, symptoms = %s
                WHERE apptID = %s AND clinicID = %s
            """, (new_date, new_time, new_symptoms, appointment_id, clinic_id))
            conn.commit()
            flash('Appointment updated successfully!')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_appointments'))
        except mysql.connector.Error as e:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('Database error: ' + str(e))
            return redirect(url_for('admin_manage_appointment', appointment_id=appointment_id))

    cursor.close()
    conn.close()

    # Normalize appointment fields for template
    appt_for_template = {}
    if isinstance(appointment, dict):
        for k, v in appointment.items():
            if k in ('appointment_date', 'reportDate') and hasattr(v, 'strftime'):
                try:
                    appt_for_template[k] = v.strftime('%Y-%m-%d')
                except Exception:
                    appt_for_template[k] = str(v)
            elif k == 'appointment_time':
                if v is None:
                    appt_for_template[k] = None
                else:
                    if hasattr(v, 'strftime'):
                        appt_for_template[k] = v.strftime('%H:%M:%S')
                    elif hasattr(v, 'total_seconds'):
                        secs = int(v.total_seconds())
                        hh = secs // 3600
                        mm = (secs % 3600) // 60
                        ss = secs % 60
                        appt_for_template[k] = f"{hh:02d}:{mm:02d}:{ss:02d}"
                    else:
                        appt_for_template[k] = str(v)
            else:
                appt_for_template[k] = v
    else:
        appt_for_template = appointment

    return render_template('clinic_admin/ManageAppointmentAdmin.html', appointment=appt_for_template)

@app.route('/admin/delete-appointment', methods=['POST'])
def admin_delete_appointment():
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    
    appointment_id = request.form.get('appointment_id')
    if not appointment_id:
        flash('Please select an appointment to delete.', 'error')
        return redirect(url_for('admin_appointments'))
    
    clinic_id = session.get('clinicID')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # Verify appointment belongs to this clinic before deleting
    cursor.execute("SELECT apptID FROM appointments WHERE apptID = %s AND clinicID = %s", (appointment_id, clinic_id))
    appointment = cursor.fetchone()
    
    if not appointment:
        cursor.close()
        conn.close()
        flash('Appointment not found or access denied.', 'error')
        return redirect(url_for('admin_appointments'))
    
    try:
        cursor.execute("DELETE FROM appointments WHERE apptID = %s AND clinicID = %s", (appointment_id, clinic_id))
        conn.commit()
        flash('Appointment deleted successfully!', 'success')
    except mysql.connector.Error as e:
        conn.rollback()
        flash('Database error: ' + str(e), 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_appointments'))

# Clinic admin: manage the clinic metadata (city/province/postalCode)
@app.route('/admin/manage_clinic', methods=['GET', 'POST'])
def clinic_manage_clinic():
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))

    clinic_id = session.get('clinicID')
    if not clinic_id:
        flash('No clinic associated with your account.', 'warning')
        return redirect(url_for('admin_home'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        clinic_email = (request.form.get('clinicEmail') or '').strip()
        city = (request.form.get('city') or '').strip()
        province = (request.form.get('province') or '').strip()
        postal = (request.form.get('postalCode') or '').strip()

        try:
            cursor.execute("UPDATE clinic SET city=%s, province=%s, postalCode=%s WHERE clinicID = %s", (city, province, postal, clinic_id))
            cursor.execute("UPDATE clinicadmin SET email=%s WHERE clinicID = %s", (clinic_email, clinic_id))
            conn.commit()
            flash('Clinic updated successfully.', 'success')
        except Exception as e:
            conn.rollback()
            flash('Failed to update clinic: {}'.format(e), 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('clinic_manage_clinic'))

    # GET - Join clinic and clinicadmin to get both clinic info and email
    cursor.execute("""
        SELECT c.*, ca.email 
        FROM clinic c
        LEFT JOIN clinicadmin ca ON c.clinicID = ca.clinicID
        WHERE c.clinicID = %s
    """, (clinic_id,))
    clinic = cursor.fetchone()
    cursor.close()
    conn.close()

    if not clinic:
        flash('Clinic not found.', 'warning')
        return redirect(url_for('admin_home'))

    return render_template('clinic_admin/manage_clinic.html', clinic=clinic)

@app.route('/admin/manage_reports')
def admin_managereports():
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    
    # Automatically delete expired reports
    expired_count = delete_expired_reports()
    if expired_count > 0:
        flash(f"Automatically removed {expired_count} expired report(s).", "info")
        create_notification(event_type="REPORT_DELETED")

    
    clinic_id = session.get('clinicID')
    filter_by = request.args.get('filter', 'newest')  # Default to newest
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Determine ORDER BY clause based on filter
    if filter_by == 'oldest':
        order_clause = "ORDER BY r.reportDate ASC"
    elif filter_by == 'expiry':
        order_clause = "ORDER BY r.expiryDate ASC"
    else:  # newest (default)
        order_clause = "ORDER BY r.reportDate DESC"
    
    # Fetch all reports for the clinic
    query = f"""
        SELECT r.reportID, r.reportDate, r.expiryDate, r.files,
               p.firstName AS patientFirstName, p.lastName AS patientLastName,
               d.firstName AS doctorFirstName, d.lastName AS doctorLastName
        FROM Reports r
        JOIN patient p ON r.patientID = p.USERID
        JOIN doctor d ON r.doctorID = d.USERID
        WHERE p.clinicID = %s
        {order_clause}
    """
    cursor.execute(query, (clinic_id,))
    
    reports = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convert dates to datetime if they're strings
    for r in reports:
        if isinstance(r['reportDate'], str):
            try:
                r['reportDate'] = datetime.strptime(r['reportDate'], '%Y-%m-%d')
            except Exception:
                pass
        if isinstance(r.get('expiryDate'), str):
            try:
                r['expiryDate'] = datetime.strptime(r['expiryDate'], '%Y-%m-%d')
            except Exception:
                pass
    
    return render_template('/clinic_admin/ManageReports.html', reports=reports, filter_by=filter_by)

@app.route('/admin/book-appointment', methods=['GET', 'POST'])
def admin_book_appointment():
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    
    clinic_id = session.get('clinicID')

    if request.method == 'POST':
        # Collect form inputs
        patient_id = request.form.get('patient_id')
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        symptoms = request.form.get('symptoms')

        if not all([patient_id, doctor_id, appointment_date, appointment_time]):
            flash('Please fill in all required fields.')
            return redirect(url_for('admin_book_appointment'))

        # Normalize time (allow HH:MM or HH:MM:SS)
        if len(appointment_time) == 5:
            appointment_time = appointment_time + ':00'

        # Check for conflict (same doctor, same date/time)
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT apptID FROM appointments WHERE doctorID = %s AND appointment_date = %s AND appointment_time = %s", (doctor_id, appointment_date, appointment_time))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            flash('Selected time slot is not available for this doctor. Please choose another time.')
            return redirect(url_for('admin_book_appointment'))

        # Insert appointment
        try:
            cursor.execute("INSERT INTO appointments (patientID, appointment_date, appointment_time, doctorID, clinicID, symptoms) VALUES (%s, %s, %s, %s, %s, %s)", (patient_id, appointment_date, appointment_time, doctor_id, clinic_id, symptoms))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Appointment booked successfully!')
            return redirect(url_for('admin_appointments'))
        except mysql.connector.Error as e:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('Database error: ' + str(e))
            return redirect(url_for('admin_book_appointment'))

    # GET: Fetch patients and doctors from this clinic
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Fetch patients for this clinic
    cursor.execute("SELECT USERID, firstName, lastName FROM patient WHERE clinicID = %s ORDER BY lastName, firstName", (clinic_id,))
    patients = cursor.fetchall()
    
    # Fetch doctors for this clinic
    cursor.execute("SELECT USERID, firstName, lastName FROM doctor WHERE clinicID = %s ORDER BY lastName, firstName", (clinic_id,))
    doctors = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template('clinic_admin/BookAppointmentAdmin.html', patients=patients, doctors=doctors)

# Legacy route redirect
@app.route('/admin/manage_appointments/book_appointment')
def admin_bookAppointment():
    return redirect(url_for('admin_book_appointment'))


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('home'))

# Search functionality for all users
@app.route('/search')
def search():
    query = request.args.get('query', '').strip()
    user_type = session.get('userType')
    user_id = session.get('user_id')
    clinic_id = session.get('clinicID')

    # Map month names to numbers
    month_map = {month.lower(): index for index, month in enumerate(calendar.month_name) if month}
    query_lower = query.lower()
    month_num = None
    year_num = None

    # Extract month and year from query
    for name, num in month_map.items():
        if name in query_lower:
            month_num = num
            # Try to extract a 4-digit year near the month name
            match = re.search(rf"{name}\s+(\d{{4}})", query_lower)
            if match:
                year_num = int(match.group(1))
            else:
                # Try the other way around: "2023 March"
                match = re.search(rf"(\d{{4}})\s+{name}", query_lower)
                if match:
                    year_num = int(match.group(1))
            break

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # --- APPOINTMENTS ---
    if user_type == 'patient':
        if month_num and year_num:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE MONTH(a.appointment_date) = %s AND YEAR(a.appointment_date) = %s
                  AND a.patientID = %s
            """, (month_num, year_num, user_id))
        elif month_num:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE MONTH(a.appointment_date) = %s
                  AND a.patientID = %s
            """, (month_num, user_id))
        else:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE (a.symptoms LIKE %s OR a.appointment_date LIKE %s)
                  AND a.patientID = %s
            """, (f"%{query}%", f"%{query}%", user_id))
        appointments = cursor.fetchall()
    elif user_type == 'doctor':
        # Only appointments for this doctor
        if month_num and year_num:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE MONTH(a.appointment_date) = %s AND YEAR(a.appointment_date) = %s
                  AND a.doctorID = %s
            """, (month_num, year_num, user_id))
        elif month_num:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE MONTH(a.appointment_date) = %s
                  AND a.doctorID = %s
            """, (month_num, user_id))
        else:
            
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE (a.symptoms LIKE %s OR a.appointment_date LIKE %s OR p.firstName LIKE %s OR p.lastName LIKE %s)
                  AND a.doctorID = %s
            """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", user_id))
        appointments = cursor.fetchall()
    elif user_type == 'clinicadmin':
        # Only appointments for this clinic
        if month_num and year_num:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE MONTH(a.appointment_date) = %s AND YEAR(a.appointment_date) = %s
                  AND a.clinicID = %s
            """, (month_num, year_num, clinic_id))
        elif month_num:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE MONTH(a.appointment_date) = %s
                  AND a.clinicID = %s
            """, (month_num, clinic_id))
        else:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE (a.symptoms LIKE %s OR a.appointment_date LIKE %s OR p.firstName LIKE %s OR p.lastName LIKE %s)
                  AND a.clinicID = %s
            """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", clinic_id))
        appointments = cursor.fetchall()
    else:
        # Default: show all
        if month_num and year_num:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE MONTH(a.appointment_date) = %s AND YEAR(a.appointment_date) = %s
            """, (month_num, year_num))
        elif month_num:
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE MONTH(a.appointment_date) = %s
            """, (month_num,))
        else:
            
            cursor.execute("""
                SELECT a.apptID, a.patientID, a.appointment_date, a.appointment_time, a.doctorID, a.symptoms,
                       p.firstName, p.lastName
                FROM appointments a
                JOIN patient p ON a.patientID = p.USERID
                WHERE a.symptoms LIKE %s OR a.appointment_date LIKE %s OR p.firstName LIKE %s OR p.lastName LIKE %s
            """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
        appointments = cursor.fetchall()

    # --- REPORTS ---
    if user_type == 'patient':
        if month_num and year_num:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE MONTH(r.reportDate) = %s AND YEAR(r.reportDate) = %s AND r.patientID = %s
            """, (month_num, year_num, user_id))
        elif month_num:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE MONTH(r.reportDate) = %s AND r.patientID = %s
            """, (month_num, user_id))
        else:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE (
                    CAST(r.reportID AS CHAR) LIKE %s
                    OR CAST(r.patientID AS CHAR) LIKE %s
                    OR r.reportDate LIKE %s
                )
                AND r.patientID = %s
            """, (f"%{query}%", f"%{query}%", f"%{query}%", user_id))
        reports = cursor.fetchall()
    elif user_type == 'doctor':
        # Only reports for this doctor
        if month_num and year_num:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE MONTH(r.reportDate) = %s AND YEAR(r.reportDate) = %s AND r.doctorID = %s
            """, (month_num, year_num, user_id))
        elif month_num:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE MONTH(r.reportDate) = %s AND r.doctorID = %s
            """, (month_num, user_id))
        else:
          
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE (
                    CAST(r.reportID AS CHAR) LIKE %s
                    OR CAST(r.patientID AS CHAR) LIKE %s
                    OR r.reportDate LIKE %s
                    OR p.firstName LIKE %s
                    OR p.lastName LIKE %s
                )
                AND r.doctorID = %s
            """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", user_id))
        reports = cursor.fetchall()
    elif user_type == 'clinicadmin':
        # Only reports for this clinic 
        if month_num and year_num:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE MONTH(r.reportDate) = %s AND YEAR(r.reportDate) = %s AND p.clinicID = %s
            """, (month_num, year_num, clinic_id))
        elif month_num:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE MONTH(r.reportDate) = %s AND p.clinicID = %s
            """, (month_num, clinic_id))
        else:
        
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE (
                    CAST(r.reportID AS CHAR) LIKE %s
                    OR CAST(r.patientID AS CHAR) LIKE %s
                    OR r.reportDate LIKE %s
                    OR p.firstName LIKE %s
                    OR p.lastName LIKE %s
                )
                AND p.clinicID = %s
            """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", clinic_id))
        reports = cursor.fetchall()
    else:
        # Default: show all
        if month_num and year_num:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
               
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE MONTH(r.reportDate) = %s AND YEAR(r.reportDate) = %s
            """, (month_num, year_num))
        elif month_num:
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE MONTH(r.reportDate) = %s
            """, (month_num,))
        else:
            # Add patient name search for default
            cursor.execute("""
                SELECT r.reportID, r.patientID, r.doctorID, r.reportDate,
                       p.firstName AS patientFirstName, p.lastName AS patientLastName,
                       d.firstName AS doctorFirstName, d.lastName AS doctorLastName
                FROM Reports r
                JOIN patient p ON r.patientID = p.USERID
                JOIN doctor d ON r.doctorID = d.USERID
                WHERE
                    CAST(r.reportID AS CHAR) LIKE %s
                    OR CAST(r.patientID AS CHAR) LIKE %s
                    OR r.reportDate LIKE %s
                    OR p.firstName LIKE %s
                    OR p.lastName LIKE %s
            """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
        reports = cursor.fetchall()

    # --- PATIENTS (for doctor and clinicadmin) ---
    patients = []
    if user_type == 'doctor':
        cursor.execute("""
            SELECT USERID, firstName, lastName, email, phone, dateofbirth
            FROM patient
            WHERE firstName LIKE %s OR lastName LIKE %s OR email LIKE %s OR phone LIKE %s
        """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
        patients = cursor.fetchall()
    elif user_type == 'clinicadmin':
        cursor.execute("""
            SELECT USERID, firstName, lastName, email, phone, dateofbirth
            FROM patient
            WHERE clinicID = %s AND (
                firstName LIKE %s OR lastName LIKE %s OR email LIKE %s OR phone LIKE %s
            )
        """, (clinic_id, f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
        patients = cursor.fetchall()

    cursor.close()
    conn.close()

    results = {
        "appointments": appointments,
        "reports": reports,
        "patients": patients
    }

    # Pass userType and user info for dynamic navbar
    user_type = session.get('userType')
    username = session.get('username')
    first_name = session.get('firstName')
    last_name = session.get('lastName')
    return render_template(
        "search_results.html",
        query=query,
        results=results,
        user_type=user_type,
        username=username,
        first_name=first_name,
        last_name=last_name
    )

# Appointment route for linking search results to appointment page with ability to show details
@app.route('/patient/appointments/detail')
def p_appointments_search():
    apptID = request.args.get('apptID')
    if not apptID or session.get('userType') != 'patient':
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM appointments WHERE apptID = %s", (apptID,))
    appointment = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('patient/p_appointments.html', appointment=appointment)

# Appointment route for doctor to view appointment details on appointment page
@app.route('/doctor/appointments/detail')
def doctor_appointments_search():
    apptID = request.args.get('apptID')
    if not apptID or session.get('userType') != 'doctor':
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Fetch the specific appointment with patient info
    cursor.execute("""
        SELECT a.apptID, a.appointment_date, a.appointment_time, a.symptoms,
               p.firstName, p.lastName
        FROM appointments a
        JOIN patient p ON a.patientID = p.USERID
        WHERE a.apptID = %s
    """, (apptID,))
    appointment = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not appointment:
        flash('Appointment not found.')
        return redirect(url_for('doctor_appointments'))
    
    # Pass as a list containing only this appointment
    return render_template('doctor/doctor_appointments.html', appointments=[appointment])

# Appointment route for clinic admin to view appointment details on appointment page
@app.route('/admin/appointments/detail')
def admin_appointments_search():
    apptID = request.args.get('apptID')
    if not apptID or session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM appointments WHERE apptID = %s", (apptID,))
    appointment = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('clinic_admin/AppointmentAdmin.html', appointment=appointment)

# Report route for patient to view report details on reports page
@app.route('/patient/reports/detail')
def patient_reports_search():
    reportID = request.args.get('reportID')
    if not reportID or session.get('userType') != 'patient':
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Reports WHERE reportID = %s", (reportID,))
    report = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('patient/myreports.html', report=report)

# Report route for doctor to view report details on reports page
@app.route('/doctor/reports/detail')
def doctor_reports_search():
    reportID = request.args.get('reportID')
    if not reportID or session.get('userType') != 'doctor':
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Reports WHERE reportID = %s", (reportID,))
    report = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('doctor/doctor_reports.html', report=report)

# Report route for clinic admin to view report details on reports page
@app.route('/admin/reports/detail')
def admin_reports_search():
    reportID = request.args.get('reportID')
    if not reportID or session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.*, 
               p.firstName AS patientFirstName, p.lastName AS patientLastName,
               d.firstName AS doctorFirstName, d.lastName AS doctorLastName
        FROM Reports r
        JOIN patient p ON r.patientID = p.USERID
        JOIN doctor d ON r.doctorID = d.USERID
        WHERE r.reportID = %s
    """, (reportID,))
    report = cursor.fetchone()
    cursor.close()
    conn.close()
    if not report:
        flash("Report not found.", "danger")
        return redirect(url_for('admin_managereports'))
    return render_template('clinic_admin/ManageReports.html', report=report)

# Helper function to check and delete expired reports
def delete_expired_reports():
    """Delete all reports where expiryDate is before today's date."""
    today = date.today()
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Find expired reports
    cursor.execute("""
        SELECT reportID, expiryDate FROM Reports
        WHERE expiryDate < %s
    """, (today,))
    
    expired_reports = cursor.fetchall()
    count = len(expired_reports)
    
    if count > 0:
        # Delete expired reports
        cursor.execute("DELETE FROM Reports WHERE expiryDate < %s", (today,))
        conn.commit()
    
    cursor.close()
    conn.close()
    
    return count

# Helper function to check and delete expired messages
def delete_expired_messages():
    """Delete all messages where expiryDate is before today's date."""
    today = date.today()
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Find expired messages
    cursor.execute("""
        SELECT messageID, expiryDate FROM messages
        WHERE expiryDate < %s
    """, (today,))
    
    expired_messages = cursor.fetchall()
    count = len(expired_messages)
    
    if count > 0:
        # Delete expired messages
        cursor.execute("DELETE FROM messages WHERE expiryDate < %s", (today,))
        conn.commit()
    
    cursor.close()
    conn.close()
    
    return count

# Helper function to check and delete expired notifications
def delete_expired_notifications():
    """Delete all notifications where expiryDate is before today's date."""
    today = date.today()
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Find expired notifications
    cursor.execute("""
        SELECT notificationID, expiryDate FROM notifications
        WHERE expiryDate < %s
    """, (today,))
    
    expired_notifications = cursor.fetchall()
    count = len(expired_notifications)
    
    if count > 0:
        # Delete expired notifications
        cursor.execute("DELETE FROM notifications WHERE expiryDate < %s", (today,))
        conn.commit()
    
    cursor.close()
    conn.close()
    
    return count

# Admin route to manually trigger expired reports cleanup
@app.route('/admin/cleanup_expired_reports', methods=['POST'])
def admin_cleanup_expired_reports():
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    
    count = delete_expired_reports()
    
    if count > 0:
        flash(f"Successfully deleted {count} expired report(s).", "success")
    else:
        flash("No expired reports found.", "info")
    
    return redirect(url_for('admin_managereports'))

# Admin delete report route
@app.route('/admin/delete_report', methods=['POST'])
def admin_delete_report():
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    
    report_id = request.form.get('reportID')
    if not report_id:
        flash("Invalid report ID.", "danger")
        return redirect(url_for('admin_managereports'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Verify the report belongs to this clinic
    clinic_id = session.get('clinicID')
    cursor.execute("""
        SELECT r.reportID 
        FROM Reports r
        JOIN patient p ON r.patientID = p.USERID
        WHERE r.reportID = %s AND p.clinicID = %s
    """, (report_id, clinic_id))
    
    report = cursor.fetchone()
    if not report:
        flash("Report not found or access denied.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('admin_managereports'))
    
    # Delete the report
    cursor.execute("DELETE FROM Reports WHERE reportID = %s", (report_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Report deleted successfully.", "success")
    return redirect(url_for('admin_managereports'))

# Admin search reports route
@app.route('/admin/search_reports', methods=['GET'])
def admin_search_reports():
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    
    clinic_id = session.get('clinicID')
    query = request.args.get('query', '').strip()
    filter_by = request.args.get('filter', 'newest')  # Get filter parameter
    
    # Month name support
    month_map = {month.lower(): index for index, month in enumerate(calendar.month_name) if month}
    query_lower = query.lower()
    month_num = None
    year_num = None
    
    # Check if query contains a month name
    for name, num in month_map.items():
        if name in query_lower:
            month_num = num
            # Check for year with month (e.g., "April 2025" or "2025 April")
            match = re.search(rf"{name}\s+(\d{{4}})", query_lower)
            if match:
                year_num = int(match.group(1))
            else:
                match = re.search(rf"(\d{{4}})\s+{name}", query_lower)
                if match:
                    year_num = int(match.group(1))
            break
    
    # Determine ORDER BY clause based on filter
    if filter_by == 'oldest':
        order_clause = "ORDER BY r.reportDate ASC"
    elif filter_by == 'expiry':
        order_clause = "ORDER BY r.expiryDate ASC"
    else:  # newest (default)
        order_clause = "ORDER BY r.reportDate DESC"
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Search based on whether we found a month
    if month_num and year_num:
        # Search by month and year
        query_sql = f"""
            SELECT r.reportID, r.reportDate, r.expiryDate, r.files,
                   p.firstName AS patientFirstName, p.lastName AS patientLastName,
                   d.firstName AS doctorFirstName, d.lastName AS doctorLastName
            FROM Reports r
            JOIN patient p ON r.patientID = p.USERID
            JOIN doctor d ON r.doctorID = d.USERID
            WHERE p.clinicID = %s AND MONTH(r.reportDate) = %s AND YEAR(r.reportDate) = %s
            {order_clause}
        """
        cursor.execute(query_sql, (clinic_id, month_num, year_num))
    elif month_num:
        # Search by month only
        query_sql = f"""
            SELECT r.reportID, r.reportDate, r.expiryDate, r.files,
                   p.firstName AS patientFirstName, p.lastName AS patientLastName,
                   d.firstName AS doctorFirstName, d.lastName AS doctorLastName
            FROM Reports r
            JOIN patient p ON r.patientID = p.USERID
            JOIN doctor d ON r.doctorID = d.USERID
            WHERE p.clinicID = %s AND MONTH(r.reportDate) = %s
            {order_clause}
        """
        cursor.execute(query_sql, (clinic_id, month_num))
    else:
        # Regular text search in report ID, date, patient name, or doctor name
        query_sql = f"""
            SELECT r.reportID, r.reportDate, r.expiryDate, r.files,
                   p.firstName AS patientFirstName, p.lastName AS patientLastName,
                   d.firstName AS doctorFirstName, d.lastName AS doctorLastName
            FROM Reports r
            JOIN patient p ON r.patientID = p.USERID
            JOIN doctor d ON r.doctorID = d.USERID
            WHERE p.clinicID = %s AND (
                CAST(r.reportID AS CHAR) LIKE %s
                OR r.reportDate LIKE %s
                OR r.expiryDate LIKE %s
                OR p.firstName LIKE %s
                OR p.lastName LIKE %s
                OR d.firstName LIKE %s
                OR d.lastName LIKE %s
            )
            {order_clause}
        """
        cursor.execute(query_sql, (clinic_id, f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
    
    reports = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convert dates to datetime if they're strings
    for r in reports:
        if isinstance(r['reportDate'], str):
            try:
                r['reportDate'] = datetime.strptime(r['reportDate'], '%Y-%m-%d')
            except Exception:
                pass
        if isinstance(r.get('expiryDate'), str):
            try:
                r['expiryDate'] = datetime.strptime(r['expiryDate'], '%Y-%m-%d')
            except Exception:
                pass
    
    return render_template('/clinic_admin/ManageReports.html', reports=reports, filter_by=filter_by, query=query)


# Clinic admin: list / search / filter accounts
@app.route('/admin/ManageAccount', methods=['GET'])
def clinic_manage_accounts():
    # require clinic admin
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))

    clinic_id = session.get('clinicID') or session.get('clinic_id')
    query = (request.args.get('query') or '').strip()
    filt = request.args.get('filter', 'all')

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    accounts = []

    # Prepare search parameter
    q_param = None
    if query:
        q_param = f"%{query}%"

    # Fetch doctors when appropriate
    if filt in ('all', 'doctors'):
        sql_doc = "SELECT USERID AS id, 'doctor' AS userType, firstName, lastName, email FROM doctor WHERE 1=1"
        params_doc = []
        if clinic_id:
            sql_doc += " AND clinicID = %s"
            params_doc.append(clinic_id)
        if q_param:
            sql_doc += " AND (firstName LIKE %s OR lastName LIKE %s OR email LIKE %s)"
            params_doc.extend([q_param, q_param, q_param])
        sql_doc += " ORDER BY lastName, firstName"
        cursor.execute(sql_doc, tuple(params_doc))
        doctors = cursor.fetchall()
        accounts.extend(doctors)

    # Fetch patients when appropriate
    if filt in ('all', 'patients'):
        sql_pat = "SELECT USERID AS id, 'patient' AS userType, firstName, lastName, email FROM patient WHERE 1=1"
        params_pat = []
        if clinic_id:
            sql_pat += " AND clinicID = %s"
            params_pat.append(clinic_id)
        if q_param:
            sql_pat += " AND (firstName LIKE %s OR lastName LIKE %s OR email LIKE %s)"
            params_pat.extend([q_param, q_param, q_param])
        sql_pat += " ORDER BY lastName, firstName"
        cursor.execute(sql_pat, tuple(params_pat))
        patients = cursor.fetchall()
        accounts.extend(patients)

    # stable sort: by userType then lastName then firstName
    try:
        accounts = sorted(accounts, key=lambda x: (x.get('userType', ''), x.get('lastName', '').lower(), x.get('firstName', '').lower()))
    except Exception:
        pass

    cursor.close()
    conn.close()

    return render_template('clinic_admin/ManageAccount.html', accounts=accounts)


# Clinic admin: show/manage a single user (basic read/update)
@app.route('/admin/manage_user/<int:user_id>', methods=['GET', 'POST'])
def clinic_manage_user(user_id):
    if session.get('userType') != 'clinicadmin':
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # POST: update appropriate table
    if request.method == 'POST':
        # Collect common fields
        utype = (request.form.get('userType') or '').strip().lower()
        first = (request.form.get('firstName') or '').strip()
        last = (request.form.get('lastName') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''

        try:
            if utype == 'patient':
                phone = request.form.get('phoneNumber') or None
                birthday = request.form.get('birthday') or None
                address = request.form.get('address') or None
                city = request.form.get('city') or None
                province = request.form.get('province') or None
                postal = request.form.get('postalCode') or None
                insurance = request.form.get('insurance') or None

                cursor.execute("""
                    UPDATE patient SET firstName=%s, lastName=%s, dateofbirth=%s, address=%s, city=%s, province=%s, postalCode=%s, phone=%s, email=%s, insurance=%s
                    WHERE USERID=%s
                """, (first, last, birthday, address, city, province, postal, phone, email, insurance, user_id))

                # Update login username/password if provided
                if password:
                    cursor.execute("UPDATE login SET username=%s, password=%s WHERE USERID=%s", (email, password, user_id))
                else:
                    cursor.execute("UPDATE login SET username=%s WHERE USERID=%s", (email, user_id))

            elif utype == 'doctor':
                phone = request.form.get('phoneNumber') or None

                # Update doctor record 
                cursor.execute("""
                    UPDATE doctor SET firstName=%s, lastName=%s, email=%s, phone=%s
                    WHERE USERID=%s
                """, (first, last, email, phone, user_id))

                # Keep login username/password in sync if provided
                if password:
                    cursor.execute("UPDATE login SET username=%s, password=%s WHERE USERID=%s", (email, password, user_id))
                else:
                    cursor.execute("UPDATE login SET username=%s WHERE USERID=%s", (email, user_id))

            else:
                flash('Unknown user type.', 'warning')
                cursor.close()
                conn.close()
                return redirect(url_for('clinic_manage_accounts'))

            conn.commit()
            flash('Account updated.', 'success')
        except Exception as e:
            conn.rollback()
            flash('Failed to update account: {}'.format(e), 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('clinic_manage_accounts'))

    # GET: try doctor then patient - fetch full row so templates can prefill all fields
    cursor.execute("SELECT * FROM doctor WHERE USERID = %s", (user_id,))
    account = cursor.fetchone()
    if account:
        # normalize keys for template
        account['id'] = account.get('USERID')
        account['userType'] = 'doctor'
    else:
        cursor.execute("SELECT * FROM patient WHERE USERID = %s", (user_id,))
        account = cursor.fetchone()
        if account:
            account['id'] = account.get('USERID')
            account['userType'] = 'patient'

    cursor.close()
    conn.close()

    if not account:
        flash('User not found.', 'warning')
        return redirect(url_for('clinic_manage_accounts'))

    # Render a type-specific manage page for better editing
    if account.get('userType') == 'doctor':
        return render_template('clinic_admin/manage_doctor.html', account=account)
    else:
        return render_template('clinic_admin/manage_patient.html', account=account)


# Clinic admin: delete user
@app.route('/admin/delete_user', methods=['POST'])
def clinic_delete_user():
    if session.get('userType') != 'clinic_admin':
        return redirect(url_for('login'))
    user_id = request.form.get('user_id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        flash('Invalid user id.', 'warning')
        return redirect(url_for('clinic_manage_accounts'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    try:
        # check doctor table
        cursor.execute("SELECT USERID FROM doctor WHERE USERID = %s", (user_id,))
        if cursor.fetchone():
            cursor.execute("DELETE FROM doctor WHERE USERID = %s", (user_id,))
        else:
            cursor.execute("SELECT USERID FROM patient WHERE USERID = %s", (user_id,))
            if cursor.fetchone():
                cursor.execute("DELETE FROM patient WHERE USERID = %s", (user_id,))
            else:
                flash('Account not found.', 'warning')
                cursor.close()
                conn.close()
                return redirect(url_for('clinic_manage_accounts'))

        # Also remove login entry if exists
        try:
            cursor.execute("DELETE FROM login WHERE USERID = %s", (user_id,))
        except Exception:
            pass

        conn.commit()
        flash('Account deleted.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Failed to delete account: {}'.format(e), 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('clinic_manage_accounts'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)