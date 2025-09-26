from datetime import datetime
from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullName = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    userType = db.Column(db.String(20), nullable=False)  # resident, leader, police
    isVerified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    resident_info = db.relationship('ResidentInfo', backref='user', uselist=True, lazy='dynamic',
                                  foreign_keys='ResidentInfo.user_id')
    leader_info = db.relationship('LeaderInfo', backref='user', uselist=False, lazy=True)
    police_info = db.relationship('PoliceInfo', backref='user', uselist=False, lazy=True)
    applications = db.relationship('AddressApplication', backref='applicant', lazy=True, 
                                 foreign_keys='AddressApplication.applicant_id')
    appointments = db.relationship('Appointment', backref='resident', lazy=True,
                                 foreign_keys='Appointment.resident_id')

    def __repr__(self):
        return f'<User {self.email}>'


class ResidentInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    firstName = db.Column(db.String(50), nullable=False)
    lastName = db.Column(db.String(50), nullable=False)
    idNumber = db.Column(db.String(20), nullable=False)
    phoneNumber = db.Column(db.String(20), nullable=False)
    settlement = db.Column(db.String(100), nullable=False)
    unitNumber = db.Column(db.String(20), nullable=False)
    postalCode = db.Column(db.String(10), nullable=False)
    isOwner = db.Column(db.Boolean, nullable=False)
    municipality = db.Column(db.String(100), nullable=False)
    wardNumber = db.Column(db.Integer, nullable=False)
    councillorName = db.Column(db.String(100), nullable=False)
    idPhotoPath = db.Column(db.String(200))  # Path to stored ID photo
    facePhotoPath = db.Column(db.String(200))  # Path to stored face photo
    
    def __repr__(self):
        return f'<ResidentInfo {self.firstName} {self.lastName}>'


class LeaderInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    firstName = db.Column(db.String(50), nullable=False)
    lastName = db.Column(db.String(50), nullable=False)
    idNumber = db.Column(db.String(20), nullable=False)
    phoneNumber = db.Column(db.String(20), nullable=False)
    municipality = db.Column(db.String(100), nullable=False)
    wardNumber = db.Column(db.Integer, nullable=False)
    officeLocation = db.Column(db.String(100), nullable=False)
    settlement = db.Column(db.String(100), nullable=False)
    unitNumber = db.Column(db.String(20), nullable=False)
    postalCode = db.Column(db.String(10), nullable=False)
    idPhotoPath = db.Column(db.String(200))  # Path to stored ID photo
    facePhotoPath = db.Column(db.String(200))  # Path to stored face photo
    isApproved = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<LeaderInfo {self.firstName} {self.lastName}>'


class PoliceInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    firstName = db.Column(db.String(50), nullable=False)
    lastName = db.Column(db.String(50), nullable=False)
    idNumber = db.Column(db.String(20), nullable=True)  # ID not required for police
    phoneNumber = db.Column(db.String(20), nullable=False)
    badgeNumber = db.Column(db.String(20), nullable=False)
    rank = db.Column(db.String(50), nullable=False)
    stationName = db.Column(db.String(100), nullable=False)
    municipality = db.Column(db.String(100), nullable=False)
    postalCode = db.Column(db.String(10), nullable=False)
    idPhotoPath = db.Column(db.String(200))  # Path to stored ID photo
    facePhotoPath = db.Column(db.String(200))  # Path to stored face photo
    isApproved = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<PoliceInfo {self.firstName} {self.lastName}>'


# Status options: "pending", "leader_approved", "interview_scheduled", "interview_completed", "approved", "rejected"
class AddressApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    officer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(30), default="pending", nullable=False)
    leader_notes = db.Column(db.Text)
    officer_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    leader = db.relationship('User', foreign_keys=[leader_id], backref='leader_applications')
    officer = db.relationship('User', foreign_keys=[officer_id], backref='officer_applications')
    
    def __repr__(self):
        return f'<AddressApplication {self.id}>'


# Status options: "scheduled", "completed", "cancelled"
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('address_application.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    status = db.Column(db.String(20), default="scheduled", nullable=False)
    meeting_notes = db.Column(db.Text)
    recording_path = db.Column(db.String(200))  # Path to stored recording (if any)
    
    # Relationships
    officer = db.relationship('User', foreign_keys=[officer_id], backref='officer_appointments')
    application = db.relationship('AddressApplication', backref='appointment')
    
    def __repr__(self):
        return f'<Appointment {self.id}>'


# For storing officers' recurring weekly schedule
class WeeklySchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    officer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time, nullable=False)  # Time only, no date
    end_time = db.Column(db.Time, nullable=False)    # Time only, no date
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    officer = db.relationship('User', backref='weekly_schedules')
    breaks = db.relationship('ScheduledBreak', backref='schedule', cascade="all, delete-orphan")

# For storing configured breaks within a weekly schedule
class ScheduledBreak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('weekly_schedule.id'), nullable=False)
    break_start_time = db.Column(db.Time, nullable=False)  # Time only, no date
    break_end_time = db.Column(db.Time, nullable=False)    # Time only, no date
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ScheduledBreak {self.break_start_time}-{self.break_end_time}>'

# For storing available time slots for officers (generated from weekly schedules)
class AvailableTimeSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    officer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    weekly_schedule_id = db.Column(db.Integer, db.ForeignKey('weekly_schedule.id'), nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_booked = db.Column(db.Boolean, default=False)
    
    # Location info (copied from officer's details when slot is created)
    municipality = db.Column(db.String(100), nullable=True)
    station_name = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(10), nullable=True)
    
    # Relationships
    officer = db.relationship('User', backref='available_slots')
    weekly_schedule = db.relationship('WeeklySchedule', backref='generated_slots')
    
    def __repr__(self):
        return f'<AvailableTimeSlot {self.start_time}>'


# For generating and storing proof of address certificates
class AddressCertificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('address_application.id'), nullable=False)
    certificate_number = db.Column(db.String(50), unique=True, nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=False)
    pdf_path = db.Column(db.String(200))  # Path to stored PDF certificate
    
    # Relationship
    application = db.relationship('AddressApplication', backref='certificate')
    
    def __repr__(self):
        return f'<AddressCertificate {self.certificate_number}>'