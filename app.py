import os
import logging
import secrets
import base64
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Database setup
class Base(DeclarativeBase):
    pass

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_key_for_demo")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Ensure the instance folder exists when the app is initialized
# This is where the SQLite DB will be stored.
try:
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path)
    app.logger.info(f"Instance path set to: {app.instance_path}")
except OSError as e:
    app.logger.error(f"Error creating instance folder at {app.instance_path}: {e}")

# Add template filters
@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    if fmt:
        return date.strftime(fmt)
    else:
        return date.strftime('%Y-%m-%d %H:%M:%S')

@app.template_filter('datetime')
def _jinja2_filter_pretty_datetime(date, fmt=None):
    if fmt:
        return date.strftime(fmt)
    else:
        return date.strftime('%d %b %Y, %H:%M')

# Database configuration
# Construct the SQLite path using app.instance_path for Render compatibility
sqlite_db_path = os.path.join(app.instance_path, 'local_test.db')
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_db_path}"
app.logger.info(f"SQLite database URI set to: {app.config['SQLALCHEMY_DATABASE_URI']}")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    'pool_pre_ping': True,
    "pool_recycle": 300,
}

# Init SQLAlchemy
db = SQLAlchemy(app, model_class=Base)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Basic routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.userType == 'resident':
            return redirect(url_for('resident_dashboard'))
        elif current_user.userType == 'leader':
            return redirect(url_for('leader_dashboard'))
        elif current_user.userType == 'police':
            return redirect(url_for('police_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullName = request.form.get('fullName')
        email = request.form.get('email')
        password = request.form.get('password')
        userType = request.form.get('userType')
        
        # Check if user already exists
        from models import User
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists.', 'danger')
            return render_template('register.html')
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(fullName=fullName, email=email, password=hashed_password, userType=userType)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            
            # Log in the new user
            login_user(new_user)
            
            # Redirect based on user type
            if userType == 'resident':
                return redirect(url_for('resident_form'))
            elif userType == 'leader':
                return redirect(url_for('leader_form'))
            elif userType == 'police':
                return redirect(url_for('police_form'))
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('register.html')

@app.route('/resident_form', methods=['GET', 'POST'])
@login_required
def resident_form():
    # Ensure user is a resident
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        from models import ResidentInfo, AddressApplication
        
        try:
            # Get form data with defaults to prevent errors
            firstName = request.form.get('firstName', '')
            lastName = request.form.get('lastName', '')
            idNumber = request.form.get('idNumber', '')
            phoneNumber = request.form.get('phoneNumber', '')
            settlement = request.form.get('settlement', '')
            unitNumber = request.form.get('unitNumber', '')
            postalCode = request.form.get('postalCode', '')
            isOwner = True if request.form.get('isOwner') == 'yes' else False
            municipality = request.form.get('municipality', '')
            wardNumber = request.form.get('wardNumber', '1')
            councillorName = request.form.get('councillorName', '')
            
            # Check if resident info already exists
            existing_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
            
            if existing_info:
                # Update existing record
                existing_info.firstName = firstName
                existing_info.lastName = lastName
                existing_info.idNumber = idNumber
                existing_info.phoneNumber = phoneNumber
                existing_info.settlement = settlement
                existing_info.unitNumber = unitNumber
                existing_info.postalCode = postalCode
                existing_info.isOwner = isOwner
                existing_info.municipality = municipality
                try:
                    existing_info.wardNumber = int(wardNumber)
                except ValueError:
                    existing_info.wardNumber = 1
                existing_info.councillorName = councillorName
                existing_info.idPhotoPath = '/static/uploads/id_photos/demo_id.jpg'
            else:
                # Create new resident info
                resident_info = ResidentInfo(
                    user_id=current_user.id,
                    firstName=firstName,
                    lastName=lastName,
                    idNumber=idNumber,
                    phoneNumber=phoneNumber,
                    settlement=settlement,
                    unitNumber=unitNumber,
                    postalCode=postalCode,
                    isOwner=isOwner,
                    municipality=municipality,
                    wardNumber=int(wardNumber) if wardNumber.isdigit() else 1,
                    councillorName=councillorName
                )
                db.session.add(resident_info)
                
                # Store the ID photo path (in a real app, would handle file upload)
                resident_info.idPhotoPath = '/static/uploads/id_photos/demo_id.jpg'
            
            # Check if application already exists
            existing_application = AddressApplication.query.filter_by(applicant_id=current_user.id).first()
            
            if not existing_application:
                # Create address application
                application = AddressApplication(
                    applicant_id=current_user.id,
                    status='pending'
                )
                db.session.add(application)
            
            # Commit all changes
            db.session.commit()
            
            # Always redirect to verification after successful submission
            return redirect(url_for('verification'))
        except Exception as e:
            db.session.rollback()
            print(f"Error in resident_form: {str(e)}")
            flash(f'Error saving information: {str(e)}', 'danger')
            # Despite error, proceed to verification for the demo
            return redirect(url_for('verification'))
    
    return render_template('resident_form.html')

@app.route('/leader_form', methods=['GET', 'POST'])
@login_required
def leader_form():
    # Ensure user is a leader
    if current_user.userType != 'leader':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        from models import LeaderInfo
        
        try:
            # Get form data with defaults to prevent errors
            firstName = request.form.get('firstName', '')
            lastName = request.form.get('lastName', '')
            idNumber = request.form.get('idNumber', '')
            phoneNumber = request.form.get('phoneNumber', '')
            municipality = request.form.get('municipality', '')
            wardNumber = request.form.get('wardNumber', '1')
            officeLocation = request.form.get('officeLocation', '')
            settlement = request.form.get('settlement', '')
            unitNumber = request.form.get('unitNumber', '')
            postalCode = request.form.get('postalCode', '')
            
            # Check if leader info already exists
            existing_info = LeaderInfo.query.filter_by(user_id=current_user.id).first()
            
            if existing_info:
                # Update existing record
                existing_info.firstName = firstName
                existing_info.lastName = lastName
                existing_info.idNumber = idNumber
                existing_info.phoneNumber = phoneNumber
                existing_info.municipality = municipality
                try:
                    existing_info.wardNumber = int(wardNumber)
                except ValueError:
                    existing_info.wardNumber = 1
                existing_info.officeLocation = officeLocation
                existing_info.settlement = settlement
                existing_info.unitNumber = unitNumber
                existing_info.postalCode = postalCode
                existing_info.idPhotoPath = '/static/uploads/id_photos/demo_id.jpg'
            else:
                # Create new leader info
                leader_info = LeaderInfo(
                    user_id=current_user.id,
                    firstName=firstName,
                    lastName=lastName,
                    idNumber=idNumber,
                    phoneNumber=phoneNumber,
                    municipality=municipality,
                    wardNumber=int(wardNumber) if wardNumber.isdigit() else 1,
                    officeLocation=officeLocation,
                    settlement=settlement,
                    unitNumber=unitNumber,
                    postalCode=postalCode
                )
                db.session.add(leader_info)
                
                # Store the ID photo path (in a real app, would handle file upload)
                leader_info.idPhotoPath = '/static/uploads/id_photos/demo_id.jpg'
            
            # Commit all changes
            db.session.commit()
            
            # Always redirect to verification after successful submission
            return redirect(url_for('verification'))
        except Exception as e:
            db.session.rollback()
            print(f"Error in leader_form: {str(e)}")
            flash(f'Error saving information: {str(e)}', 'danger')
            # Despite error, proceed to verification for the demo
            return redirect(url_for('verification'))
    
    return render_template('leader_form.html')

@app.route('/police_form', methods=['GET', 'POST'])
@login_required
def police_form():
    # Ensure user is a police officer
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        from models import PoliceInfo
        
        try:
            # Get form data with defaults to prevent errors
            firstName = request.form.get('firstName', '')
            lastName = request.form.get('lastName', '')
            # idNumber is no longer required for police officers
            idNumber = "Not Required"  # Default value since field is not in the form
            phoneNumber = request.form.get('phoneNumber', '')
            badgeNumber = request.form.get('badgeNumber', '')
            rank = request.form.get('rank', '')
            stationName = request.form.get('stationName', '')
            municipality = request.form.get('municipality', '')
            postalCode = request.form.get('postalCode', '')
            
            # Check if police info already exists
            existing_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
            
            if existing_info:
                # Update existing record
                existing_info.firstName = firstName
                existing_info.lastName = lastName
                existing_info.idNumber = idNumber
                existing_info.phoneNumber = phoneNumber
                existing_info.badgeNumber = badgeNumber
                existing_info.rank = rank
                existing_info.stationName = stationName
                existing_info.municipality = municipality
                existing_info.postalCode = postalCode
                existing_info.idPhotoPath = '/static/uploads/id_photos/demo_id.jpg'
            else:
                # Create new police info
                police_info = PoliceInfo(
                    user_id=current_user.id,
                    firstName=firstName,
                    lastName=lastName,
                    idNumber=idNumber,
                    phoneNumber=phoneNumber,
                    badgeNumber=badgeNumber,
                    rank=rank,
                    stationName=stationName,
                    municipality=municipality,
                    postalCode=postalCode
                )
                db.session.add(police_info)
                
                # Store the ID photo path (in a real app, would handle file upload)
                police_info.idPhotoPath = '/static/uploads/id_photos/demo_id.jpg'
            
            # Commit all changes
            db.session.commit()
            
            # Always redirect to verification after successful submission
            return redirect(url_for('verification'))
        except Exception as e:
            db.session.rollback()
            print(f"Error in police_form: {str(e)}")
            flash(f'Error saving information: {str(e)}', 'danger')
            # Despite error, proceed to verification for the demo
            return redirect(url_for('verification'))
    
    return render_template('police_form.html')

@app.route('/verification', methods=['GET', 'POST'])
@login_required
def verification():
    if request.method == 'POST':
        try:
            # Check if face image data was provided
            face_image_data = request.form.get('face_image_data')
            skip_verification = request.form.get('skip_verification')
            
            # In a real app, we would process the face_image_data and store it
            # For the demo, just simulate successful verification
            if current_user.userType == 'resident':
                # Residents are immediately verified for the demo
                current_user.isVerified = True
                
                # If there's a resident_info record, store the face photo path
                resident_info_record = current_user.resident_info.first() # Get the first ResidentInfo record
                if resident_info_record:
                    resident_info_record.facePhotoPath = '/static/uploads/face_photos/demo_face.jpg'
            
            elif current_user.userType == 'leader':
                # Leaders need approval - set to not verified initially
                current_user.isVerified = True # Changed to True for testing
                
                # Store the face photo path
                if current_user.leader_info:
                    current_user.leader_info.facePhotoPath = '/static/uploads/face_photos/demo_face.jpg'
                    # Also mark as not approved initially
                    current_user.leader_info.isApproved = True # Changed to True for testing
            
            elif current_user.userType == 'police':
                # Police need approval - set to not verified initially
                current_user.isVerified = True # Changed to True for testing
                
                # Store the face photo path
                if current_user.police_info:
                    current_user.police_info.facePhotoPath = '/static/uploads/face_photos/demo_face.jpg'
                    # Also mark as not approved initially
                    current_user.police_info.isApproved = True # Changed to True for testing
            
            db.session.commit()
            
            print(f"User {current_user.id} verification processing complete")
            return redirect(url_for('confirmation'))
        except Exception as e:
            print(f"Error in verification: {str(e)}")
            # For demo only, still proceed to confirmation
            return redirect(url_for('confirmation'))
    
    # All users must go through camera verification - no auto-submit
    return render_template('verification.html', auto_submit=False)

@app.route('/confirmation')
@login_required
def confirmation():
    # Get appropriate user info based on user type
    user_data = {
        'fullName': current_user.fullName,
        'email': current_user.email,
        'userType': current_user.userType,
        'isVerified': current_user.isVerified
    }
    
    # Get additional info based on user type
    if current_user.userType == 'resident':
        info = current_user.resident_info.first() # Fetch the actual ResidentInfo object
        if info: # Check if info is not None
            user_data.update({
                'firstName': info.firstName,
                'lastName': info.lastName,
                'idNumber': info.idNumber,
                'settlement': info.settlement,
                'municipality': info.municipality
            })
    elif current_user.userType == 'leader' and current_user.leader_info:
        info = current_user.leader_info
        user_data.update({
            'firstName': info.firstName,
            'lastName': info.lastName,
            'idNumber': info.idNumber,
            'municipality': info.municipality,
            'wardNumber': info.wardNumber
        })
    elif current_user.userType == 'police' and current_user.police_info:
        info = current_user.police_info
        user_data.update({
            'firstName': info.firstName,
            'lastName': info.lastName,
            'idNumber': info.idNumber,
            'badgeNumber': info.badgeNumber,
            'rank': info.rank,
            'stationName': info.stationName
        })
    
    return render_template('confirmation.html', user_data=user_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('loginEmail')
        password = request.form.get('loginPassword')
        
        # Find user by email
        from models import User
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            # Login successful
            login_user(user)
            
            # Generate and store a "2FA code" (for demo purposes)
            # In a real app, this would be sent via SMS/email
            twofa_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
            session['twofa_code'] = twofa_code
            
            # For demo, we'll just verify the code without actually sending it
            # In production, this would require a separate verification step
            
            # Redirect based on user type and verification status
            if user.userType == 'resident':
                # Residents can access their dashboard
                return redirect(url_for('resident_dashboard'))
            elif user.userType == 'leader':
                # Check if leader is approved
                if user.leader_info and user.leader_info.isApproved:
                    return redirect(url_for('leader_dashboard'))
                else:
                    flash('Your leader account is pending approval.', 'warning')
                    return redirect(url_for('index'))
            elif user.userType == 'police':
                # Check if police officer is approved
                if user.police_info and user.police_info.isApproved:
                    return redirect(url_for('police_dashboard'))
                else:
                    flash('Your police officer account is pending approval.', 'warning')
                    return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Dashboard routes
@app.route('/resident/dashboard')
@login_required
def resident_dashboard():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication, Appointment, AddressCertificate
    
    # Get the resident's information
    resident_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
    
    # Get the most recent approved application, if any
    approved_application = AddressApplication.query.filter_by(
        applicant_id=current_user.id,
        status='approved'
    ).order_by(AddressApplication.updated_at.desc()).first()
    
    # Get the certificate for the approved application, if any
    certificate = None
    if approved_application:
        certificate = AddressCertificate.query.filter_by(
            application_id=approved_application.id
        ).first()
    
    # Check if there's a pending application
    pending_application = AddressApplication.query.filter(
        AddressApplication.applicant_id == current_user.id,
        AddressApplication.status.in_(['pending', 'leader_approved', 'interview_scheduled', 'interview_completed'])
    ).order_by(AddressApplication.created_at.desc()).first()
    
    # Get the most recent appointment, if any
    appointment = None
    if pending_application:
        appointment = Appointment.query.filter_by(application_id=pending_application.id).first()
    
    return render_template(
        'resident/dashboard.html',
        resident_info=resident_info,
        approved_application=approved_application,
        pending_application=pending_application,
        appointment=appointment,
        certificate=certificate
    )

@app.route('/resident/application-status')
@login_required
def resident_application_status():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication, Appointment, AddressCertificate
    
    # Get the resident's information
    resident_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
    
    # Get the most recent approved application, if any
    approved_application = AddressApplication.query.filter_by(
        applicant_id=current_user.id,
        status='approved'
    ).order_by(AddressApplication.updated_at.desc()).first()
    
    # Get the certificate for the approved application, if any
    certificate = None
    if approved_application:
        certificate = AddressCertificate.query.filter_by(
            application_id=approved_application.id
        ).first()
    
    # Check if there's a pending application
    pending_application = AddressApplication.query.filter(
        AddressApplication.applicant_id == current_user.id,
        AddressApplication.status.in_(['pending', 'leader_approved', 'interview_scheduled', 'interview_completed'])
    ).order_by(AddressApplication.created_at.desc()).first()
    
    # Get the most recent appointment, if any
    appointment = None
    if pending_application:
        appointment = Appointment.query.filter_by(application_id=pending_application.id).first()
    
    return render_template(
        'resident/application_status.html',
        resident_info=resident_info,
        approved_application=approved_application,
        pending_application=pending_application,
        appointment=appointment,
        certificate=certificate
    )

@app.route('/resident/schedule-interview', methods=['GET', 'POST'])
@login_required
def resident_schedule_interview():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication, Appointment, AvailableTimeSlot, User, AddressCertificate
    import uuid
    
    # Get the resident's information
    resident_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
    
    # Check if there's a pending application with leader_approved status or any pending application
    leader_approved_application = AddressApplication.query.filter(
        AddressApplication.applicant_id == current_user.id,
        AddressApplication.status == 'leader_approved'
    ).order_by(AddressApplication.created_at.desc()).first()
    
    # Get the most recent pending application regardless of status for displaying in the template
    any_pending_application = AddressApplication.query.filter(
        AddressApplication.applicant_id == current_user.id,
        AddressApplication.status.in_(['pending', 'leader_approved', 'interview_scheduled', 'interview_completed'])
    ).order_by(AddressApplication.created_at.desc()).first()
    
    # Can only schedule if the application status is leader_approved
    if not leader_approved_application:
        flash('You can only schedule an interview after your application has been approved by the community leader.', 'warning')
        return redirect(url_for('resident_dashboard'))
        
    # Set the pending_application to the leader_approved one for scheduling
    pending_application = leader_approved_application
    
    # Check if the interview is already scheduled
    existing_appointment = Appointment.query.filter_by(application_id=pending_application.id).first()
    if existing_appointment:
        flash('You already have a scheduled interview.', 'info')
        return redirect(url_for('resident_application_status'))
    
    # Handle GET request with location parameters to show specific location's slots
    from datetime import datetime, timedelta
    
    selected_location = None
    selected_slots = []
    
    # Check if location parameters were provided in the GET request
    if request.method == 'GET':
        municipality = request.args.get('municipality')
        station_name = request.args.get('station_name')
        postal_code = request.args.get('postal_code')
        
        if municipality and station_name and postal_code:
            # User selected a location, show available slots for that location
            selected_location = {
                'municipality': municipality,
                'station_name': station_name,
                'postal_code': postal_code
            }
            
            # Get available slots for the selected location
            selected_slots = AvailableTimeSlot.query.filter(
                AvailableTimeSlot.is_booked == False,
                AvailableTimeSlot.start_time > datetime.now(),
                AvailableTimeSlot.municipality == municipality,
                AvailableTimeSlot.station_name == station_name,
                AvailableTimeSlot.postal_code == postal_code
            ).order_by(AvailableTimeSlot.start_time).all()
            
            app.logger.info(f"Found {len(selected_slots)} slots for location: {municipality}, {station_name}, {postal_code}")
    
    # Handle POST request for scheduling an interview
    if request.method == 'POST':
        slot_id = request.form.get('slot_id')
        
        if not slot_id:
            flash('Please select a time slot.', 'warning')
            return redirect(url_for('resident_schedule_interview'))
        
        # Get the selected time slot
        time_slot = AvailableTimeSlot.query.get(slot_id)
        
        if not time_slot or time_slot.is_booked:
            flash('The selected time slot is no longer available.', 'danger')
            return redirect(url_for('resident_schedule_interview'))
        
        # Create a new appointment - FOR TESTING PURPOSES, mark as completed immediately
        appointment = Appointment(
            resident_id=current_user.id,
            officer_id=time_slot.officer_id,
            application_id=pending_application.id,
            appointment_date=time_slot.start_time,
            duration_minutes=30,
            status='completed'  # Auto-complete for testing
        )
        
        # Mark the time slot as booked
        time_slot.is_booked = True
        
        # For testing: Auto-approve application (skip interview)
        pending_application.status = 'approved'
        pending_application.officer_id = time_slot.officer_id
        pending_application.officer_notes = "Auto-approved for testing purposes"
        
        # Create a certificate immediately for testing
        certificate_number = f"AM-{uuid.uuid4().hex[:8].upper()}"
        issue_date = datetime.now()
        expiry_date = issue_date + timedelta(days=365)  # Valid for 1 year
        
        certificate = AddressCertificate(
            application_id=pending_application.id,
            certificate_number=certificate_number,
            issue_date=issue_date,
            expiry_date=expiry_date,
            pdf_path='/static/certificates/demo_certificate.pdf'  # Demo path
        )
        
        # Save changes to database
        try:
            db.session.add(appointment)
            db.session.add(certificate)
            db.session.commit()
            flash('Interview scheduled and automatically approved for testing! You may now download your address certificate.', 'success')
        except Exception as e:
            app.logger.error(f"Error booking interview: {str(e)}")
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            
        return redirect(url_for('resident_application_status'))
    
    # GET request - show available time slots grouped by location
    from datetime import datetime
    from sqlalchemy import func
    
    # Get available time slots from police officers that are in the future
    available_slots = AvailableTimeSlot.query.filter(
        AvailableTimeSlot.is_booked == False,
        AvailableTimeSlot.start_time > datetime.now()
    ).order_by(AvailableTimeSlot.start_time).all()
    
    # Get all unique locations where interviews are available
    # This is for location-based scheduling - users select a location first, not an officer
    import logging
    from sqlalchemy import func
    
    try:
        locations = db.session.query(
            AvailableTimeSlot.municipality,
            AvailableTimeSlot.station_name,
            AvailableTimeSlot.postal_code,
            func.count(AvailableTimeSlot.id).label('slot_count')
        ).filter(
            AvailableTimeSlot.is_booked == False,
            AvailableTimeSlot.start_time > datetime.now(),
            AvailableTimeSlot.municipality != None,  # Ensure location data exists
            AvailableTimeSlot.station_name != None,
            AvailableTimeSlot.postal_code != None
        ).group_by(
            AvailableTimeSlot.municipality,
            AvailableTimeSlot.station_name,
            AvailableTimeSlot.postal_code
        ).all()
        
        logging.info(f"Found {len(locations)} unique locations with available slots")
        for loc in locations:
            logging.info(f"Available location: {loc.municipality}, {loc.station_name}, {loc.postal_code}, slots: {loc.slot_count}")
    except Exception as e:
        logging.error(f"Error getting location data: {str(e)}")
        locations = []
    
    # Get officer information for selected slots (if any) 
    # Officer identity is hidden until after booking for privacy and security
    # Just collect minimal required info
    if selected_slots:
        for slot in selected_slots:
            try:
                officer = User.query.get(slot.officer_id)
                # We don't use officer name in the UI until after booking, so this is just for record keeping
                slot.officer_name = officer.fullName if officer else "Unknown Officer"
            except Exception as e:
                logging.error(f"Error getting officer info for slot {slot.id}: {str(e)}")
                slot.officer_name = "Unknown Officer"
    
    return render_template(
        'resident/schedule_interview.html',
        resident_info=resident_info,
        application=pending_application,  # For checking leader_approved status
        pending_application=any_pending_application,  # For displaying any pending application
        selected_location=selected_location,
        selected_slots=selected_slots,
        locations=locations
    )

@app.route('/resident/proof-of-address')
@login_required
def resident_proof_of_address():
    # Ensure only residents can access this page
    if current_user.userType != 'resident':
        flash('Access denied. Only residents can view address certificates.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication, AddressCertificate
    
    # Get the resident's information
    resident_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
    
    # Get the most recent approved application, if any
    approved_application = AddressApplication.query.filter_by(
        applicant_id=current_user.id,
        status='approved'
    ).order_by(AddressApplication.updated_at.desc()).first()
    
    # Get the certificate for the approved application, if any
    certificate = None
    if approved_application:
        certificate = AddressCertificate.query.filter_by(
            application_id=approved_application.id
        ).first()
    
    # If there's no certificate, let them view the page anyway instead of redirecting
    # This allows them to see the "not available" message
    
    return render_template(
        'resident/proof_of_address.html',
        resident_info=resident_info,
        approved_application=approved_application,
        certificate=certificate
    )

@app.route('/resident/download-certificate/<int:certificate_id>')
@login_required
def download_certificate(certificate_id):
    # Strict access control - only residents can download their certificates
    if current_user.userType != 'resident':
        flash('Access denied. Only residents can download address certificates.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication, AddressCertificate
    import io
    from flask import send_file
    from datetime import datetime
    
    # Find the certificate and ensure it belongs to the current user
    certificate = AddressCertificate.query.filter_by(id=certificate_id).first()
    
    if not certificate:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('resident_proof_of_address'))
    
    # Verify this belongs to the current user
    application = AddressApplication.query.filter_by(id=certificate.application_id).first()
    if not application or application.applicant_id != current_user.id:
        flash('Access denied. You can only access your own certificates.', 'danger')
        return redirect(url_for('resident_proof_of_address'))
    
    # Get resident info for the certificate
    resident_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
    
    # Generate PDF content
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        # Create a file-like buffer to receive PDF data
        buffer = io.BytesIO()
        
        # Create the PDF document using ReportLab
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        title_style.alignment = 1  # Center alignment
        subtitle_style = styles['Heading2']
        subtitle_style.alignment = 1
        normal_style = styles['Normal']
        
        # Create custom styles
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=14,
            alignment=1,
            spaceAfter=10
        )
        
        # Create content elements
        elements = []
        
        # Title
        elements.append(Paragraph("ADDRESS VERIFICATION CERTIFICATE", title_style))
        elements.append(Spacer(1, 20))
        
        # Logo placeholder
        elements.append(Paragraph("AddressMe", header_style))
        elements.append(Paragraph("Official Proof of Address Certificate", subtitle_style))
        elements.append(Spacer(1, 20))
        
        # Certificate information
        data = [
            ["Certificate Number:", certificate.certificate_number],
            ["Full Name:", f"{resident_info.firstName} {resident_info.lastName}"],
            ["ID Number:", resident_info.idNumber],
            ["Verified Address:", f"Unit {resident_info.unitNumber}, {resident_info.settlement}"],
            ["", f"{resident_info.municipality}"],
            ["", resident_info.postalCode],
            ["Verification Date:", certificate.issue_date.strftime("%d %B %Y")],
            ["Valid Until:", certificate.expiry_date.strftime("%d %B %Y")]
        ]
        
        # Create table with the data
        table = Table(data, colWidths=[150, 350])
        
        # Apply styles to the table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (1, 0), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 30))
        
        # Verification information
        elements.append(Paragraph("This certificate can be verified online at www.addressme.co.za/verify", normal_style))
        elements.append(Paragraph(f"using the certificate number: {certificate.certificate_number}", normal_style))
        
        # Build the PDF document
        doc.build(elements)
        
        # Set the file pointer to the beginning of the buffer
        buffer.seek(0)
        
        # Generate filename based on certificate number
        filename = f"AddressMe_Certificate_{certificate.certificate_number}.pdf"
        
        # Send the PDF as a downloadable attachment
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        # Log the error for debugging
        print(f"Error generating PDF: {str(e)}")
        flash('There was an error generating your certificate. Please try again later.', 'danger')
        return redirect(url_for('resident_proof_of_address'))

@app.route('/resident/email-certificate/<int:certificate_id>', methods=['POST'])
@login_required
def email_certificate(certificate_id):
    # Strict access control - only residents can email their certificates
    if current_user.userType != 'resident':
        flash('Access denied. Only residents can email address certificates.', 'danger') 
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication, AddressCertificate
    
    # Extract form data
    recipient_email = request.form.get('recipient_email')
    email_message = request.form.get('email_message', '')
    send_copy = 'send_copy' in request.form
    
    # Validate recipient email
    if not recipient_email:
        flash('Please provide a recipient email address.', 'danger')
        return redirect(url_for('resident_proof_of_address'))
    
    # Find the certificate and ensure it belongs to the current user
    certificate = AddressCertificate.query.filter_by(id=certificate_id).first()
    
    if not certificate:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('resident_proof_of_address'))
    
    # Verify this belongs to the current user
    application = AddressApplication.query.filter_by(id=certificate.application_id).first()
    if not application or application.applicant_id != current_user.id:
        flash('Access denied. You can only access your own certificates.', 'danger')
        return redirect(url_for('resident_proof_of_address'))
    
    # Since this is a demo, we'll simulate email sending
    try:
        # Log the email details for demonstration purposes
        print(f"[DEMO EMAIL] Certificate #{certificate.certificate_number} would be sent to: {recipient_email}")
        if send_copy:
            print(f"[DEMO EMAIL] Copy would be sent to: {current_user.email}")
        if email_message:
            print(f"[DEMO EMAIL] Message: {email_message}")
            
        # Display success message
        flash(f'Demo Mode: Certificate would be emailed to {recipient_email}. In a real application, the email would be sent with the certificate attached.', 'success')
        return redirect(url_for('resident_proof_of_address'))
        
    except Exception as e:
        # Log the error
        print(f"Error sending email: {str(e)}")
        flash('There was an error sending your certificate. Please try again later.', 'danger')
        return redirect(url_for('resident_proof_of_address'))

@app.route('/resident/profile-settings', methods=['GET', 'POST'])
@login_required
def resident_profile_settings():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo
    from werkzeug.security import generate_password_hash, check_password_hash
    from werkzeug.utils import secure_filename
    import os
    
    # Get the resident's information
    resident_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        form_type = request.form.get('form_type', '')
        
        # Handle personal information update
        if form_type == 'personal_info':
            first_name = request.form.get('firstName')
            last_name = request.form.get('lastName')
            phone_number = request.form.get('phoneNumber')
            email = request.form.get('email')
            
            if first_name and last_name and phone_number and email:
                # Update resident info
                resident_info.firstName = first_name
                resident_info.lastName = last_name
                resident_info.phoneNumber = phone_number
                
                # Update user email
                current_user.email = email
                
                # Update user full name
                current_user.fullName = f"{first_name} {last_name}"
                
                # Reset verification status
                current_user.isVerified = False
                
                # Reset any existing application statuses
                from models import AddressApplication
                existing_applications = AddressApplication.query.filter_by(applicant_id=current_user.id, status='pending').all()
                for app in existing_applications:
                    app.status = 'cancelled'
                    app.leader_notes = "Application cancelled due to profile information change."
                
                db.session.commit()
                flash('Personal information updated successfully! Your address verification has been reset and will need to be verified again.', 'warning')
            else:
                flash('Please fill in all required fields.', 'danger')
        
        # Handle password update
        elif form_type == 'security':
            current_password = request.form.get('currentPassword')
            new_password = request.form.get('newPassword')
            confirm_password = request.form.get('confirmPassword')
            
            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
            elif not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'danger')
            else:
                current_user.password = generate_password_hash(new_password)
                db.session.commit()
                flash('Password updated successfully!', 'success')
        
        # Handle photo uploads
        elif form_type == 'id_photo' and 'idPhoto' in request.files:
            id_photo = request.files['idPhoto']
            
            if id_photo and id_photo.filename:
                filename = secure_filename(f"id_{current_user.id}_{id_photo.filename}")
                filepath = os.path.join('static/uploads/id_photos', filename)
                
                # Ensure the directory exists
                os.makedirs('static/uploads/id_photos', exist_ok=True)
                
                # Save the file
                id_photo.save(filepath)
                
                # Update the path in the database
                resident_info.idPhotoPath = f"/{filepath}"
                
                # Reset verification status
                current_user.isVerified = False
                
                # Reset any existing application statuses
                from models import AddressApplication
                existing_applications = AddressApplication.query.filter_by(applicant_id=current_user.id, status='pending').all()
                for app in existing_applications:
                    app.status = 'cancelled'
                    app.leader_notes = "Application cancelled due to ID photo change."
                
                db.session.commit()
                
                flash('ID photo updated successfully! Your address verification has been reset and will need to be verified again.', 'warning')
        
        elif form_type == 'face_photo' and 'profilePhoto' in request.files:
            face_photo = request.files['profilePhoto']
            
            if face_photo and face_photo.filename:
                filename = secure_filename(f"face_{current_user.id}_{face_photo.filename}")
                filepath = os.path.join('static/uploads/face_photos', filename)
                
                # Ensure the directory exists
                os.makedirs('static/uploads/face_photos', exist_ok=True)
                
                # Save the file
                face_photo.save(filepath)
                
                # Update the path in the database
                resident_info.facePhotoPath = f"/{filepath}"
                
                # Reset verification status
                current_user.isVerified = False
                
                # Reset any existing application statuses
                from models import AddressApplication
                existing_applications = AddressApplication.query.filter_by(applicant_id=current_user.id, status='pending').all()
                for app in existing_applications:
                    app.status = 'cancelled'
                    app.leader_notes = "Application cancelled due to profile photo change."
                
                db.session.commit()
                
                flash('Profile photo updated successfully! Your address verification has been reset and will need to be verified again.', 'warning')
        
        # Handle notification settings
        elif form_type == 'notifications':
            # Process notification preferences (this would typically be saved to a user preferences table)
            email_notifications = 'emailNotifications' in request.form
            sms_notifications = 'smsNotifications' in request.form
            appointment_reminders = 'appointmentReminders' in request.form
            system_updates = 'systemUpdates' in request.form
            
            # In a real application, we would save these preferences to the database
            flash('Notification preferences updated successfully!', 'success')
        
        return redirect(url_for('resident_profile_settings'))
    
    return render_template(
        'resident/profile_settings.html',
        resident_info=resident_info
    )

@app.route('/resident/my-address')
@login_required
def resident_my_address():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication, AddressCertificate
    
    # Get the resident's information
    resident_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
    
    # Get the most recent approved application, if any
    approved_application = AddressApplication.query.filter_by(
        applicant_id=current_user.id,
        status='approved'
    ).order_by(AddressApplication.updated_at.desc()).first()
    
    # Get the certificate for the approved application, if any
    certificate = None
    if approved_application:
        certificate = AddressCertificate.query.filter_by(
            application_id=approved_application.id
        ).first()
    
    # Check if there's a pending application
    pending_application = AddressApplication.query.filter(
        AddressApplication.applicant_id == current_user.id,
        AddressApplication.status.in_(['pending', 'leader_approved', 'interview_scheduled', 'interview_completed'])
    ).order_by(AddressApplication.created_at.desc()).first()
    
    return render_template(
        'resident/my_address.html',
        resident_info=resident_info,
        approved_application=approved_application,
        certificate=certificate,
        pending_application=pending_application
    )

@app.route('/resident/address-history')
@login_required
def resident_address_history():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication, AddressCertificate
    
    # Get all approved and superseded applications for the user, ordered by date (newest first)
    approved_applications = AddressApplication.query.filter(
        AddressApplication.applicant_id == current_user.id,
        AddressApplication.status.in_(['approved', 'superseded'])
    ).order_by(AddressApplication.updated_at.desc()).all()
    
    # Get the current active application (most recent approved, not superseded)
    current_active = None
    for app in approved_applications:
        if app.status == 'approved':
            current_active = app
            break
    
    # Get certificates for all applications
    certificates = {}
    for app in approved_applications:
        certificate = AddressCertificate.query.filter_by(
            application_id=app.id
        ).first()
        if certificate:
            certificates[app.id] = certificate
    
    return render_template(
        'resident/address_history.html',
        approved_applications=approved_applications,
        certificates=certificates,
        current_active=current_active
    )

@app.route('/resident/update-address', methods=['GET', 'POST'])
@login_required
def resident_update_address():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import ResidentInfo, AddressApplication
    
    # Get the resident's information
    resident_info = ResidentInfo.query.filter_by(user_id=current_user.id).first()
    
    if not resident_info:
        flash('No address information found. Please complete your profile first.', 'warning')
        return redirect(url_for('resident_my_address'))
    
    # Check if there's a pending application
    pending_application = AddressApplication.query.filter(
        AddressApplication.applicant_id == current_user.id,
        AddressApplication.status.in_(['pending', 'leader_approved', 'interview_scheduled', 'interview_completed'])
    ).order_by(AddressApplication.created_at.desc()).first()
    
    if pending_application:
        flash('You already have a pending application. Please wait for it to be processed before updating your address.', 'warning')
        return redirect(url_for('resident_my_address'))
    
    if request.method == 'POST':
        try:
            # Get form data with defaults to prevent errors
            settlement = request.form.get('settlement', '')
            unitNumber = request.form.get('unitNumber', '')
            postalCode = request.form.get('postalCode', '')
            isOwner = True if request.form.get('isOwner') == 'yes' else False
            municipality = request.form.get('municipality', '')
            wardNumber = request.form.get('wardNumber', '1')
            councillorName = request.form.get('councillorName', '')
            
            # Update address information
            resident_info.settlement = settlement
            resident_info.unitNumber = unitNumber
            resident_info.postalCode = postalCode
            resident_info.isOwner = isOwner
            resident_info.municipality = municipality
            resident_info.wardNumber = int(wardNumber)
            resident_info.councillorName = councillorName
            
            # Mark any approved applications as superseded in officer_notes
            approved_applications = AddressApplication.query.filter_by(
                applicant_id=current_user.id,
                status='approved'
            ).all()
            
            for app in approved_applications:
                app.status = 'superseded'
                if app.officer_notes:
                    app.officer_notes += "\n\nThis application has been superseded by an address update."
                else:
                    app.officer_notes = "This application has been superseded by an address update."
            
            # Create a new pending application
            new_application = AddressApplication(
                applicant_id=current_user.id,
                status='pending'
            )
            db.session.add(new_application)
            
            # Reset verification status
            current_user.isVerified = False
            
            # Commit all changes
            db.session.commit()
            
            flash('Your address has been updated. You will need to go through the verification process again.', 'info')
            return redirect(url_for('resident_my_address'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error in resident_update_address: {str(e)}")
            flash(f'Error updating address: {str(e)}', 'danger')
            return redirect(url_for('resident_update_address'))
    
    return render_template(
        'resident/update_address.html',
        resident_info=resident_info
    )

# Leader Routes
@app.route('/leader/dashboard')
@login_required
def leader_dashboard():
    if current_user.userType != 'leader':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import LeaderInfo, AddressApplication, User
    
    # Get the leader's information
    leader_info = LeaderInfo.query.filter_by(user_id=current_user.id).first()
    
    # Leaders must be approved to access the dashboard
    if not leader_info or not leader_info.isApproved:
        flash('Your leader account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get applications for leader's ward
    applications = []
    # In a real app, we'd filter by ward/municipality
    # Here, we'll just get all pending applications for the demo
    applications = AddressApplication.query.filter_by(status='pending').all()
    
    # Count applications by status
    pending_applications_count = AddressApplication.query.filter_by(status='pending').count()
    approved_applications_count = AddressApplication.query.filter_by(
        status='leader_approved', leader_id=current_user.id).count()
    rejected_applications_count = AddressApplication.query.filter_by(
        status='rejected', leader_id=current_user.id).count()
    total_applications_count = (pending_applications_count + 
                                approved_applications_count + 
                                rejected_applications_count)
    
    # Get the most recent applications for the dashboard
    recent_applications = applications[:5] if applications else []
    
    return render_template(
        'leader/dashboard.html',
        leader_info=leader_info,
        pending_applications_count=pending_applications_count,
        approved_applications_count=approved_applications_count,
        rejected_applications_count=rejected_applications_count,
        total_applications_count=total_applications_count,
        recent_applications=recent_applications
    )

@app.route('/leader/applications')
@login_required
def leader_applications():
    if current_user.userType != 'leader':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import LeaderInfo, AddressApplication, ResidentInfo, User
    from sqlalchemy import or_
    
    # Get the leader's information
    leader_info = LeaderInfo.query.filter_by(user_id=current_user.id).first()
    
    # Leaders must be approved to access the dashboard
    if not leader_info or not leader_info.isApproved:
        flash('Your leader account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get query parameters
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of applications per page
    
    # Show all applications (pending, approved, rejected, etc.)
    if status == 'all':
        applications = AddressApplication.query.all()
    elif status == 'pending':
        applications = AddressApplication.query.filter_by(status='pending').all()
    elif status == 'approved':
        applications = AddressApplication.query.filter(
            AddressApplication.status.in_(['leader_approved', 'interview_scheduled', 'interview_completed', 'approved'])
        ).all()
    elif status == 'rejected':
        applications = AddressApplication.query.filter_by(status='rejected').all()
    else:
        applications = AddressApplication.query.all()
    
    # Count pending applications for notification badge
    pending_applications_count = AddressApplication.query.filter_by(status='pending').count()
    
    return render_template(
        'leader/applications.html',
        leader_info=leader_info,
        applications=applications,
        current_status=status,
        pending_applications_count=pending_applications_count
    )

@app.route('/leader/application-history')
@login_required
def leader_application_history():
    if current_user.userType != 'leader':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import LeaderInfo, AddressApplication, ResidentInfo, User
    
    # Get the leader's information
    leader_info = LeaderInfo.query.filter_by(user_id=current_user.id).first()
    
    # Leaders must be approved to access the dashboard
    if not leader_info or not leader_info.isApproved:
        flash('Your leader account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get query parameters
    status = request.args.get('status', 'all')
    
    # Get applications from residents in the leader's municipality/ward
    applications_query = db.session.query(AddressApplication, User, ResidentInfo)\
        .join(User, User.id == AddressApplication.applicant_id)\
        .join(ResidentInfo, ResidentInfo.user_id == User.id)\
        .filter(
            # Applications in leader's municipality and ward
            ResidentInfo.municipality == leader_info.municipality,
            ResidentInfo.wardNumber == leader_info.wardNumber
        )
    
    # Only show approved and rejected applications in application history
    # By default, show both approved and rejected
    applications_query = applications_query.filter(
        AddressApplication.status.in_(['leader_approved', 'interview_scheduled', 'interview_completed', 'approved', 'rejected'])
    )
    
    # Apply status filter if specified
    if status == 'approved':
        applications_query = applications_query.filter(AddressApplication.status.in_(['leader_approved', 'interview_scheduled', 'interview_completed', 'approved']))
    elif status == 'rejected':
        applications_query = applications_query.filter(AddressApplication.status == 'rejected')
    
    # Execute query
    applications_result = applications_query.all()
    
    # Extract just the application objects and ensure no duplicates
    unique_app_ids = set()
    applications = []
    for result in applications_result:
        app = result[0]
        if app.id not in unique_app_ids:
            unique_app_ids.add(app.id)
            applications.append(app)
    
    # Count pending applications for notification badge
    pending_applications_count = db.session.query(AddressApplication, User, ResidentInfo)\
        .join(User, User.id == AddressApplication.applicant_id)\
        .join(ResidentInfo, ResidentInfo.user_id == User.id)\
        .filter(
            ResidentInfo.municipality == leader_info.municipality,
            ResidentInfo.wardNumber == leader_info.wardNumber,
            AddressApplication.status == 'pending'
        ).count()
    
    # Gather statistics
    stats = {
        'approved': len([app for app in applications if app.status in ['leader_approved', 'interview_scheduled', 'interview_completed', 'approved']]),
        'rejected': len([app for app in applications if app.status == 'rejected']),
        'pending': pending_applications_count,
        'total': len(applications)
    }
    
    return render_template(
        'leader/application_history.html',
        leader_info=leader_info,
        applications=applications,
        pending_applications_count=pending_applications_count,
        current_status=status,
        stats=stats
    )

@app.route('/leader/profile-settings', methods=['GET', 'POST'])
@login_required
def leader_profile_settings():
    if current_user.userType != 'leader':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import LeaderInfo, AddressApplication, User, ResidentInfo
    from werkzeug.security import generate_password_hash, check_password_hash
    from werkzeug.utils import secure_filename
    import os
    
    # Get the leader's information
    leader_info = LeaderInfo.query.filter_by(user_id=current_user.id).first()
    
    # Count pending applications for notification badge
    pending_applications_count = AddressApplication.query.filter_by(status='pending').count()
    
    if request.method == 'POST':
        form_type = request.form.get('form_type', '')
        
        # Handle personal information update
        if form_type == 'personal_info':
            first_name = request.form.get('firstName')
            last_name = request.form.get('lastName')
            phone_number = request.form.get('phoneNumber')
            email = request.form.get('email')
            
            if first_name and last_name and phone_number and email:
                # Update leader info
                leader_info.firstName = first_name
                leader_info.lastName = last_name
                leader_info.phoneNumber = phone_number
                
                # Update user email
                current_user.email = email
                
                # Update user full name
                current_user.fullName = f"{first_name} {last_name}"
                
                # Reset approval status since information has changed
                leader_info.isApproved = False
                
                db.session.commit()
                flash('Personal information updated successfully! Your account will need to be verified again due to the changes.', 'warning')
            else:
                flash('Please fill in all required fields.', 'danger')
        
        # Handle office information update
        elif form_type == 'office_info':
            municipality = request.form.get('municipality')
            ward_number = request.form.get('wardNumber')
            office_location = request.form.get('officeLocation')
            settlement = request.form.get('settlement')
            unit_number = request.form.get('unitNumber')
            postal_code = request.form.get('postalCode')
            
            if municipality and ward_number and office_location and settlement and unit_number and postal_code:
                # Update leader info
                leader_info.municipality = municipality
                leader_info.wardNumber = int(ward_number)
                leader_info.officeLocation = office_location
                leader_info.settlement = settlement
                leader_info.unitNumber = unit_number
                leader_info.postalCode = postal_code
                
                # Reset approval status since information has changed
                leader_info.isApproved = False
                
                db.session.commit()
                flash('Office information updated successfully! Your account will need to be verified again due to the changes.', 'warning')
            else:
                flash('Please fill in all required fields.', 'danger')
        
        # Handle password update
        elif form_type == 'security':
            current_password = request.form.get('currentPassword')
            new_password = request.form.get('newPassword')
            confirm_password = request.form.get('confirmPassword')
            
            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
            elif not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'danger')
            else:
                current_user.password = generate_password_hash(new_password)
                db.session.commit()
                flash('Password updated successfully!', 'success')
        
        # Handle photo uploads
        elif form_type == 'id_photo' and 'idPhoto' in request.files:
            id_photo = request.files['idPhoto']
            
            if id_photo and id_photo.filename:
                filename = secure_filename(f"id_{current_user.id}_{id_photo.filename}")
                filepath = os.path.join('static/uploads/id_photos', filename)
                
                # Ensure the directory exists
                os.makedirs('static/uploads/id_photos', exist_ok=True)
                
                # Save the file
                id_photo.save(filepath)
                
                # Update the path in the database
                leader_info.idPhotoPath = f"/{filepath}"
                db.session.commit()
                
                flash('ID photo updated successfully!', 'success')
        
        elif form_type == 'face_photo' and 'profilePhoto' in request.files:
            face_photo = request.files['profilePhoto']
            
            if face_photo and face_photo.filename:
                filename = secure_filename(f"face_{current_user.id}_{face_photo.filename}")
                filepath = os.path.join('static/uploads/face_photos', filename)
                
                # Ensure the directory exists
                os.makedirs('static/uploads/face_photos', exist_ok=True)
                
                # Save the file
                face_photo.save(filepath)
                
                # Update the path in the database
                leader_info.facePhotoPath = f"/{filepath}"
                db.session.commit()
                
                flash('Profile photo updated successfully!', 'success')
        
        return redirect(url_for('leader_profile_settings'))
    
    return render_template(
        'leader/profile_settings.html',
        leader_info=leader_info,
        pending_applications_count=pending_applications_count
    )

@app.route('/police/dashboard')
@login_required
def police_dashboard():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, Appointment, AddressApplication
    from datetime import datetime, timedelta
    
    # Get the officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access the dashboard
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get today's appointments
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Get today's appointments
    today_appointments = Appointment.query.filter(
        Appointment.officer_id == current_user.id,
        Appointment.appointment_date >= today_start,
        Appointment.appointment_date <= today_end
    ).order_by(Appointment.appointment_date).all()
    
    # Get upcoming appointments
    upcoming_appointments = Appointment.query.filter(
        Appointment.officer_id == current_user.id,
        Appointment.appointment_date > today_end
    ).order_by(Appointment.appointment_date).all()
    
    # Get applications for review
    applications_for_review = AddressApplication.query.filter_by(
        status='interview_completed', officer_id=current_user.id
    ).all()
    
    # Statistics for the dashboard
    upcoming_appointments_count = len(upcoming_appointments)
    completed_interviews_count = Appointment.query.filter_by(
        officer_id=current_user.id, status='completed'
    ).count()
    approved_applications_count = AddressApplication.query.filter_by(
        status='approved', officer_id=current_user.id
    ).count()
    pending_review_count = len(applications_for_review)
    
    # Recent applications for display
    recent_applications = applications_for_review[:5] if applications_for_review else []
    
    return render_template(
        'police/dashboard.html',
        police_info=police_info,
        today_appointments=today_appointments,
        upcoming_appointments=upcoming_appointments,
        recent_applications=recent_applications,
        upcoming_appointments_count=upcoming_appointments_count,
        completed_interviews_count=completed_interviews_count,
        approved_applications_count=approved_applications_count,
        pending_review_count=pending_review_count
    )

@app.route('/police/appointments')
@login_required
def police_appointments():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, Appointment
    from datetime import datetime
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access the dashboard
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get all upcoming appointments
    today = datetime.now()
    upcoming_appointments = Appointment.query.filter(
        Appointment.officer_id == current_user.id,
        Appointment.appointment_date >= today,
        Appointment.status == 'scheduled'
    ).order_by(Appointment.appointment_date).all()
    
    return render_template(
        'police/appointments.html',
        police_info=police_info,
        upcoming_appointments=upcoming_appointments
    )

@app.route('/police/past-appointments')
@login_required
def police_past_appointments():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, Appointment
    from datetime import datetime
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access the dashboard
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get all past appointments
    today = datetime.now()
    past_appointments = Appointment.query.filter(
        Appointment.officer_id == current_user.id
    ).filter(
        (Appointment.appointment_date < today) | 
        (Appointment.status == 'completed')
    ).order_by(Appointment.appointment_date.desc()).all()
    
    return render_template(
        'police/past_appointments.html',
        police_info=police_info,
        past_appointments=past_appointments
    )

@app.route('/police/verified-addresses')
@login_required
def police_verified_addresses():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, AddressApplication, AddressCertificate, User, ResidentInfo
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access the dashboard
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get all approved applications with certificates
    verified_addresses = db.session.query(
        AddressApplication, User, ResidentInfo, AddressCertificate
    ).join(
        User, User.id == AddressApplication.applicant_id
    ).join(
        ResidentInfo, ResidentInfo.user_id == User.id
    ).join(
        AddressCertificate, AddressCertificate.application_id == AddressApplication.id
    ).filter(
        AddressApplication.officer_id == current_user.id,
        AddressApplication.status == 'approved'
    ).order_by(AddressCertificate.issue_date.desc()).all()
    
    return render_template(
        'police/verified_addresses.html',
        police_info=police_info,
        verified_addresses=verified_addresses
    )

@app.route('/police/profile-settings', methods=['GET', 'POST'])
@login_required
def police_profile_settings():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, User
    from werkzeug.security import generate_password_hash, check_password_hash
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Handle form submission
    if request.method == 'POST':
        if 'update_profile' in request.form:
            # Update profile information
            police_info.firstName = request.form.get('firstName')
            police_info.lastName = request.form.get('lastName')
            police_info.phoneNumber = request.form.get('phoneNumber')
            police_info.rank = request.form.get('rank')
            police_info.stationName = request.form.get('stationName')
            
            # Update user email if changed
            new_email = request.form.get('email')
            if new_email != current_user.email:
                existing_user = User.query.filter_by(email=new_email).first()
                if existing_user and existing_user.id != current_user.id:
                    flash('Email already in use.', 'danger')
                else:
                    current_user.email = new_email
            
            # Reset approval status since information has changed
            police_info.isApproved = False
            
            db.session.commit()
            flash('Profile updated successfully! Your account will need to be verified again due to the changes.', 'warning')
            
        elif 'change_password' in request.form:
            # Change password
            current_password = request.form.get('currentPassword')
            new_password = request.form.get('newPassword')
            confirm_password = request.form.get('confirmPassword')
            
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'danger')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
            else:
                current_user.password = generate_password_hash(new_password)
                db.session.commit()
                flash('Password changed successfully.', 'success')
        
        return redirect(url_for('police_profile_settings'))
    
    return render_template(
        'police/profile_settings.html',
        police_info=police_info
    )

@app.route('/police/delete_weekly_schedule/<int:schedule_id>')
@login_required
def police_delete_weekly_schedule(schedule_id):
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, WeeklySchedule, AvailableTimeSlot, ScheduledBreak
    from datetime import datetime
    import logging
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access this feature
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get the specific weekly schedule
    schedule = WeeklySchedule.query.filter_by(
        id=schedule_id,
        officer_id=current_user.id
    ).first()
    
    if not schedule:
        flash('Schedule not found.', 'danger')
        return redirect(url_for('police_availability'))
    
    try:
        # Mark the schedule as inactive (soft delete)
        schedule.is_active = False
        
        # Delete all future non-booked time slots associated with this schedule
        now = datetime.now()
        deleted_slots = AvailableTimeSlot.query.filter(
            AvailableTimeSlot.weekly_schedule_id == schedule.id,
            AvailableTimeSlot.is_booked == False,
            AvailableTimeSlot.start_time > now
        ).delete()
        
        db.session.commit()
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        flash(f'Removed weekly schedule for {days[schedule.day_of_week]} and {deleted_slots} future slots.', 'success')
    except Exception as e:
        logging.error(f"Error deleting weekly schedule: {e}")
        db.session.rollback()
        flash('An error occurred while removing the schedule. Please try again.', 'danger')
    
    return redirect(url_for('police_availability'))


@app.route('/police/availability')
@login_required
def police_availability():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, AvailableTimeSlot, WeeklySchedule
    from datetime import datetime
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access this page
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Get all available time slots for this officer
    available_slots = AvailableTimeSlot.query.filter_by(
        officer_id=current_user.id
    ).order_by(AvailableTimeSlot.start_time).all()
    
    # Get all slots (both available and booked) for calendar
    all_slots = AvailableTimeSlot.query.filter_by(
        officer_id=current_user.id
    ).all()
    
    # Get weekly schedules including their scheduled breaks
    from models import ScheduledBreak
    
    weekly_schedules = WeeklySchedule.query.filter_by(
        officer_id=current_user.id,
        is_active=True
    ).order_by(WeeklySchedule.day_of_week, WeeklySchedule.start_time).all()
    
    # Eager load breaks for each schedule
    for schedule in weekly_schedules:
        schedule.breaks = ScheduledBreak.query.filter_by(schedule_id=schedule.id).all()
    
    # Get today's date in ISO format for min date inputs
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # Days of the week for display
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    return render_template(
        'police/availability.html',
        police_info=police_info,
        available_slots=available_slots,
        all_slots=all_slots,
        weekly_schedules=weekly_schedules,
        days=days,
        today_date=today_date
    )

@app.route('/police/add_availability', methods=['POST'])
@login_required
def police_add_availability():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, AvailableTimeSlot
    from datetime import datetime
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access this feature
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        slot_date = request.form.get('slot_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        if not slot_date or not start_time or not end_time:
            flash('All fields are required.', 'danger')
            return redirect(url_for('police_availability'))
        
        # Convert to datetime objects
        try:
            start_datetime = datetime.strptime(f"{slot_date} {start_time}", '%Y-%m-%d %H:%M')
            end_datetime = datetime.strptime(f"{slot_date} {end_time}", '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Invalid date or time format.', 'danger')
            return redirect(url_for('police_availability'))
        
        # Validate time values
        if start_datetime >= end_datetime:
            flash('End time must be after start time.', 'danger')
            return redirect(url_for('police_availability'))
            
        if start_datetime < datetime.now():
            flash('Cannot add time slots in the past.', 'danger')
            return redirect(url_for('police_availability'))
        
        # Check for overlapping slots
        overlapping_slots = AvailableTimeSlot.query.filter(
            AvailableTimeSlot.officer_id == current_user.id,
            AvailableTimeSlot.start_time < end_datetime,
            AvailableTimeSlot.end_time > start_datetime
        ).all()
        
        if overlapping_slots:
            flash('This time slot overlaps with an existing slot.', 'danger')
            return redirect(url_for('police_availability'))
        
        # Create new time slot with location information
        new_slot = AvailableTimeSlot(
            officer_id=current_user.id,
            start_time=start_datetime,
            end_time=end_datetime,
            is_booked=False,
            # Add location information
            municipality=police_info.municipality,
            station_name=police_info.stationName,
            postal_code=police_info.postalCode
        )
        
        try:
            db.session.add(new_slot)
            db.session.commit()
            flash('Time slot added successfully.', 'success')
        except:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
        
        return redirect(url_for('police_availability'))

@app.route('/police/delete_availability/<int:slot_id>', methods=['GET', 'POST'])
@login_required
def police_delete_availability(slot_id):
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, AvailableTimeSlot
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access this feature
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    # Find the time slot
    time_slot = AvailableTimeSlot.query.get(slot_id)
    
    if not time_slot or time_slot.officer_id != current_user.id:
        flash('Time slot not found.', 'danger')
        return redirect(url_for('police_availability'))
    
    if time_slot.is_booked:
        flash('Cannot delete a booked time slot.', 'danger')
        return redirect(url_for('police_availability'))
    
    try:
        db.session.delete(time_slot)
        db.session.commit()
        flash('Time slot deleted successfully.', 'success')
    except:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'danger')
    
    return redirect(url_for('police_availability'))

@app.route('/police/add_weekly_availability', methods=['POST'])
@login_required
def police_add_weekly_availability():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, WeeklySchedule, AvailableTimeSlot, ScheduledBreak
    from datetime import datetime, timedelta, time
    import logging
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access this feature
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Log the form data for debugging
        logging.debug(f"Form data received: {request.form}")
        
        day_of_week = request.form.get('day_of_week')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        
        if day_of_week is None or not start_time_str or not end_time_str:
            flash('Please select a day and provide both start and end times.', 'danger')
            return redirect(url_for('police_availability'))
        
        try:
            day_of_week = int(day_of_week)
            start_time_obj = datetime.strptime(start_time_str, '%H:%M').time()
            end_time_obj = datetime.strptime(end_time_str, '%H:%M').time()
        except (ValueError, TypeError) as e:
            logging.error(f"Time parsing error: {e}")
            flash('Invalid time format. Please use the time picker.', 'danger')
            return redirect(url_for('police_availability'))
        
        # Validate time values
        if start_time_obj >= end_time_obj:
            flash('Start time must be before end time.', 'danger')
            return redirect(url_for('police_availability'))
        
        # Check if this day already has a schedule
        existing_schedule = WeeklySchedule.query.filter_by(
            officer_id=current_user.id,
            day_of_week=day_of_week,
            is_active=True
        ).first()
        
        if existing_schedule:
            flash(f'You already have a schedule for this day. Please delete the existing schedule first.', 'warning')
            return redirect(url_for('police_availability'))
        
        # Create new weekly schedule
        try:
            new_schedule = WeeklySchedule(
                officer_id=current_user.id,
                day_of_week=day_of_week,
                start_time=start_time_obj,
                end_time=end_time_obj,
                is_active=True
            )
            
            db.session.add(new_schedule)
            db.session.flush()  # Get the ID without committing
            
            # Process custom breaks
            break_starts = request.form.getlist('break_start[]')
            break_ends = request.form.getlist('break_end[]')
            
            for i in range(len(break_starts)):
                if break_starts[i] and break_ends[i]:  # Only add if both times are provided
                    try:
                        break_start_time = datetime.strptime(break_starts[i], '%H:%M').time()
                        break_end_time = datetime.strptime(break_ends[i], '%H:%M').time()
                        
                        # Create scheduled break
                        scheduled_break = ScheduledBreak(
                            schedule_id=new_schedule.id,
                            break_start_time=break_start_time,
                            break_end_time=break_end_time
                        )
                        db.session.add(scheduled_break)
                    except Exception as e:
                        logging.error(f"Error adding break: {e}")
                        continue
            
            # Generate slots for the next 4 weeks
            slots_added = 0
            now = datetime.now()
            days_ahead = (day_of_week - now.weekday()) % 7  # Days until the next occurrence
            if days_ahead == 0:  # If today is the day
                # If current time is past the end time, schedule for next week
                if now.time() >= end_time_obj:
                    days_ahead = 7
            
            # Calculate the next occurrence of this day
            next_date = now.date() + timedelta(days=days_ahead)
            
            # Create slots for the next 4 weeks
            for week in range(4):
                slot_date = next_date + timedelta(days=week * 7)
                
                # Combine date and time
                day_start = datetime.combine(slot_date, start_time_obj)
                day_end = datetime.combine(slot_date, end_time_obj)
                
                if day_start < datetime.now():
                    continue  # Skip if in the past
                
                # Create 30-minute interview slots with 15-minute gaps between each
                current_slot_start = day_start
                interview_duration = timedelta(minutes=30)
                gap_duration = timedelta(minutes=15)
                
                # Get the scheduled breaks for this weekly schedule
                break_times = []
                scheduled_breaks = ScheduledBreak.query.filter_by(schedule_id=new_schedule.id).all()
                for scheduled_break in scheduled_breaks:
                    break_times.append((scheduled_break.break_start_time, scheduled_break.break_end_time))
                
                while current_slot_start + interview_duration <= day_end:
                    current_slot_end = current_slot_start + interview_duration
                    
                    # Check if this slot overlaps with a break time
                    is_break_time = False
                    for break_start, break_end in break_times:
                        slot_start_time = current_slot_start.time()
                        slot_end_time = current_slot_end.time()
                        
                        # Check for any overlap with break
                        if (slot_start_time < break_end and slot_end_time > break_start):
                            is_break_time = True
                            break
                    
                    if is_break_time:
                        # Skip this slot as it's during a break
                        current_slot_start = current_slot_end
                        continue
                    
                    # Check for overlapping slots
                    overlapping_slots = AvailableTimeSlot.query.filter(
                        AvailableTimeSlot.officer_id == current_user.id,
                        AvailableTimeSlot.start_time < current_slot_end,
                        AvailableTimeSlot.end_time > current_slot_start
                    ).all()
                    
                    if not overlapping_slots:
                        # Create new 30-minute interview slot linked to this weekly schedule
                        try:
                            new_slot = AvailableTimeSlot(
                                officer_id=current_user.id,
                                weekly_schedule_id=new_schedule.id,
                                start_time=current_slot_start,
                                end_time=current_slot_end,
                                is_booked=False,
                                # Add location information
                                municipality=police_info.municipality,
                                station_name=police_info.stationName,
                                postal_code=police_info.postalCode
                            )
                            
                            db.session.add(new_slot)
                            slots_added += 1
                            logging.debug(f"Added interview slot: {current_slot_start} to {current_slot_end} at {police_info.stationName}")
                        except Exception as e:
                            logging.error(f"Error adding slot: {e}")
                    
                    # Move to next slot (30 minutes + 15 minute gap = 45 minutes later)
                    current_slot_start = current_slot_end + gap_duration
            
            db.session.commit()
            
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            flash(f'Added weekly schedule for {days[day_of_week]} and generated {slots_added} interview slots.', 'success')
            
        except Exception as e:
            logging.error(f"Database error: {e}")
            db.session.rollback()
            flash('An error occurred while saving your weekly schedule. Please try again.', 'danger')
        
        return redirect(url_for('police_availability'))

@app.route('/police/clear_availability')
@login_required
def police_clear_availability():
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import PoliceInfo, AvailableTimeSlot, WeeklySchedule
    from datetime import datetime
    import logging
    
    # Get the police officer's information
    police_info = PoliceInfo.query.filter_by(user_id=current_user.id).first()
    
    # Police officers must be approved to access this feature
    if not police_info or not police_info.isApproved:
        flash('Your police officer account is pending approval.', 'warning')
        return redirect(url_for('index'))
    
    try:
        # Delete all available (not booked) future time slots
        now = datetime.now()
        deleted_slots = AvailableTimeSlot.query.filter(
            AvailableTimeSlot.officer_id == current_user.id,
            AvailableTimeSlot.is_booked == False,
            AvailableTimeSlot.start_time > now
        ).delete()
        
        # Mark all weekly schedules as inactive
        WeeklySchedule.query.filter_by(
            officer_id=current_user.id,
            is_active=True
        ).update({WeeklySchedule.is_active: False})
        
        db.session.commit()
        flash(f'Successfully cleared all weekly schedules and {deleted_slots} future available time slots.', 'success')
    except:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'danger')
    
    return redirect(url_for('police_availability'))

# API endpoints for officer availability and interview scheduling
@app.route('/api/location-availability')
@login_required
def api_location_availability():
    from models import AvailableTimeSlot, User
    from datetime import datetime
    from flask import jsonify, request
    from sqlalchemy import func
    import logging
    
    # Get location parameters
    municipality = request.args.get('municipality')
    station_name = request.args.get('station')
    postal_code = request.args.get('postal')
    
    logging.info(f"API Location Availability Request - Municipality: {municipality}, Station: {station_name}, Postal: {postal_code}")
    
    if not municipality or not station_name or not postal_code:
        logging.error("Missing location parameters in API request")
        return jsonify({"error": "Missing location parameters"}), 400
    
    # Get available slots for this location
    try:
        available_slots = AvailableTimeSlot.query.filter(
            AvailableTimeSlot.municipality == municipality,
            AvailableTimeSlot.station_name == station_name,
            AvailableTimeSlot.postal_code == postal_code,
            AvailableTimeSlot.is_booked == False,
            AvailableTimeSlot.start_time > datetime.now()
        ).order_by(AvailableTimeSlot.start_time).all()
        
        logging.info(f"Found {len(available_slots)} available slots for the location")
    except Exception as e:
        logging.error(f"Error querying for available slots: {str(e)}")
        return jsonify({"error": "Error fetching available slots"}), 500
    
    slots_data = []
    for slot in available_slots:
        # Get minimum officer info (name is hidden until after booking)
        officer_id = slot.officer_id
        
        slots_data.append({
            'id': slot.id,
            'start_time': slot.start_time.isoformat(),
            'end_time': slot.end_time.isoformat(),
            'municipality': slot.municipality,
            'station_name': slot.station_name,
            'postal_code': slot.postal_code
        })
    
    return jsonify(slots_data)

@app.route('/api/officer-availability/<int:officer_id>')
@login_required
def api_officer_availability(officer_id):
    from models import AvailableTimeSlot, User, PoliceInfo
    from datetime import datetime
    from flask import jsonify
    
    # Verify the officer exists and is approved
    officer = User.query.filter_by(id=officer_id, userType='police').first()
    if not officer:
        return jsonify([])
    
    police_info = PoliceInfo.query.filter_by(user_id=officer_id).first()
    if not police_info or not police_info.isApproved:
        return jsonify([])
    
    # Get available slots (not booked) with start time in the future
    available_slots = AvailableTimeSlot.query.filter(
        AvailableTimeSlot.officer_id == officer_id,
        AvailableTimeSlot.is_booked == False,
        AvailableTimeSlot.start_time > datetime.now()
    ).order_by(AvailableTimeSlot.start_time).all()
    
    # Format slots for JSON response
    slots_data = []
    for slot in available_slots:
        slots_data.append({
            'id': slot.id,
            'start_time': slot.start_time.isoformat(),
            'end_time': slot.end_time.isoformat()
        })
    
    return jsonify(slots_data)

@app.route('/api/slot-details/<int:slot_id>')
@login_required
def api_slot_details(slot_id):
    from models import AvailableTimeSlot, User, PoliceInfo
    from flask import jsonify
    import logging
    
    logging.info(f"API Slot Details Request - Slot ID: {slot_id}")
    
    try:
        # Get the slot
        slot = AvailableTimeSlot.query.get_or_404(slot_id)
        logging.info(f"Found slot with ID {slot_id} for officer ID {slot.officer_id}")
        
        # Get officer details
        officer = User.query.get(slot.officer_id)
        if not officer:
            logging.error(f"Officer not found for ID {slot.officer_id}")
            return jsonify({"error": "Officer not found"}), 404
            
        officer_info = PoliceInfo.query.filter_by(user_id=officer.id).first()
        if not officer_info:
            logging.error(f"Officer information not found for user ID {officer.id}")
            return jsonify({"error": "Officer information not found"}), 404
    except Exception as e:
        logging.error(f"Error retrieving slot or officer details: {str(e)}")
        return jsonify({"error": "Error retrieving slot details"}), 500
    
    # Create response data - only use location info in initial selection
    # Officer name is intentionally removed until after booking
    slot_data = {
        'id': slot.id,
        'start_time': slot.start_time.isoformat(),
        'end_time': slot.end_time.isoformat(),
        'is_booked': slot.is_booked,
        'officer_id': officer.id,
        'station_name': slot.station_name,
        'municipality': slot.municipality,
        'postal_code': slot.postal_code
    }
    
    return jsonify(slot_data)

@app.route('/book-interview-slot', methods=['POST'])
@login_required
def book_interview_slot():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import AvailableTimeSlot, AddressApplication, Appointment
    from datetime import datetime
    
    slot_id = request.form.get('slot_id')
    application_id = request.form.get('application_id')
    
    if not slot_id or not application_id:
        flash('Missing required information.', 'danger')
        return redirect(url_for('resident_schedule_interview'))
    
    # Get the application
    application = AddressApplication.query.get(application_id)
    if not application or application.applicant_id != current_user.id:
        flash('Application not found.', 'danger')
        return redirect(url_for('resident_schedule_interview'))
    
    # Check if application status allows booking
    if application.status != 'leader_approved':
        flash('This application is not ready for interview scheduling.', 'danger')
        return redirect(url_for('resident_schedule_interview'))
    
    # Get the time slot
    time_slot = AvailableTimeSlot.query.get(slot_id)
    if not time_slot:
        flash('Time slot not found.', 'danger')
        return redirect(url_for('resident_schedule_interview'))
    
    # Check if the slot is already booked
    if time_slot.is_booked:
        flash('This time slot is no longer available.', 'danger')
        return redirect(url_for('resident_schedule_interview'))
    
    # For testing - import needed classes
    from models import AddressCertificate
    import uuid
    
    # Create an appointment
    appointment = Appointment(
        resident_id=current_user.id,
        officer_id=time_slot.officer_id,
        application_id=application.id,
        appointment_date=time_slot.start_time,
        duration_minutes=30,  # 30-minute appointments
        status='completed'  # Mark as completed immediately for testing
    )
    
    # Mark the currently selected slot as booked
    time_slot.is_booked = True
    
    # Also mark any slots that overlap with this one (including the 15 minutes after)
    # This ensures that when a slot is booked, that time plus 15 minutes after won't be available
    from datetime import timedelta
    buffer_end_time = time_slot.end_time + timedelta(minutes=15)
    
    # Find overlapping slots (slots that start during or right after this interview)
    overlapping_slots = AvailableTimeSlot.query.filter(
        AvailableTimeSlot.officer_id == time_slot.officer_id,
        AvailableTimeSlot.id != time_slot.id,  # Exclude the current slot
        AvailableTimeSlot.is_booked == False,  # Only consider slots that aren't already booked
        AvailableTimeSlot.start_time < buffer_end_time,  # The slot starts before the buffered end time
        AvailableTimeSlot.end_time > time_slot.start_time  # The slot ends after this slot starts
    ).all()
    
    # Mark all overlapping slots as booked
    for slot in overlapping_slots:
        slot.is_booked = True
    
    # For testing: Auto-approve application (skip interview)
    application.status = 'approved'
    application.officer_id = time_slot.officer_id
    application.officer_notes = "Auto-approved for testing purposes"
    
    # Create a certificate immediately for testing
    certificate_number = f"AM-{uuid.uuid4().hex[:8].upper()}"
    issue_date = datetime.now()
    expiry_date = issue_date + timedelta(days=365)  # Valid for 1 year
    
    certificate = AddressCertificate(
        application_id=application.id,
        certificate_number=certificate_number,
        issue_date=issue_date,
        expiry_date=expiry_date,
        pdf_path='/static/certificates/demo_certificate.pdf'  # Demo path
    )
    
    try:
        db.session.add(appointment)
        db.session.add(certificate)
        db.session.commit()
        flash('Interview scheduled and automatically approved for testing! You may now download your address certificate.', 'success')
        
        # Send notification to officer
        # (In a real system, this would send an email or push notification)
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error booking interview: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'danger')
    
    return redirect(url_for('resident_application_status'))

@app.route('/cancel-interview', methods=['POST'])
@login_required
def cancel_interview():
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import Appointment, AddressApplication, AvailableTimeSlot
    
    appointment_id = request.form.get('appointment_id')
    if not appointment_id:
        flash('Missing appointment information.', 'danger')
        return redirect(url_for('resident_schedule_interview'))
    
    # Get the appointment
    appointment = Appointment.query.get(appointment_id)
    if not appointment or appointment.resident_id != current_user.id:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('resident_schedule_interview'))
    
    # Check if the appointment can be cancelled
    if appointment.status != 'scheduled':
        flash('This appointment cannot be cancelled.', 'danger')
        return redirect(url_for('resident_schedule_interview'))
    
    # Get the application
    application = AddressApplication.query.get(appointment.application_id)
    
    # Mark the appointment as cancelled
    appointment.status = 'cancelled'
    
    # Update application status back to leader_approved
    if application:
        application.status = 'leader_approved'
    
    # Find and free up the time slot
    time_slot = AvailableTimeSlot.query.filter_by(
        officer_id=appointment.officer_id,
        start_time=appointment.appointment_date,
        is_booked=True
    ).first()
    
    if time_slot:
        time_slot.is_booked = False
    
    try:
        db.session.commit()
        flash('Interview cancelled successfully.', 'success')
        
        # Send notification to officer
        # (In a real system, this would send an email or push notification)
        
    except:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'danger')
    
    return redirect(url_for('resident_schedule_interview'))

