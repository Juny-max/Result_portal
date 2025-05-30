from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager

class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


import secrets
import string

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    admin_logs = db.relationship('AuditLog', backref='admin', lazy='dynamic')
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    user_type = db.Column(db.Enum('admin', 'student', name='user_types'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    first_login = db.Column(db.Boolean, default=True, nullable=False)
    student = db.relationship('Student', backref='user', uselist=False, lazy=True)
    
    @classmethod
    def generate_random_password(cls, length=12):
        """Generate a random password with letters, digits, and special characters"""
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
        while True:
            password = ''.join(secrets.choice(alphabet) for _ in range(length))
            # Ensure password has at least one of each character type
            if (any(c.islower() for c in password) 
                and any(c.isupper() for c in password) 
                and any(c.isdigit() for c in password)):
                return password
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.user_type == 'admin'
        
    def unread_notifications_count(self):
        return self.notifications.filter_by(is_read=False).count()

# Association table for many-to-many relationship between Program and Course
program_courses = db.Table('program_courses',
    db.Column('program_id', db.Integer, db.ForeignKey('programs.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('courses.id'), primary_key=True)
)

class Program(db.Model):
    __tablename__ = 'programs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    archived = db.Column(db.Boolean, default=False, nullable=False)
    courses = db.relationship('Course', secondary=program_courses, back_populates='programs')
    students = db.relationship('Student', backref='program', lazy=True)

class Level(db.Model):
    __tablename__ = 'levels'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(100))
    archived = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<Level {self.name}>'

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    index_number = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)  # Corrected
    archived = db.Column(db.Boolean, default=False, nullable=False)
    results = db.relationship('Result', backref='student', lazy=True)
    level = db.relationship('Level', backref='students', lazy=True)  # Corrected

    GRADE_POINTS = {
        'A': 4.0,
        'A-': 3.85,
        'B+': 3.5,
        'B': 3.0,
        'C+': 2.5,
        'C': 2.0,
        'D': 1.5,
        'E': 1.0,
        'F': 0.0
    }

    def calculate_gpa_for_semester(self, semester, academic_year):
        """
        Calculate GPA for a specific semester and academic year.
        Handles repeated courses (uses latest result), and skips missing grades.
        """
        # Get all results for this student, semester, and year
        filtered = [r for r in self.results if str(r.semester) == str(semester) and str(r.academic_year) == str(academic_year) and r.grade]
        # Handle repeated courses: keep only the latest result for each course
        latest_results = {}
        for r in sorted(filtered, key=lambda x: x.uploaded_at):
            latest_results[r.course_id] = r
        total_points = 0
        total_credits = 0
        for r in latest_results.values():
            if not r.course:
                continue  # skip if course is missing
            gp = self.GRADE_POINTS.get(r.grade, 0.0)
            ch = r.course.credit_hours
            total_points += gp * ch
            total_credits += ch
        return round(total_points / total_credits, 2) if total_credits else 0.0

    def calculate_cgpa_for_year(self, academic_year, semesters=('1', '2')):
        """
        Calculate CGPA for an academic year as the average of semester GPAs.
        """
        gpas = []
        for sem in semesters:
            gpa = self.calculate_gpa_for_semester(sem, academic_year)
            if gpa > 0:
                gpas.append(gpa)
        return round(sum(gpas) / len(gpas), 2) if gpas else 0.0

    # Legacy method (for compatibility, not recommended for new code)
    def calculate_gpa(self, semester=None, academic_year=None):
        if semester and academic_year:
            return self.calculate_gpa_for_semester(semester, academic_year)
        elif academic_year:
            return self.calculate_cgpa_for_year(academic_year)
        else:
            return 0.0

    def calculate_overall_cgpa(self):
        """
        Calculate true cumulative CGPA (all levels/years/semesters),
        using the weighted average of all grade points and credit hours.
        Only the latest attempt for each course in each semester/year is used.
        """
        results = [r for r in self.results if r.grade]
        # Use latest result for each (course, semester, academic_year)
        latest_results = {}
        for r in sorted(results, key=lambda x: x.uploaded_at):
            key = (r.course_id, str(r.semester), str(r.academic_year))
            latest_results[key] = r
        total_points = 0
        total_credits = 0
        for r in latest_results.values():
            if not r.course:
                continue  # skip if course is missing
            gp = self.GRADE_POINTS.get(r.grade, 0.0)
            ch = r.course.credit_hours
            total_points += gp * ch
            total_credits += ch
        return round(total_points / total_credits, 2) if total_credits else 0.0

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    credit_hours = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)
    level = db.Column(db.Integer, nullable=True)
    semester = db.Column(db.String(20), nullable=True)
    results = db.relationship('Result', backref='course', lazy=True)
    programs = db.relationship('Program', secondary=program_courses, back_populates='courses')
    
    def __repr__(self):
        return f'<Course {self.code} - {self.title}>'

class Result(db.Model):
    __tablename__ = 'results'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    score = db.Column(db.Numeric(5, 2), nullable=False)
    grade = db.Column(db.String(2), nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    remarks = db.Column(db.Text)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    student_level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=True)
    student_level = db.relationship('Level', backref='results', lazy=True)
    
    def determine_grade(self):
        score = float(self.score)
        if score >= 80:
            return 'A'
        elif score >= 70:
            return 'A-'
        elif score >= 65:
            return 'B+'
        elif score >= 60:
            return 'B'
        elif score >= 55:
            return 'C+'
        elif score >= 50:
            return 'C'
        elif score >= 45:
            return 'D'
        elif score >= 40:
            return 'E'
        else:
            return 'F'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))