# Application review and approval routes
@app.route('/leader/applications/<int:application_id>', methods=['GET', 'POST'])
@login_required
def leader_review_application(application_id):
    if current_user.userType != 'leader':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import LeaderInfo, AddressApplication, ResidentInfo, User
    
    # Get the leader's information
    leader_info = LeaderInfo.query.filter_by(user_id=current_user.id).first()
    if not leader_info or not leader_info.isApproved:
        flash('Your account is not yet verified as a leader.', 'warning')
        return redirect(url_for('leader_dashboard'))
    
    # Get the application
    application = AddressApplication.query.get_or_404(application_id)
    
    # Get resident info
    resident = User.query.get(application.applicant_id)
    resident_info = ResidentInfo.query.filter_by(user_id=resident.id).first()
    
    if request.method == 'POST':
        decision = request.form.get('decision')
        leader_notes = request.form.get('leader_notes')
        
        if decision == 'approve':
            application.status = 'leader_approved'
            application.leader_id = current_user.id
            application.leader_notes = leader_notes
            flash('Application has been approved.', 'success')
        elif decision == 'reject':
            application.status = 'rejected'
            application.leader_id = current_user.id
            application.leader_notes = leader_notes
            flash('Application has been rejected.', 'info')
        
        db.session.commit()
        return redirect(url_for('leader_dashboard'))
    
    return render_template(
        'leader/review_application.html',
        application=application,
        resident_info=resident_info,
        pending_applications_count=AddressApplication.query.filter_by(status='pending').count()
    )

@app.route('/resident/schedule/<int:application_id>', methods=['GET', 'POST'])
@login_required
def schedule_interview(application_id):
    if current_user.userType != 'resident':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import AddressApplication, PoliceInfo, User, Appointment, AvailableTimeSlot
    from datetime import datetime, timedelta
    
    # Get the application
    application = AddressApplication.query.get_or_404(application_id)
    if application.applicant_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('resident_dashboard'))
    
    if application.status != 'leader_approved':
        flash('Your application is not ready for interview scheduling.', 'warning')
        return redirect(url_for('resident_dashboard'))
    
    # Get available officers
    officers = User.query.join(PoliceInfo).filter(PoliceInfo.isApproved == True).all()
    
    # For demo purposes, create some available time slots if none exist
    available_slots = AvailableTimeSlot.query.filter_by(is_booked=False).all()
    if not available_slots and officers:
        # Create mock time slots for the next 7 days
        start_date = datetime.now() + timedelta(days=1)  # Start tomorrow
        for day in range(7):
            slot_date = start_date + timedelta(days=day)
            for hour in [9, 11, 13, 15]:  # 9am, 11am, 1pm, 3pm
                slot_time = datetime.combine(slot_date.date(), datetime.min.time()) + timedelta(hours=hour)
                new_slot = AvailableTimeSlot(
                    officer_id=officers[0].id,
                    start_time=slot_time,
                    end_time=slot_time + timedelta(minutes=30),
                    is_booked=False
                )
                db.session.add(new_slot)
        db.session.commit()
        available_slots = AvailableTimeSlot.query.filter_by(is_booked=False).all()
    
    if request.method == 'POST':
        slot_id = request.form.get('time_slot')
        if not slot_id:
            flash('Please select a time slot.', 'danger')
        else:
            slot = AvailableTimeSlot.query.get(slot_id)
            if slot and not slot.is_booked:
                # Book the slot
                slot.is_booked = True
                
                # Create appointment
                appointment = Appointment(
                    resident_id=current_user.id,
                    officer_id=slot.officer_id,
                    application_id=application.id,
                    appointment_date=slot.start_time,
                    duration_minutes=30,
                    status='scheduled'
                )
                
                # Update application status
                application.status = 'interview_scheduled'
                application.officer_id = slot.officer_id
                
                db.session.add(appointment)
                db.session.commit()
                
                flash('Interview successfully scheduled.', 'success')
                return redirect(url_for('resident_dashboard'))
            else:
                flash('The selected time slot is no longer available.', 'danger')
    
    # Group slots by date for display
    grouped_slots = {}
    for slot in available_slots:
        date_str = slot.start_time.strftime('%Y-%m-%d')
        if date_str not in grouped_slots:
            grouped_slots[date_str] = []
        grouped_slots[date_str].append(slot)
    
    # Sort dates
    sorted_dates = sorted(grouped_slots.keys())
    
    return render_template(
        'resident/schedule_interview.html',
        application=application,
        grouped_slots=grouped_slots,
        sorted_dates=sorted_dates
    )

@app.route('/police/appointment/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def conduct_interview(appointment_id):
    if current_user.userType != 'police':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    from models import Appointment, AddressApplication, ResidentInfo, User
    
    # Get the appointment
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.officer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('police_dashboard'))
    
    # Get application and resident info
    application = AddressApplication.query.get(appointment.application_id)
    resident = User.query.get(appointment.resident_id)
    resident_info = ResidentInfo.query.filter_by(user_id=resident.id).first()
    
    if request.method == 'POST':
        decision = request.form.get('decision')
        officer_notes = request.form.get('officer_notes')
        
        if decision == 'approve':
            # Complete the interview
            appointment.status = 'completed'
            appointment.meeting_notes = officer_notes
            
            # Approve the application
            application.status = 'approved'
            application.officer_notes = officer_notes
            
            # Create a certificate
            from models import AddressCertificate
            from datetime import datetime, timedelta
            import uuid
            
            certificate_number = f"AM-{uuid.uuid4().hex[:8].upper()}"
            issue_date = datetime.now()
            expiry_date = issue_date + timedelta(days=365)  # Valid for 1 year
            
            certificate = AddressCertificate(
                application_id=application.id,
                certificate_number=certificate_number,
                issue_date=issue_date,
                expiry_date=expiry_date,
                pdf_path='/static/certificates/demo_certificate.pdf'  # Demo path
            )
            
            db.session.add(certificate)
            flash('Application has been approved and certificate generated.', 'success')
            
        elif decision == 'reject':
            # Complete the interview
            appointment.status = 'completed'
            appointment.meeting_notes = officer_notes
            
            # Reject the application
            application.status = 'rejected'
            application.officer_notes = officer_notes
            
            flash('Application has been rejected.', 'info')
            
        elif decision == 'reschedule':
            # Mark the appointment as needing rescheduling
            appointment.status = 'cancelled'
            appointment.meeting_notes = officer_notes
            
            # Update application status
            application.status = 'leader_approved'  # Back to scheduling stage
            application.officer_notes = officer_notes
            
            flash('Interview has been cancelled. The resident will need to reschedule.', 'warning')
        
        db.session.commit()
        return redirect(url_for('police_dashboard'))
    
    return render_template(
        'police/interview.html',
        appointment=appointment,
        application=application,
        resident_info=resident_info
    )

# Create database tables
with app.app_context():
    import models  # Import to register models
    db.create_all()
    logging.info("Database tables created (or ensured they exist)")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
