import io
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template, flash, redirect, url_for, request, current_app, send_file, jsonify, make_response, render_template_string
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import csv
from datetime import datetime
from flask import Blueprint
from app import db
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
import pandas as pd
from io import BytesIO
import shutil
import tempfile
import zipfile
import subprocess
from flask import send_from_directory

from app.admin.forms import UploadResultsForm, AddCourseForm, EditStudentForm, EnterResultForm, StudentSearchForm
from app.models import User, Student, Course, Result, Program, Level, AuditLog
from app.utils.helpers import allowed_file
from app.utils.audit_logger import log_admin_action
#from app.models import ProgramCourse

# Create and configure the admin blueprint
bp = Blueprint('admin', __name__)

@bp.route('/program/<int:program_id>/students')
@login_required
def view_students(program_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    program = Program.query.get_or_404(program_id)
    students = Student.query.filter_by(program_id=program_id, archived=0).all()
    
    return render_template('admin/program_students.html', 
                         program=program, 
                         students=students)

@bp.route('/program/<int:program_id>/export')
@login_required
def export_program_students(program_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    program = Program.query.get_or_404(program_id)
    students = db.session.query(Student, User).join(User, Student.user_id == User.id)\
                .filter(Student.program_id == program_id, Student.archived == 0).all()
    
    # Create a DataFrame
    data = []
    for student, user in students:
        data.append({
            'Index Number': student.index_number,
            'Full Name': student.full_name,
            'Email': user.email,  # Get email from User model
            'Program': program.name,
            'Level': student.level.name if student.level else 'N/A',
            'Status': 'Active' if not student.archived else 'Archived'
        })
    
    df = pd.DataFrame(data)
    
    # Create a BytesIO buffer
    output = BytesIO()
    # Create a shorter worksheet name (max 31 chars)
    sheet_name = f"{program.name[:20]}"  # Use first 20 chars of program name
    sheet_name = sheet_name.replace(' ', '')  # Remove spaces to fit more characters
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])  # Ensure max 31 chars
    
    # Create a safe filename using program name
    safe_program_name = ''.join(c if c.isalnum() else '_' for c in program.name)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{safe_program_name}_students_{timestamp}.xlsx"
    
    # Create response
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@bp.route('/programs/export')
@login_required
def export_all_programs():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    # Get all programs with student counts
    program_data = db.session.query(
        Program,
        func.count(Student.id).label('student_count')
    ).outerjoin(Student, (Student.program_id == Program.id) & (Student.archived == 0))\
     .group_by(Program.id).all()
    
    # Create a DataFrame
    data = [{
        'Program Name': program.name,
        'Student Count': student_count,
        'Status': 'Active' if not program.archived else 'Archived'
    } for program, student_count in program_data]
    
    df = pd.DataFrame(data)
    
    # Create a BytesIO buffer
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Programs Summary")
    
    # Create response
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"programs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    # Total students count (not archived)
    total_students = Student.query.filter_by(archived=0).count()

    # Programs and student counts
    program_counts = (
        db.session.query(Program, func.count(Student.id))
        .outerjoin(Student, (Student.program_id == Program.id) & (Student.archived == 0))
        .group_by(Program.id)
        .all()
    )

    # Recent results with related info
    recent_results = (
        db.session.query(Result)
        .join(Student, Result.student_id == Student.id)
        .join(Program, Student.program_id == Program.id)
        .join(Course, Result.course_id == Course.id)
        .order_by(Result.uploaded_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'admin/dashboard.html',
        total_students=total_students,
        program_counts=program_counts,
        recent_results=recent_results,
        student_count=total_students,  # if used elsewhere
        archived_count=Student.query.filter_by(archived=1).count(),
        program_count=Program.query.count(),
        course_count=Course.query.count()
    )

@bp.route('/audit_logs')
@login_required
def audit_logs():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import AuditLog
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template('admin/audit_logs.html', logs=logs)

    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    total_students = Student.query.count()
    total_courses = Course.query.count()
    
    # Get recent results with program names
    recent_results = Result.query.join(Student).join(Program).order_by(Result.uploaded_at.desc()).limit(5).all()
    
    # Get all programs and count of students per program (excluding archived)
    program_counts = db.session.query(
        Program.name, db.func.count(Student.id)
    ).join(Student, Program.id == Student.program_id).filter(Student.archived == False).group_by(Program.name).all()

    return render_template('admin/dashboard.html', 
                         title='Admin Dashboard',
                         total_students=total_students,
                         total_courses=total_courses,
                         recent_results=recent_results,
                         program_counts=program_counts)


@bp.route('/send_notification', methods=['GET', 'POST'])
@login_required
def send_notification():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.admin.forms import SendNotificationForm
    from app.models import Student, Notification
    form = SendNotificationForm()
    # Populate student choices
    students = Student.query.filter_by(archived=False).all()
    form.student.choices = [(s.id, f"{s.full_name} ({s.index_number})") for s in students]
    if form.validate_on_submit():
        student = Student.query.get(form.student.data)
        notif = Notification(user_id=student.user_id, message=form.message.data)
        db.session.add(notif)
        db.session.commit()
        # Log audit
        from app.models import AuditLog
        log = AuditLog(admin_id=current_user.id, action='Send Notification', target_type='Student', target_id=student.id, details=f'Sent notification to {student.full_name} ({student.index_number})')
        db.session.add(log)
        db.session.commit()
        flash('Notification sent!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/send_notification.html', form=form)

@bp.route('/broadcast_message', methods=['GET', 'POST'])
@login_required
def broadcast_message():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
        
    from app.admin.forms import BroadcastMessageForm
    from app.models import Student, Notification, Program, Level
    
    form = BroadcastMessageForm()
    
    # Set choices for the form
    try:
        form.program.choices = [('', 'All Programs')] + [(str(p.id), p.name) for p in Program.query.filter_by(archived=False).order_by(Program.name).all()]
        form.level.choices = [('', 'All Levels')] + [(str(l.id), l.name) for l in Level.query.filter_by(archived=False).order_by(Level.name).all()]
    except Exception as e:
        current_app.logger.error(f"Error loading form choices: {str(e)}")
        flash('Error loading form data. Please try again.', 'error')
        form.program.choices = [('', 'All Programs')]
        form.level.choices = [('', 'All Levels')]
    
    if form.validate_on_submit():
        try:
            # Query for students based on filters
            students_query = Student.query.filter_by(archived=False)
            
            # Apply program filter if selected
            program_id = form.program.data
            if program_id and program_id != '':
                students_query = students_query.filter(Student.program_id == program_id)
                
            # Apply level filter if selected
            level_id = form.level.data
            if level_id and level_id != '':
                students_query = students_query.filter(Student.level_id == level_id)
                
            students = students_query.all()
            
            # Create notifications for each student
            for student in students:
                notification = Notification(
                    user_id=student.user_id,
                    message=form.message.data,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.session.add(notification)
            
            # Log the broadcast action
            log = AuditLog(
                admin_id=current_user.id,
                action='Broadcast Notification',
                target_type='Student',
                target_id=None,
                details=f'Broadcasted notification to {len(students)} students',
                timestamp=datetime.utcnow()
            )
            db.session.add(log)
            
            db.session.commit()
            
            flash(f'Broadcast sent to {len(students)} students!', 'success')
            return redirect(url_for('admin.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            error_details = str(e)
            current_app.logger.error(f"Error sending broadcast: {error_details}", exc_info=True)
            flash(f'Error: {error_details}', 'danger')
            flash('Failed to send broadcast. Please check the form and try again.', 'error')
    
    return render_template('admin/broadcast_message.html', form=form)

@bp.route('/download_results_template')
@login_required
def download_results_template():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    # Create a sample CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header with level field
    writer.writerow(['index_number', 'course_code', 'score', 'semester', 'academic_year', 'level', 'remarks'])
    
    # Write sample data with level
    writer.writerow(['INDEX001', 'MATH101', '85.5', 'First', '2024/2025', '100', 'Excellent performance'])
    writer.writerow(['INDEX002', 'PHYS101', '72.0', 'First', '2024/2025', '100', 'Good work'])
    
    # Create response
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='results_template.csv',
        max_age=0
    )

@bp.route('/upload_results', methods=['GET', 'POST'])
@login_required
def upload_results():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    form = UploadResultsForm()
    if form.validate_on_submit():
        if form.file.data:
            file = form.file.data
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                
                # Ensure upload directory exists
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                
                try:
                    results_added = 0
                    results_skipped = 0
                    
                    # Read the file based on its extension
                    if file.filename.lower().endswith(('.xls', '.xlsx')):
                        import pandas as pd
                        df = pd.read_excel(filepath)
                        # Convert column names to lowercase and strip whitespace
                        df.columns = df.columns.str.strip().str.lower()
                        # Replace NaN with empty string
                        df = df.fillna('')
                        records = df.to_dict('records')
                    else:
                        with open(filepath, 'r', encoding='utf-8-sig') as csvfile:
                            reader = csv.DictReader(csvfile)
                            # Convert fieldnames to lowercase and strip whitespace
                            reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
                            records = list(reader)
                    
                    current_app.logger.info(f'Processing {len(records)} records from {filename}')
                    
                    for i, row in enumerate(records, 1):
                        try:
                            # Clean up the data
                            row = {k.strip().lower() if isinstance(k, str) else k: 
                                  v.strip() if isinstance(v, str) else v for k, v in row.items()}
                            
                            current_app.logger.debug(f'Processing row {i}: {row}')
                            
                            # Get required fields with case-insensitive matching
                            index_number = row.get('index_number', '').strip()
                            course_code = row.get('course_code', '').strip()
                            
                            if not index_number or not course_code:
                                current_app.logger.warning(f'Skipping row {i}: Missing required fields')
                                results_skipped += 1
                                continue
                            
                            # Get student and course
                            student = Student.query.filter(
                                func.lower(Student.index_number) == index_number.lower().strip()
                            ).first()
                            
                            # Handle potential spaces in course codes
                            course = Course.query.filter(
                                func.lower(func.replace(Course.code, ' ', '')) == course_code.lower().replace(' ', '')
                            ).first()
                            
                            # If still not found, try exact match with stripped spaces
                            if not course and ' ' in course_code:
                                course = Course.query.filter(
                                    func.lower(Course.code) == course_code.lower().strip()
                                ).first()
                            
                            if not student:
                                current_app.logger.warning(f'Student not found: {index_number}')
                                results_skipped += 1
                                continue
                                
                            if not course:
                                current_app.logger.warning(f'Course not found: {course_code}')
                                results_skipped += 1
                                continue
                            
                            # Check if result already exists for this student and course
                            semester = row.get('semester', '').strip()
                            academic_year = row.get('academic_year', '').strip()
                            level = row.get('level', '').strip()
                            
                            if not all([semester, academic_year, level]):
                                current_app.logger.warning(f'Missing required fields for student {index_number}, course {course_code}')
                                results_skipped += 1
                                continue
                                
                            # Convert semester to numeric format (1 or 2)
                            semester = semester.lower().strip()
                            if 'first' in semester or '1' in semester:
                                semester = '1'
                            elif 'second' in semester or '2' in semester:
                                semester = '2'
                            else:
                                current_app.logger.warning(f'Invalid semester format: {semester}. Must be "First/1" or "Second/2"')
                                results_skipped += 1
                                continue
                            
                            # Convert level to level ID (100->1, 200->2, etc.)
                            try:
                                level_num = int(level)
                                if level_num not in [100, 200, 300, 400, 500]:
                                    raise ValueError('Level must be 100, 200, 300, 400, or 500')
                                # Convert to level ID (100 -> 1, 200 -> 2, etc.)
                                level_id = level_num // 100
                                # Find the level in the database
                                level_obj = Level.query.filter_by(id=level_id).first()
                                if not level_obj:
                                    raise ValueError(f'Level {level_num} not found in database')
                                level = level_id
                            except (ValueError, TypeError) as e:
                                current_app.logger.warning(f'Invalid level format for student {index_number}, course {course_code}: {level}. Error: {str(e)}')
                                results_skipped += 1
                                continue
                            
                            # Try to convert score to float
                            try:
                                score = float(row.get('score', 0))
                                if score < 0 or score > 100:
                                    raise ValueError('Score must be between 0 and 100')
                            except (ValueError, TypeError) as e:
                                current_app.logger.warning(f'Invalid score format for student {index_number}, course {course_code}: {row.get("score")}')
                                results_skipped += 1
                                continue
                            
                            # Check for existing result with more flexible matching
                            existing_result = Result.query.filter(
                                Result.student_id == student.id,
                                Result.course_id == course.id,
                                func.lower(Result.semester) == semester.lower().strip(),
                                Result.academic_year == academic_year.strip(),
                                Result.student_level_id == level
                            ).first()
                            
                            # Log the search criteria for debugging
                            current_app.logger.info(f'Checking for existing result - Student: {student.id}, Course: {course.id}, Semester: {semester}, Year: {academic_year}, Level ID: {level}')
                            current_app.logger.info(f'Student level: {student.level_id}, Course level: {level}')
                            
                            if existing_result:
                                current_app.logger.info(f'Updating existing result for {index_number} in {course_code}')
                                existing_result.score = score
                                existing_result.remarks = row.get('remarks', '').strip()
                                existing_result.uploaded_by = current_user.id
                                existing_result.grade = existing_result.determine_grade()
                                existing_result.updated_at = datetime.utcnow()
                            else:
                                current_app.logger.info(f'Adding new result for {index_number} in {course_code}')
                                result = Result(
                                    student_id=student.id,
                                    course_id=course.id,
                                    score=score,
                                    semester=semester,
                                    academic_year=academic_year,
                                    student_level_id=level,
                                    remarks=row.get('remarks', '').strip(),
                                    uploaded_by=current_user.id
                                )
                                result.grade = result.determine_grade()
                                db.session.add(result)
                            
                            results_added += 1
                            
                            # Commit in batches of 50
                            if results_added % 50 == 0:
                                db.session.commit()
                                
                        except Exception as e:
                            current_app.logger.error(f'Error processing row {i}: {str(e)}', exc_info=True)
                            results_skipped += 1
                            continue
                    
                    db.session.commit()
                    
                    if results_added > 0:
                        flash(f'Successfully processed {results_added} results. {results_skipped} records were skipped.', 'success')
                        current_app.logger.info(f'Successfully processed {results_added} results. {results_skipped} records were skipped.')
                    else:
                        flash('No valid results were processed. Please check the file format and try again.', 'warning')
                        
                except Exception as e:
                    db.session.rollback()
                    error_msg = f'Error processing file: {str(e)}'
                    current_app.logger.error(error_msg, exc_info=True)
                    flash(error_msg, 'danger')
                    
                finally:
                    try:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    except Exception as e:
                        current_app.error(f'Error removing temporary file: {str(e)}')
            else:
                flash('Only CSV and Excel files are allowed', 'danger')
        else:
            # Handle manual form submission
            student = Student.query.filter_by(index_number=form.index_number.data).first()
            course = Course.query.filter_by(code=form.course_code.data).first()
            
            if not student or not course:
                flash('Student or Course not found', 'danger')
                return redirect(url_for('admin.upload_results'))
            
            result = Result(
                student_id=student.id,
                course_id=course.id,
                score=form.score.data,
                semester=form.semester.data,
                academic_year=form.academic_year.data,
                remarks=form.remarks.data,
                uploaded_by=current_user.id
            )
            result.grade = result.determine_grade()
            db.session.add(result)
            db.session.commit()
            flash('Result added successfully!', 'success')
        
        return redirect(url_for('admin.upload_results'))
    
    return render_template('admin/upload_results.html', title='Upload Results', form=form)

@bp.route('/manage_courses')
@login_required
def manage_courses():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
        
    # Check for any flash messages from the add_course route
    if request.referrer and 'add_course' in request.referrer:
        # The flash message is already set in add_course, no need to set it again
        pass
        
    courses = Course.query.all()
    programs = Program.query.filter_by(archived=False).all()
    form = AddCourseForm()
    
    # Populate program choices for the form
    form.program_id.choices = [(p.id, p.name) for p in programs]
    
    # If there are no programs, add a default choice
    if not form.program_id.choices:
        form.program_id.choices = [('', 'No programs available')]
    
    return render_template('admin/manage_courses.html', 
                         title='Manage Courses', 
                         courses=courses, 
                         programs=programs,
                         form=form,
                         show_programs=False,
                         show_course_modal=False)

@bp.route('/manage_programs', defaults={'program_id': None})
@bp.route('/manage_programs/<int:program_id>')
@login_required
def manage_programs(program_id=None):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program, Course, Student
    from app.admin.forms import AddCourseForm  # Import AddCourseForm
    
    programs = Program.query.filter_by(archived=False).all()
    archived_programs = Program.query.filter_by(archived=True).all()
    all_courses = Course.query.all()
    selected_program = Program.query.get(program_id) if program_id else None
    
    # Find unique student programs not yet in Program table
    student_programs = set([s.program.name for s in Student.query.join(Program).distinct() if s.program])
    program_names = set([p.name for p in programs] + [p.name for p in archived_programs])
    missing_programs = sorted(list(student_programs - program_names))
    
    # Create form instance for the add course modal
    form = AddCourseForm()
    
    # Populate program choices for the form
    form.program_id.choices = [(p.id, p.name) for p in Program.query.filter_by(archived=False).all()]
    
    # If there are no programs, add a default choice
    if not form.program_id.choices:
        form.program_id.choices = [('', 'No programs available')]
    
    return render_template('admin/manage_courses.html', 
                         title='Manage Programs',
                         show_programs=True, 
                         programs=programs, 
                         archived_programs=archived_programs,
                         selected_program=selected_program, 
                         all_courses=all_courses,
                         missing_programs=missing_programs,
                         form=form,  # Pass form to template
                         show_course_modal=False)  # Don't show course modal by default

@bp.route('/import_student_program', methods=['POST'])
@login_required
def import_student_program():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program
    name = request.form.get('import_program_name')
    if name:
        program = Program(name=name)
        db.session.add(program)
        db.session.commit()
        flash(f'Imported program "{name}" from students.', 'success')
    else:
        flash('No program name provided.', 'danger')
    return redirect(url_for('admin.manage_programs'))

@bp.route('/edit_program/<int:program_id>', methods=['GET', 'POST'])
@login_required
def edit_program(program_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program
    program = Program.query.get_or_404(program_id)
    if request.method == 'POST':
        name = request.form.get('edit_program_name')
        description = request.form.get('edit_program_description')
        if name:
            program.name = name
            program.description = description
            db.session.commit()
            flash('Program updated successfully!', 'success')
            return redirect(url_for('admin.manage_programs', program_id=program_id))
        else:
            flash('Program name is required.', 'danger')
    return render_template('admin/edit_program.html', program=program)

@bp.route('/add_program', methods=['POST'])
@login_required
def add_program():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program
    name = request.form.get('name')
    description = request.form.get('description')
    if name:
        program = Program(name=name, description=description)
        db.session.add(program)
        db.session.commit()
        flash('Program added successfully!', 'success')
    else:
        flash('Program name is required.', 'danger')
    return redirect(url_for('admin.manage_programs'))

@bp.route('/delete_program/<int:program_id>', methods=['POST'])
@login_required
def delete_program(program_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program
    program = Program.query.get_or_404(program_id)
    db.session.delete(program)
    db.session.commit()
    flash('Program deleted successfully!', 'success')
    return redirect(url_for('admin.manage_programs'))

@bp.route('/archive_program/<int:program_id>', methods=['POST'])
@login_required
def archive_program(program_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program
    program = Program.query.get_or_404(program_id)
    program.archived = True
    db.session.commit()
    flash('Program archived successfully!', 'success')
    return redirect(url_for('admin.manage_programs'))

@bp.route('/restore_program/<int:program_id>', methods=['POST'])
@login_required
def restore_program(program_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program
    program = Program.query.get_or_404(program_id)
    program.archived = False
    db.session.commit()
    flash('Program restored successfully!', 'success')
    return redirect(url_for('admin.manage_programs'))

@bp.route('/add_course_to_program/<int:program_id>', methods=['POST'])
@login_required
def add_course_to_program(program_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program, Course
    program = Program.query.get_or_404(program_id)
    course_id = request.form.get('course_id')
    course = Course.query.get(course_id)
    if course and course not in program.courses:
        program.courses.append(course)
        db.session.commit()
        flash('Course added to program.', 'success')
    else:
        flash('Invalid course selection or course already assigned.', 'danger')
    return redirect(url_for('admin.manage_programs', program_id=program_id))

@bp.route('/remove_course_from_program/<int:program_id>/<int:course_id>', methods=['POST'])
@login_required
def remove_course_from_program(program_id, course_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.models import Program, Course
    program = Program.query.get_or_404(program_id)
    course = Course.query.get_or_404(course_id)
    if course in program.courses:
        program.courses.remove(course)
        db.session.commit()
        flash('Course removed from program.', 'success')
    else:
        flash('Course not assigned to program.', 'danger')
    return redirect(url_for('admin.manage_programs', program_id=program_id))

@bp.route('/edit_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
        
    course = Course.query.get_or_404(course_id)
    form = AddCourseForm(obj=course)
    
    # Set program choices
    all_programs = Program.query.filter_by(archived=False).order_by(Program.name).all()
    form.program_id.choices = [(p.id, p.name) for p in all_programs]
    
    # Get current program for the course (first one if exists)
    current_program = course.programs[0] if course.programs else None
    
    if form.validate_on_submit():
        course.code = form.course_code.data
        course.title = form.course_title.data
        course.credit_hours = form.credit_hours.data
        course.level = form.level.data
        course.semester = form.semester.data
        course.description = form.description.data
        
        # Update program relationship
        selected_program = Program.query.get(form.program_id.data)
        if selected_program and selected_program != current_program:
            # Clear existing programs and add the new one
            course.programs = [selected_program]
        
        db.session.commit()
        
        # Log audit
        from app.models import AuditLog
        log = AuditLog(
            admin_id=current_user.id, 
            action='Edit Course', 
            target_type='Course', 
            target_id=course.id, 
            details=f'Edited course {course.title} ({course.code})'
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Course updated successfully!', 'success')
        return redirect(url_for('admin.manage_courses'))
        
    # Set form data for GET request
    form.course_code.data = course.code
    form.course_title.data = course.title
    form.credit_hours.data = course.credit_hours
    form.level.data = course.level
    form.semester.data = course.semester
    form.description.data = course.description
    
    # Set the current program in the form if it exists
    if current_program:
        form.program_id.data = current_program.id
    
    # Get all programs for the template
    programs = Program.query.filter_by(archived=False).order_by(Program.name).all()
    
    return render_template('admin/add_course.html', 
                         title='Edit Course', 
                         form=form,
                         programs=programs,
                         selected_program_id=current_program.id if current_program else None)

@bp.route('/delete_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def delete_course(course_id):
    if not current_user.is_admin():
        if request.is_json:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        return redirect(url_for('main.index'))
        
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        try:
            # Log audit before deleting
            from app.models import AuditLog
            log = AuditLog(
                admin_id=current_user.id,
                action='Delete Course',
                target_type='Course',
                target_id=course.id,
                details=f'Deleted course {course.title} ({course.code})'
            )
            db.session.add(log)
            
            db.session.delete(course)
            db.session.commit()
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': 'Course deleted successfully!'
                })
                
            flash('Course deleted successfully!', 'success')
            return redirect(url_for('admin.manage_courses'))
            
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': f'Error deleting course: {str(e)}'
                }), 500
            flash(f'Error deleting course: {str(e)}', 'danger')
            return redirect(url_for('admin.manage_courses'))
    
    # Handle GET request (for backward compatibility)
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Log audit before deleting
            from app.models import AuditLog
            log = AuditLog(
                admin_id=current_user.id,
                action='Delete Course',
                target_type='Course',
                target_id=course.id,
                details=f'Deleted course {course.title} ({course.code})'
            )
            db.session.add(log)
            
            db.session.delete(course)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Course deleted successfully!'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Error deleting course: {str(e)}'
            }), 500
    else:
        # Non-AJAX request handling
        try:
            # Log audit before deleting
            from app.models import AuditLog
            log = AuditLog(
                admin_id=current_user.id,
                action='Delete Course',
                target_type='Course',
                target_id=course.id,
                details=f'Deleted course {course.title} ({course.code})'
            )
            db.session.add(log)
            
            db.session.delete(course)
            db.session.commit()
            flash('Course deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting course: {str(e)}', 'danger')
        
        return redirect(url_for('admin.manage_courses'))

@bp.route('/add_course', methods=['GET', 'POST'])
@login_required
def add_course():
    if not current_user.is_admin():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        return redirect(url_for('main.index'))
        
    from app.models import Program, Course, AuditLog
    programs = Program.query.filter_by(archived=False).all()
    form = AddCourseForm()
    is_modal = request.form.get('is_modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        program_id = request.form.get('program_id')
        
        # Validate form
        if not form.validate_on_submit():
            if is_modal:
                return jsonify({
                    'success': False, 
                    'message': 'Please correct the errors in the form.',
                    'errors': form.errors
                }), 400
            flash('Please correct the errors in the form.', 'danger')
            return render_template('admin/add_course.html', 
                                title='Add Course', 
                                form=form, 
                                programs=programs, 
                                selected_program_id=program_id)
        
        # Validate program selection
        if not program_id or program_id == '':
            if is_modal:
                return jsonify({
                    'success': False, 
                    'message': 'You must select a program before adding a course.'
                }), 400
            flash('You must select a program before adding a course.', 'program_error')
            return render_template('admin/add_course.html', 
                                title='Add Course', 
                                form=form, 
                                programs=programs, 
                                selected_program_id=program_id)
        
        # Check if course code already exists
        existing_course = Course.query.filter_by(code=form.course_code.data).first()
        if existing_course:
            if is_modal:
                return jsonify({
                    'success': False, 
                    'message': 'A course with this code already exists.'
                }), 400
            flash('A course with this code already exists.', 'danger')
            return render_template('admin/add_course.html',
                                title='Add Course',
                                form=form,
                                programs=programs,
                                selected_program_id=program_id)
        
        try:
            # Create new course with basic fields
            course_data = {
                'code': form.course_code.data.upper(),
                'title': form.course_title.data.strip(),
                'credit_hours': form.credit_hours.data,
            }
            
            # Add optional fields if they exist in the form
            if hasattr(form, 'description') and form.description.data:
                course_data['description'] = form.description.data.strip()
                
            if hasattr(form, 'level') and form.level.data:
                course_data['level'] = form.level.data
                
            if hasattr(form, 'semester') and form.semester.data:
                course_data['semester'] = form.semester.data
            
            # Create the course with the collected data
            course = Course(**course_data)
            db.session.add(course)
            
            # Assign course to program
            program = Program.query.get(int(program_id))
            if program:
                program.courses.append(course)
            
            # Log audit
            log = AuditLog(
                admin_id=current_user.id, 
                action='Add Course', 
                target_type='Course', 
                target_id=course.id, 
                details=f'Added course {course.title} ({course.code}) to program {program.name if program else "Unknown"}'
            )
            db.session.add(log)
            
            db.session.commit()
            
            if is_modal:
                return jsonify({
                    'success': True, 
                    'message': 'Course added successfully!',
                    'course': {
                        'id': course.id,
                        'code': course.code,
                        'title': course.title
                    }
                })
                
            flash('Course added successfully!', 'success')
            return redirect(url_for('admin.manage_courses'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding course: {str(e)}")
            if is_modal:
                return jsonify({
                    'success': False, 
                    'message': f'An error occurred while adding the course: {str(e)}'
                }), 500
            flash('An error occurred while adding the course. Please try again.', 'danger')
    
    return render_template('admin/add_course.html', 
                         title='Add Course', 
                         form=form, 
                         programs=programs, 
                         selected_program_id=None)

@bp.route('/enter_result', methods=['GET', 'POST'])
@login_required
def enter_result():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
        
    from app.admin.forms import EnterResultForm
    from app.models import Program, Level, Student, Result, AuditLog, Course
    
    form = EnterResultForm()
    
    # Get all active programs and levels
    programs = Program.query.filter_by(archived=False).all()
    levels = Level.query.filter_by(archived=False).order_by(Level.name).all()
    
    # Set program and level choices
    form.program.choices = [(p.id, p.name) for p in programs]
    form.level.choices = [(l.id, l.name) for l in levels]
    
    # Handle AJAX request for students and courses
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        program_id = request.form.get('program_id')
        level_id = request.form.get('level_id')
        
        if not program_id or not level_id:
            return jsonify({'error': 'Missing program_id or level_id'}), 400
            
        try:
            # Get students for the selected program and level
            students = Student.query.filter_by(
                program_id=program_id,
                level_id=level_id,
                archived=False
            ).all()
            
            # Get courses for the selected program
            program = Program.query.get(program_id)
            courses = program.courses if program else []
            
            return jsonify({
                'students': [{'id': s.id, 'text': f"{s.full_name} ({s.index_number})"} for s in students],
                'courses': [{'id': c.id, 'text': f"{c.code} - {c.title}"} for c in courses]
            })
        except Exception as e:
            current_app.logger.error(f"Error in AJAX request: {str(e)}")
            return jsonify({'error': 'An error occurred while fetching data'}), 500
    
    # Set initial empty choices for program and level
    form.program.choices = [('', '-- Select Program --')] + [(str(p.id), p.name) for p in programs]
    form.level.choices = [('', '-- Select Level --')] + [(str(l.id), l.name) for l in levels]
    form.student.choices = [('', '-- Select Student --')]
    form.course.choices = [('', '-- Select Course --')]
    
    # Handle AJAX requests for dynamic dropdowns
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        program_id = request.form.get('program')
        level_id = request.form.get('level')
        
        if program_id and level_id:
            # Get students for the selected program and level
            students = Student.query.filter_by(
                program_id=program_id,
                level_id=level_id,
                archived=False
            ).all()
            
            # Get courses for the selected program
            program = Program.query.get(program_id)
            courses = program.courses if program else []
            
            return jsonify({
                'students': [{'id': s.id, 'text': f"{s.full_name} ({s.index_number})"} for s in students],
                'courses': [{'id': c.id, 'text': f"{c.code} - {c.title}"} for c in courses]
            })
        return jsonify({'error': 'Missing parameters'}), 400
    
    # Handle form submission
    if request.method == 'POST' and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        current_app.logger.info("Processing form submission")
        current_app.logger.info(f"Form data: {request.form}")
        
        # Always set program and level choices
        form.program.choices = [(p.id, p.name) for p in Program.query.all()]
        form.level.choices = [(l.id, l.name) for l in Level.query.all()]
        
        # Set choices for validation if we have program and level
        if form.program.data and form.level.data:
            try:
                current_app.logger.info(f"Setting choices for program: {form.program.data}, level: {form.level.data}")
                
                # Set student choices
                students = Student.query.filter_by(
                    program_id=form.program.data, 
                    level_id=form.level.data, 
                    archived=False
                ).all()
                form.student.choices = [(str(s.id), f"{s.full_name} ({s.index_number})") for s in students]
                current_app.logger.info(f"Found {len(students)} students")
                
                # Set course choices
                program = Program.query.get(form.program.data)
                if program:
                    form.course.choices = [(str(c.id), f"{c.code} - {c.title}") for c in program.courses]
                    current_app.logger.info(f"Found {len(program.courses)} courses")
                else:
                    form.course.choices = []
                    current_app.logger.warning("No program found for the selected program ID")
                
            except Exception as e:
                current_app.logger.error(f"Error setting choices: {str(e)}", exc_info=True)
                flash('An error occurred while loading form data', 'error')
        
        # Log form validation errors if any
        if not form.validate():
            current_app.logger.warning(f"Form validation failed: {form.errors}")
            flash('Please correct the errors in the form', 'error')
    
    if form.validate_on_submit():
        try:
            current_app.logger.info("Form validation passed")
            student_id = form.student.data
            course_id = form.course.data
            score = float(form.score.data)
            semester = form.semester.data
            academic_year = form.academic_year.data
            remarks = form.remarks.data if hasattr(form, 'remarks') and form.remarks.data else None
            
            current_app.logger.info(f"Processing form submission - Student ID: {student_id}, Course ID: {course_id}, Score: {score}")
            
            # Get the student to ensure it exists
            student = Student.query.get(student_id)
            if not student:
                flash('Selected student not found', 'danger')
                current_app.logger.error(f"Student not found with ID: {student_id}")
                return redirect(url_for('admin.enter_result'))
            
            current_app.logger.info(f"Found student: {student.full_name} ({student.index_number})")
                
            # Get the course
            course = Course.query.get(course_id)
            if not course:
                flash('Course not found', 'danger')
                current_app.logger.error(f"Course not found with ID: {course_id}")
                return redirect(url_for('admin.enter_result'))
                
            current_app.logger.info(f"Found course: {course.code} - {course.title}")
            
            # Check if result already exists for this student and course
            result = Result.query.filter_by(
                student_id=student_id,
                course_id=course_id,
                semester=semester,
                academic_year=academic_year
            ).first()
            
            if result:
                # Update existing result
                result.score = score
                result.remarks = remarks
                result.updated_at = datetime.utcnow()
                db.session.commit()
                
                # Log the update
                log_admin_action(
                    admin_id=current_user.id,
                    action='update',
                    entity_type='result',
                    entity_id=result.id,
                    details=f'Updated result for {student.full_name} in {course.code}: {score}%'
                )
                
                flash('Result updated successfully!', 'success')
                current_app.logger.info(f"Result updated - ID: {result.id}")
                return redirect(url_for('admin.view_results'))
            else:
                # Create new result
                result = Result(
                    student_id=student_id,
                    course_id=course_id,
                    score=score,
                    semester=semester,
                    academic_year=academic_year,
                    remarks=remarks,
                    uploaded_by=current_user.id,
                    grade=calculate_grade(score)  # Calculate grade based on score
                )
                
                db.session.add(result)
                db.session.commit()
                
                # Log the creation
                log_admin_action(
                    admin_id=current_user.id,
                    action='create',
                    entity_type='result',
                    entity_id=result.id,
                    details=f'Created result for {student.full_name} in {course.code}: {score}%'
                )
                
                flash('Result saved successfully!', 'success')
                current_app.logger.info(f"New result created - ID: {result.id}")
                return redirect(url_for('admin.view_results'))
                
        except Exception as e:
            db.session.rollback()
            error_msg = f"An error occurred while saving the result: {str(e)}"
            flash(error_msg, 'danger')
            current_app.logger.error(error_msg)
            current_app.logger.exception(e)
            return redirect(url_for('admin.enter_result'))
    elif request.method == 'POST' and not form.validate():
        # If form validation fails, set the choices again to prevent validation errors
        form.student.choices = [(s.id, f"{s.full_name} ({s.index_number})") 
                              for s in Student.query.filter_by(program_id=form.program.data, 
                                                             level_id=form.level.data, 
                                                             archived=False).all()]
        # Get courses associated with the selected program through the many-to-many relationship
        program = Program.query.get(form.program.data)
        form.course.choices = [(c.id, f"{c.code} - {c.title}") for c in program.courses] if program else []
    
    return render_template('admin/enter_result.html', 
                         title='Enter Result', 
                         form=form, 
                         programs=programs, 
                         levels=levels,
                         selected_program=request.args.get('program', ''),
                         selected_level=request.args.get('level', ''))

@bp.route('/update_result_filters', methods=['POST'])
@login_required
def update_result_filters():
    # Log the start of the request
    current_app.logger.info("\n" + "="*80)
    current_app.logger.info("UPDATE_RESULT_FILTERS ROUTE CALLED")
    current_app.logger.info(f"Request method: {request.method}")
    current_app.logger.info(f"Request headers: {dict(request.headers)}")
    current_app.logger.info(f"Form data: {request.form}")
    current_app.logger.info(f"JSON data: {request.get_json(silent=True) or 'No JSON data'}")
    
    response_data = {'success': False, 'message': '', 'students': [], 'courses': []}
    
    try:
        # Log the incoming request data
        current_app.logger.info(f"Raw form data: {request.form}")
        
        # Get form data with validation
        program_id = request.form.get('program', type=int)
        level_id = request.form.get('level', type=int)
        
        current_app.logger.info(f"Extracted program_id: {program_id} (type: {type(program_id)})")
        current_app.logger.info(f"Extracted level_id: {level_id} (type: {type(level_id)})")
        
        current_app.logger.info(f"Program ID: {program_id}, Level ID: {level_id}")
        
        if not program_id or not level_id:
            error_msg = f"Missing required parameters. Program ID: {program_id}, Level ID: {level_id}"
            current_app.logger.warning(error_msg)
            response_data['message'] = 'Program and level are required'
            response_data['details'] = error_msg
            return jsonify(response_data), 400
        
        # Check if program exists
        program = Program.query.get(program_id)
        if not program:
            error_msg = f"Program with ID {program_id} not found"
            current_app.logger.warning(error_msg)
            response_data['message'] = 'Program not found'
            response_data['details'] = error_msg
            return jsonify(response_data), 404
        
        # Get students for the selected program and level
        try:
            students = Student.query.filter_by(
                program_id=program_id,
                level_id=level_id,
                archived=False
            ).order_by(Student.full_name).all()
            
            response_data['students'] = [
                {'id': s.id, 'text': f"{s.full_name} ({s.index_number})"}
                for s in students
            ]
            current_app.logger.info(f"Found {len(students)} students for program {program_id} and level {level_id}")
            
        except Exception as e:
            error_msg = f"Error fetching students: {str(e)}"
            current_app.logger.error(error_msg, exc_info=True)
            response_data['message'] = 'Error fetching students'
            response_data['details'] = error_msg
            return jsonify(response_data), 500
        
        # Get courses for the selected program
        try:
            response_data['courses'] = [
                {'id': c.id, 'text': f"{c.code} - {c.title}"}
                for c in program.courses
            ]
            current_app.logger.info(f"Found {len(response_data['courses'])} courses for program {program_id}")
            
        except Exception as e:
            error_msg = f"Error fetching courses: {str(e)}"
            current_app.logger.error(error_msg, exc_info=True)
            response_data['message'] = 'Error fetching courses'
            response_data['details'] = error_msg
            return jsonify(response_data), 500
        
        response_data['success'] = True
        response_data['message'] = 'Data retrieved successfully'
        return jsonify(response_data)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        response_data['message'] = 'An unexpected error occurred'
        response_data['details'] = error_msg
        return jsonify(response_data), 500

def calculate_grade(score):
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

    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    results = Result.query.order_by(Result.uploaded_at.desc()).all()
    return render_template('admin/view_results.html', results=results)



@bp.route('/edit_result/<int:result_id>', methods=['GET', 'POST'])
@login_required
def edit_result(result_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    from app.admin.forms import EnterResultForm
    from app.models import Program, Level, Student, Course, Result, AuditLog
    
    # Get the result with related data
    result = Result.query.options(
        db.joinedload(Result.student).joinedload(Student.program),
        db.joinedload(Result.course)
    ).get_or_404(result_id)
    
    if not result.student:
        flash('Student not found for this result', 'danger')
        return redirect(url_for('admin.view_results'))
    
    # Initialize form with data from the result
    form = EnterResultForm()
    
    # Get all active programs and levels for dropdowns
    programs = Program.query.filter_by(archived=False).all()
    levels = Level.query.filter_by(archived=False).order_by(Level.name).all()
    
    # Set up the form choices
    form.program.choices = [(str(p.id), p.name) for p in programs]
    form.level.choices = [(str(l.id), l.name) for l in levels]
    
    # Set up course choices for the student's program
    courses = []
    if result.student and result.student.program:
        courses = result.student.program.courses
    
    # Convert courses to choices format and ensure they're strings
    course_choices = [(str(course.id), f"{course.code} - {course.title}") for course in courses]
    form.course.choices = course_choices
    
    # Set the selected course
    if result.course_id:
        form.course.data = str(result.course_id)
    
    # Handle form submission
    if form.validate_on_submit():
        try:
            # Get the score and calculate grade
            score = float(form.score.data)
            grade = calculate_grade(score)
            
            # Update result
            result.score = score
            result.grade = grade
            result.semester = form.semester.data
            result.academic_year = form.academic_year.data
            result.remarks = form.remarks.data
            result.uploaded_by = current_user.id
            result.uploaded_at = datetime.utcnow()
            
            # Log the update
            log = AuditLog(
                admin_id=current_user.id,
                action='Update Result',
                target_type='Result',
                target_id=result.id,
                details=f'Updated result for {result.student.index_number} - {result.course.code} (Score: {score})'
            )
            db.session.add(log)
            
            db.session.commit()
            flash('Result updated successfully!', 'success')
            return redirect(url_for('admin.view_results'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating result: {str(e)}")
            flash('An error occurred while updating the result', 'danger')
    
    # Prefill form with existing result data (GET request)
    # Set program and level based on student's current program
    program = result.student.program
    level = result.student.level
    
    # Get courses for the program
    courses = program.courses if program else []
    
    # Set form data
    form.program.data = str(program.id) if program else ''
    form.level.data = str(level.id) if level else ''
    form.course.data = str(result.course_id) if result.course_id else ''
    form.score.data = result.score
    form.semester.data = result.semester
    form.academic_year.data = result.academic_year
    form.remarks.data = result.remarks or ''
    
    # Prepare context for template
    context = {
        'form': form,
        'editing': True,
        'result_id': result_id,
        'programs': programs,
        'student_name': result.student.full_name,
        'student_index': result.student.index_number,
        'levels': levels,
        'selected_program': str(program.id) if program else None,
        'selected_level': str(level.id) if level else None,
        'program': program,
        'courses': [(str(c.id), f"{c.code} - {c.title}") for c in courses],
        'selected_course': str(result.course_id) if result.course_id else None,
        'title': 'Edit Result'
    }
    
    return render_template('admin/enter_result.html', **context)

@bp.route('/view_results', methods=['GET', 'POST'])
@login_required
def view_results():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
        
    # Get filter options
    from app.models import Program, Result, Student
    
    # Get all active programs and levels
    programs = Program.query.filter_by(archived=False).all()
    levels = Level.query.filter_by(archived=False).order_by(Level.name).all()
    
    # Get filter values from request
    selected_program = request.args.get('program', '')
    selected_level = request.args.get('level', '')
    
    # Base query for results with joined student and course data
    results_query = db.session.query(Result).join(
        Student, Result.student_id == Student.id
    ).join(
        Program, Student.program_id == Program.id
    ).options(
        db.joinedload(Result.student).joinedload(Student.program),
        db.joinedload(Result.course)
    )
    
    # Apply filters
    if selected_program:
        results_query = results_query.filter(Program.id == selected_program)
    if selected_level:
        results_query = results_query.filter(Student.level_id == selected_level)
    
    # Order and execute the query
    results = results_query.order_by(
        Result.academic_year.desc(), 
        Result.semester.desc(),
        Student.full_name
    ).all()
    
    # Prepare program and level choices for the filter form
    program_choices = [(str(p.id), p.name) for p in programs]
    level_choices = [(str(l.id), l.name) for l in levels]
    
    return render_template('admin/view_results.html',
        programs=programs,
        levels=levels,
        selected_program=selected_program,
        selected_level=selected_level,
        results=results,
        program_choices=program_choices,
        level_choices=level_choices)

@bp.route('/reports')
@login_required
def reports():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    total_students = Student.query.count()
    total_courses = Course.query.count()
    total_results = Result.query.count()
    pass_count = Result.query.filter(Result.grade.in_(['A', 'B', 'C', 'D'])).count()
    fail_count = Result.query.filter(Result.grade=='F').count()
    pass_rate = round((pass_count / total_results) * 100, 2) if total_results else 0
    fail_rate = round((fail_count / total_results) * 100, 2) if total_results else 0
    grades = ['A', 'B', 'C', 'D', 'F']
    grade_dist = {g: Result.query.filter(Result.grade==g).count() for g in grades}
    return render_template('admin/reports.html',
        total_students=total_students,
        total_courses=total_courses,
        total_results=total_results,
        pass_rate=pass_rate,
        fail_rate=fail_rate,
        grade_dist=grade_dist,
        now=datetime.now()
    )

@bp.route('/manage_students', methods=['GET', 'POST'])
@login_required
def manage_students():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    from app.admin.forms import ManageStudentForm
    
    # Debug request data
    print("\n=== NEW REQUEST ===")
    print(f"Request method: {request.method}")
    print(f"Request form data: {request.form}")
    
    # Initialize form with request data
    form = ManageStudentForm()
    
    if request.method == 'POST':
        # Manually populate form data from request
        form = ManageStudentForm(request.form)
        print(f"\nForm data after init: {form.data}")
        print(f"Form errors: {form.errors}")
        
        # Initialize base query with joins
        query = Student.query.options(
            joinedload(Student.level),
            joinedload(Student.program)
        )
        
        # Flag to track if any filters were applied
        filters_applied = False
        
        # Apply index number filter if provided
        if form.index_number.data:
            print(f"Applying index number filter: {form.index_number.data}")
            query = query.filter(Student.index_number.ilike(f"%{form.index_number.data}%"))
            filters_applied = True
            
        # Apply full name filter if provided
        if form.full_name.data:
            print(f"Applying full name filter: {form.full_name.data}")
            query = query.filter(Student.full_name.ilike(f"%{form.full_name.data}%"))
            filters_applied = True
            
        # Apply level filter if provided and not empty
        if form.level.data and form.level.data != 'All':
            level_name = form.level.data
            print(f"\n=== DEBUGGING LEVEL FILTER ===")
            print(f"Filtering by level: {level_name}")
            
            # Debug: Check if level exists
            level = Level.query.filter_by(name=level_name).first()
            print(f"Level found: {level}")
            if level:
                print(f"Level ID: {level.id}, Name: {level.name}")
                
                # Debug: Check students with this level
                students_with_level = Student.query.filter_by(level_id=level.id).all()
                print(f"\nStudents with level {level_name} (ID: {level.id}):")
                for s in students_with_level:
                    print(f"- {s.full_name} (ID: {s.id})")
                print(f"Total: {len(students_with_level)} students")
                
            else:
                print(f"No level found with name: {level_name}")
            
            # Get all level names for debugging
            all_levels = Level.query.all()
            print("\nAll available levels:")
            for lvl in all_levels:
                students_count = Student.query.filter_by(level_id=lvl.id).count()
                print(f"- {lvl.name} (ID: {lvl.id}): {students_count} students")
            
            # Apply level filter
            print(f"\n=== APPLYING LEVEL FILTER ===")
            print(f"Level name from form: {level_name}")
            
            # First try to find the level by name to get its ID
            level = Level.query.filter(Level.name == f"Level {level_name}").first()
            
            if level:
                print(f"Found level in levels table: {level.name} (ID: {level.id})")
                # Filter by level_id
                query = query.filter(Student.level_id == level.id)
                filters_applied = True
                print(f"Applied filter: level_id = {level.id} (Level {level_name})")
                
                # Debug: Check how many students match this level_id
                count = query.count()
                print(f"Found {count} students with level_id = {level.id}")
            else:
                print(f"Warning: No level found with name 'Level {level_name}' in levels table")
                # Fallback to filtering by level string if level not found in levels table
                query = query.filter(Student.level == level_name)
                filters_applied = True
                print(f"Applied fallback filter: level = '{level_name}'")
            
            # Debug: Print the generated SQL
            print("\nGenerated SQL query after level filter:")
            print(str(query))
            print("\n" + "="*50 + "\n")
            
        # Apply program filter if provided and not empty
        if form.program.data and form.program.data != 'All':
            program_name = form.program.data
            print(f"\n=== DEBUGGING PROGRAM FILTER ===")
            print(f"Filtering by program name: {program_name}")
            
            # Debug: Check if program exists
            program = Program.query.filter_by(name=program_name).first()
            print(f"Program found: {program}")
            if program:
                print(f"Program ID: {program.id}, Name: {program.name}")
                
                # Debug: Check students in this program
                students_in_program = Student.query.filter_by(program_id=program.id).all()
                print(f"\nStudents in program {program_name} (ID: {program.id}):")
                for s in students_in_program:
                    level_name = s.level.name if s.level else 'None'
                    print(f"- {s.full_name} (ID: {s.id}), Level: {level_name}")
                print(f"Total: {len(students_in_program)} students")
                
            else:
                print(f"No program found with name: {program_name}")
            
            # Get all program names for debugging
            all_programs = Program.query.all()
            print("\nAll available programs:")
            for p in all_programs:
                students_count = Student.query.filter_by(program_id=p.id).count()
                print(f"- {p.name} (ID: {p.id}): {students_count} students")
            
            # Apply program filter with correct relationship
            query = query.join(Program, Student.program_id == Program.id)\
                .filter(Program.name == program_name)
            filters_applied = True
            print(f"Applied filter: Program name = '{program_name}'")
            
            # Debug: Print the generated SQL
            print("\nGenerated SQL query:")
            print(str(query))
            
            # Direct query to check for students with this program and level
            if form.program.data and form.program.data != 'All' and form.level.data and form.level.data != 'All':
                print("\n=== DIRECT DATABASE QUERY ===")
                direct_query = db.session.query(Student).join(Program).join(Level).filter(
                    Program.name == form.program.data,
                    Level.name == form.level.data
                )
                print(f"Direct query SQL: {str(direct_query)}")
                direct_results = direct_query.all()
                print(f"Direct query results: {len(direct_results)} students found")
                for s in direct_results:
                    print(f"- {s.full_name} (ID: {s.id}), Program: {s.program.name if s.program else 'None'}, Level: {s.level.name if s.level else 'None'}")
            
            print("\n" + "="*50 + "\n")
            

            
        # Apply status filter
        if form.status.data == 'active':
            print("Filtering for active students")
            query = query.filter_by(archived=False)
            filters_applied = True
        elif form.status.data == 'archived':
            print("Filtering for archived students")
            query = query.filter_by(archived=True)
            filters_applied = True
        
        if not filters_applied:
            print("No filters applied, showing active students")
            query = query.filter_by(archived=False)
            
        # Execute the query with ordering
        students = query.order_by(Student.full_name).all()
        print(f"Final query: {query}")
        print(f"Number of students found: {len(students)}")
        
        # Flash message if no results found
        if filters_applied and not students:
            flash('No students found matching the selected criteria.', 'warning')
        
        return render_template('admin/manage_students.html', 
                             title='Manage Students',
                             students=students,
                             form=form)
    
    # For GET requests, show all active students
    print("Handling GET request")
    students = Student.query.filter_by(archived=False)\
        .options(joinedload(Student.level), joinedload(Student.program))\
        .order_by(Student.full_name).all()
    
    return render_template('admin/manage_students.html',
                         title='Manage Students',
                         students=students,
                         form=form)

@bp.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
        
    from app.admin.forms import AddEditStudentForm
    from app.models import User, AuditLog, Program, Level, Student
    from werkzeug.security import generate_password_hash
    import logging
    
    form = AddEditStudentForm()
    
    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    if form.validate_on_submit():
        try:
            logger.debug("Form validated successfully")
            
            # Check if email already exists
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already exists. Please use a different email.', 'danger')
                return render_template('admin/add_edit_student.html', form=form, editing=False)
                
            # Check if index number already exists
            if Student.query.filter_by(index_number=form.index_number.data.upper()).first():
                flash('Index number already exists. Please use a different index number.', 'danger')
                return render_template('admin/add_edit_student.html', form=form, editing=False)
            
            # Generate a random password if not provided
            password = form.password.data or User.generate_random_password()
            
            # Use the provided username or generate from email if not provided
            username = form.username.data.lower() if form.username.data else form.email.data.split('@')[0].lower()
            
            # Create user
            user = User(
                username=username,
                email=form.email.data.lower(),
                user_type='student',
                password_hash=generate_password_hash(password, method='pbkdf2:sha256')
            )
            db.session.add(user)
            db.session.flush()  # Get user.id before commit
            logger.debug(f"Created user with ID: {user.id}")
            
            # Get program and level objects
            program = Program.query.get_or_404(form.program.data)
            level = Level.query.get_or_404(form.level.data)
            
            # Create student with level relationship
            student = Student(
                user_id=user.id,
                index_number=form.index_number.data.upper(),
                full_name=form.full_name.data.title(),
                program_id=program.id,
                level_id=level.id,  # Set the foreign key
                level=level,  # This sets up the relationship object
                archived=False
            )
            db.session.add(student)
            logger.debug("Added student to session")
            
            # Log audit
            log = AuditLog(
                admin_id=current_user.id, 
                action='Add Student', 
                target_type='Student', 
                target_id=student.id, 
                details=f'Added student {student.full_name} ({student.index_number}) to {program.name}'
            )
            db.session.add(log)
            
            # Commit all changes at once
            db.session.commit()
            logger.debug("Committed all changes to database")
            
            # Send welcome email with credentials
            try:
                from flask import url_for, render_template_string
                from flask_mail import Message
                from app import mail  # Import mail instance
                from datetime import datetime
                import smtplib
                import ssl
                
                # Log email configuration for debugging
                current_app.logger.info('Email Configuration:')
                current_app.logger.info(f'Server: {current_app.config["MAIL_SERVER"]}:{current_app.config["MAIL_PORT"]}')
                current_app.logger.info(f'Username: {current_app.config["MAIL_USERNAME"]}')
                current_app.logger.info(f'Using SSL: {current_app.config["MAIL_USE_SSL"]}')
                current_app.logger.info(f'Using TLS: {current_app.config["MAIL_USE_TLS"]}')
                
                login_url = url_for('auth.login', _external=True, _scheme='https')
                
                # Create email message with HTML and plain text versions
                msg = Message(
                    'Welcome to Student Portal - Your Account Details',
                    recipients=[user.email],
                    sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                    reply_to=current_app.config.get('MAIL_DEFAULT_SENDER')
                )
                
                # First, ensure we have the render_template function
                from flask import render_template
                
                # Define all template variables
                template_vars = {
                    'student_name': student.full_name,
                    'username': username,
                    'password': password,
                    'login_url': login_url,
                    'current_year': datetime.now().year
                }
                
                # Try to render the template file first
                try:
                    msg.html = render_template('emails/welcome_student.html', **template_vars)
                    current_app.logger.info('Successfully rendered email template from file')
                except Exception as template_error:
                    current_app.logger.error(f'Error rendering email template: {str(template_error)}')
                    # Fallback to a simple HTML template
                    msg.html = """
                    <html>
                        <body>
                            <h2>Welcome {student_name}!</h2>
                            <p>Your student account has been created successfully.</p>
                            <p><strong>Username:</strong> {username}</p>
                            <p><strong>Password:</strong> {password}</p>
                            <p>Please <a href='{login_url}'>click here to log in</a> and change your password.</p>
                            <p>Login URL: {login_url}</p>
                        </body>
                    </html>
                    """.format(
                        student_name=student.full_name,
                        username=username,
                        password=password,
                        login_url=login_url
                    )
                
                # Plain text version
                msg.body = f"""Welcome to Student Portal

Hi {student.full_name},

Your student account has been created successfully.

Login Details:
Username: {username}
Password: {password}

Please log in at: {login_url}

For security reasons, please change your password after your first login.

Best regards,
The Administration Team"""
                
                # Set email priority to high
                msg.extra_headers = {'X-Priority': '1 (Highest)'}
                msg.extra_headers['X-MSMail-Priority'] = 'High'
                msg.extra_headers['Importance'] = 'High'
                
                # Send the email using Flask-Mail with proper configuration
                try:
                    current_app.logger.info(f'Preparing to send welcome email to {user.email}')
                    
                    # Log email configuration for debugging
                    current_app.logger.info('Email Configuration:')
                    current_app.logger.info(f'Server: {current_app.config["MAIL_SERVER"]}:{current_app.config["MAIL_PORT"]}')
                    current_app.logger.info(f'Username: {current_app.config["MAIL_USERNAME"]}')
                    current_app.logger.info(f'Use SSL: {current_app.config["MAIL_USE_SSL"]}')
                    current_app.logger.info(f'Use TLS: {current_app.config["MAIL_USE_TLS"]}')
                    
                    # Ensure we have the mail instance
                    from app import mail
                    
                    # Send the email using Flask-Mail
                    with mail.connect() as conn:
                        conn.send(msg)
                    
                    current_app.logger.info(f'Successfully sent welcome email to {user.email}')
                    flash(f'Welcome email sent to {user.email}.', 'info')
                    
                except Exception as send_error:
                    error_msg = f'Error sending email to {user.email}: {str(send_error)}'
                    current_app.logger.error(error_msg, exc_info=True)
                    # Fallback to direct SMTP if Flask-Mail fails
                    try:
                        current_app.logger.info('Attempting fallback SMTP send...')
                        mail_server = current_app.config['MAIL_SERVER']
                        mail_port = current_app.config['MAIL_PORT']
                        mail_username = current_app.config['MAIL_USERNAME']
                        mail_password = current_app.config['MAIL_PASSWORD']
                        
                        context = ssl.create_default_context()
                        
                        if current_app.config['MAIL_USE_SSL']:
                            with smtplib.SMTP_SSL(mail_server, mail_port, context=context, timeout=20) as server:
                                server.login(mail_username, mail_password)
                                server.send_message(
                                    msg,
                                    from_addr=current_app.config['MAIL_DEFAULT_SENDER'],
                                    to_addrs=msg.recipients
                                )
                        else:
                            with smtplib.SMTP(mail_server, mail_port, timeout=20) as server:
                                if current_app.config['MAIL_USE_TLS']:
                                    server.starttls(context=context)
                                server.login(mail_username, mail_password)
                                server.send_message(
                                    msg,
                                    from_addr=current_app.config['MAIL_DEFAULT_SENDER'],
                                    to_addrs=msg.recipients
                                )
                        
                        current_app.logger.info(f'Successfully sent welcome email using fallback SMTP to {user.email}')
                        flash(f'Welcome email sent to {user.email}.', 'info')
                        
                    except Exception as fallback_error:
                        error_msg = f'Fallback SMTP send failed: {str(fallback_error)}'
                        current_app.logger.error(error_msg, exc_info=True)
                        flash('Welcome email could not be sent. The student was added successfully.', 'warning')
                
            except Exception as e:
                logger.error(f"Error sending welcome email: {str(e)}", exc_info=True)
                flash('Student added, but there was an error sending the welcome email.', 'warning')
            
            flash(f'Student {student.full_name} added successfully!', 'success')
            return redirect(url_for('admin.manage_students'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error adding student: {str(e)}', exc_info=True)
            flash(f'An error occurred while adding the student: {str(e)}', 'danger')
    
    # If GET request or form not validated, show the form
    from flask import render_template  # Ensure render_template is in local scope
    try:
        return render_template('admin/add_edit_student.html', form=form, editing=False)
    except Exception as e:
        current_app.logger.error(f"Error rendering template: {str(e)}")
        flash('An error occurred while loading the form. Please try again.', 'danger')
        return redirect(url_for('admin.manage_students'))

@bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    student = Student.query.get_or_404(student_id)
    form = EditStudentForm()
    
    if form.validate_on_submit():
        try:
            student.full_name = form.full_name.data
            
            # Find the program by name and update the program_id
            program = Program.query.filter_by(name=form.program.data).first()
            if program:
                student.program_id = program.id
            else:
                flash('Program not found!', 'error')
                return redirect(url_for('admin.edit_student', student_id=student_id))
            
            # Find the level by name and update the level_id
            level = Level.query.filter_by(name=form.level.data).first()
            if level:
                student.level_id = level.id
            else:
                flash('Level not found!', 'error')
                return redirect(url_for('admin.edit_student', student_id=student_id))
            
            db.session.commit()
            
            # Log audit
            log = AuditLog(
                admin_id=current_user.id,
                action='Edit Student',
                target_type='Student',
                target_id=student.id,
                details=f'Edited student {student.full_name} ({student.index_number})'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Student updated successfully!', 'success')
            return redirect(url_for('admin.manage_students'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'error')
            return redirect(url_for('admin.edit_student', student_id=student_id))
    
    # If GET request or validation failed, pre-populate the form
    form.full_name.data = student.full_name
    if student.program_id:
        program = Program.query.get(student.program_id)
        if program:
            form.program.data = program.name
    if student.level_id:
        level = Level.query.get(student.level_id)
        if level:
            form.level.data = level.name
    
    return render_template('admin/edit_student.html', form=form, student=student, no_program=not student.program_id)
@bp.route('/archive_student/<int:student_id>')
@login_required
def archive_student(student_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    student = Student.query.get_or_404(student_id)
    student.archived = True
    db.session.commit()
    # Log audit
    from app.models import AuditLog
    log = AuditLog(admin_id=current_user.id, action='Archive Student', target_type='Student', target_id=student.id, details=f'Archived student {student.full_name} ({student.index_number})')
    db.session.add(log)
    db.session.commit()
    flash('Student archived successfully!', 'success')
    return redirect(url_for('admin.manage_students'))

@bp.route('/download_student_template')
@login_required
def download_student_template():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
        
    # Create a CSV template in memory
    si = io.StringIO()
    cw = csv.writer(si)
    # Add header row
    cw.writerow(['Index Number', 'Full Name', 'Program Name', 'Level (e.g., 100, 200, 300, 400)'])
    # Add an example row
    cw.writerow(['BIT0001234', 'John Doe', 'Bsc Information Technology', '100'])
    
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name='student_import_template.csv',
        conditional=True
    )

@bp.route('/export_students')
@login_required
def export_students():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
        
    # Query students with joined program and level data
    students = Student.query.filter_by(archived=False)\
        .join(Program, Student.program_id == Program.id)\
        .join(Level, Student.level_id == Level.id)\
        .add_columns(Program.name.label('program_name'), Level.name.label('level_name'))\
        .all()
        
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Index Number', 'Full Name', 'Program', 'Level'])
    
    for s in students:
        # Extract the numeric part from the level name (e.g., 'Level 100' -> '100')
        level_number = s.level_name.split()[-1] if s.level_name else 'N/A'
        cw.writerow([s.Student.index_number, s.Student.full_name, s.program_name, level_number])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='students.csv')

@bp.route('/import_students', methods=['POST'])
@login_required
def import_students():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a valid CSV file.', 'danger')
        return redirect(url_for('admin.manage_students'))
    stream = io.StringIO(file.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    from app.models import User
    from werkzeug.security import generate_password_hash
    for row in reader:
        # Basic validation
        index_number = row.get('Index Number')
        full_name = row.get('Full Name')
        program = row.get('Program')
        level = row.get('Level')
        if not (index_number and full_name and program and level):
            continue
        # Create user and student if not exists
        user = User.query.filter_by(username=index_number).first()
        if not user:
            user = User(
                username=index_number,
                email=f"{index_number}@student.portal",
                user_type='student',
                password_hash=generate_password_hash('changeme123', method='pbkdf2:sha256')
            )
            db.session.add(user)
            db.session.flush()
            student = Student(
                user_id=user.id,
                index_number=index_number,
                full_name=full_name,
                program=program,
                level=level,
                archived=False
            )
            db.session.add(student)
    db.session.commit()
    flash('CSV import complete. Default password is "changeme123".', 'success')
    return redirect(url_for('admin.manage_students'))

@bp.route('/bulk_students_action', methods=['POST'])
@login_required
def bulk_students_action():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    ids = request.form.getlist('student_ids')
    action = request.form.get('action')
    if not ids or not action:
        flash('No students selected or no action specified.', 'warning')
        return redirect(url_for('admin.manage_students'))
    students = Student.query.filter(Student.id.in_(ids)).all()
    if action == 'archive':
        for s in students:
            s.archived = True
        db.session.commit()
        flash(f'{len(students)} students archived.', 'success')
    elif action == 'delete':
        for s in students:
            db.session.delete(s)
        db.session.commit()
        flash(f'{len(students)} students deleted.', 'success')
    else:
        flash('Invalid action.', 'danger')
    return redirect(url_for('admin.manage_students'))

@bp.route('/archived_students')
@login_required
def archived_students():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    students = Student.query.filter_by(archived=True).all()
    return render_template('admin/archived_students.html', students=students)

@bp.route('/reset_student_password/<int:student_id>', methods=['GET', 'POST'])
@login_required
def reset_student_password(student_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    from app.admin.forms import ResetStudentPasswordForm
    from app.models import User
    from werkzeug.security import generate_password_hash
    student = Student.query.get_or_404(student_id)
    user = User.query.get(student.user_id)
    form = ResetStudentPasswordForm()
    if form.validate_on_submit():
        user.password_hash = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        db.session.commit()
        # Log audit
        from app.models import AuditLog
        log = AuditLog(admin_id=current_user.id, action='Reset Password', target_type='Student', target_id=student.id, details=f'Reset password for {student.full_name} ({student.index_number})')
        db.session.add(log)
        db.session.commit()
        flash('Password reset successfully!', 'success')
        return redirect(url_for('admin.manage_students'))
    return render_template('admin/reset_student_password.html', form=form, student=student)

@bp.route('/view_login_history/<int:student_id>')
@login_required
def view_login_history(student_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    student = Student.query.get_or_404(student_id)
    from app.models import LoginHistory
    history = LoginHistory.query.filter_by(user_id=student.user_id).order_by(LoginHistory.timestamp.desc()).all()
    return render_template('admin/login_history.html', student=student, history=history)

@bp.route('/restore_student/<int:student_id>', methods=['POST'])
@login_required
def restore_student(student_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    student = Student.query.get_or_404(student_id)
    student.archived = False
    db.session.commit()
    flash('Student restored successfully.', 'success')
    return redirect(url_for('admin.archived_students'))

@bp.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    # Log audit
    from app.models import AuditLog
    log = AuditLog(admin_id=current_user.id, action='Delete Student', target_type='Student', target_id=student.id, details=f'Deleted student {student.full_name} ({student.index_number})')
    db.session.add(log)
    db.session.commit()
    flash('Student permanently deleted!', 'success')
    return redirect(url_for('admin.archived_students'))


def get_backup_dir():
    """Get or create backup directory"""
    backup_dir = os.path.join(current_app.root_path, '..', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


@bp.route('/backup', methods=['GET', 'POST'])
@login_required
def backup_database():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            # Use the backup utility to create a backup
            from app.utils.backup_utils import create_backup
            
            # Create the backup
            result = create_backup()
            
            if not result.get('success'):
                raise Exception(result.get('error', 'Unknown error during backup'))
            
            # Log the backup
            log = AuditLog(
                admin_id=current_user.id,
                action='Backup',
                target_type='System',
                details=f'Created backup: {result["filename"]}'
            )
            db.session.add(log)
            db.session.commit()
            
            flash(f'Backup created successfully: {result["filename"]}', 'success')
            
        except Exception as e:
            current_app.logger.error(f'Backup failed: {str(e)}', exc_info=True)
            flash(f'Backup failed: {str(e)}', 'danger')
    
    # List all backup files
    backup_dir = get_backup_dir()
    backups = []
    
    try:
        for file in os.listdir(backup_dir):
            if file.endswith('.zip'):
                file_path = os.path.join(backup_dir, file)
                backups.append({
                    'name': file,
                    'size': os.path.getsize(file_path),
                    'created': datetime.fromtimestamp(os.path.getctime(file_path))
                })
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
    except Exception as e:
        current_app.logger.error(f'Error listing backups: {str(e)}')
        flash(f'Error listing backups: {str(e)}', 'danger')
    
    return render_template('admin/backup.html', backups=backups)


@bp.route('/backup/download/<filename>')
@login_required
def download_backup(filename):
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    backup_dir = get_backup_dir()
    return send_from_directory(
        backup_dir,
        filename,
        as_attachment=True,
        download_name=filename
    )


@bp.route('/backup/restore', methods=['POST'])
@login_required
def restore_backup():
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    backup_file = request.form.get('backup_file')
    if not backup_file:
        return jsonify({'success': False, 'message': 'No backup file selected'}), 400
    
    backup_dir = get_backup_dir()
    backup_path = os.path.join(backup_dir, backup_file)
    
    if not os.path.exists(backup_path):
        return jsonify({'success': False, 'message': 'Backup file not found'}), 404
    
    try:
        # Extract backup to temp directory
        temp_dir = tempfile.mkdtemp()
        
        with zipfile.ZipFile(backup_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find the SQL file in the extracted files
        sql_files = [f for f in os.listdir(temp_dir) if f.endswith('.sql')]
        if not sql_files:
            shutil.rmtree(temp_dir)
            return jsonify({'success': False, 'message': 'No SQL file found in backup'}), 400
        
        sql_file = os.path.join(temp_dir, sql_files[0])
        
        # Get database config
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        db_name = db_uri.split('/')[-1].split('?')[0]
        db_user = db_uri.split('//')[1].split(':')[0]
        db_pass = db_uri.split(':')[2].split('@')[0]
        
        # Drop and recreate database
        drop_cmd = [
            'mysql',
            f'--user={db_user}',
            f'--password={db_pass}',
            '--host=localhost',
            '-e', f'DROP DATABASE IF EXISTS {db_name}; CREATE DATABASE {db_name};'
        ]
        
        subprocess.run(drop_cmd, check=True)
        
        # Restore database
        restore_cmd = [
            'mysql',
            f'--user={db_user}',
            f'--password={db_pass}',
            '--host=localhost',
            db_name
        ]
        
        with open(sql_file, 'r') as f:
            subprocess.run(restore_cmd, stdin=f, check=True)
        
        # Clean up
        shutil.rmtree(temp_dir)
        
        # Log the restore
        log = AuditLog(
            admin_id=current_user.id,
            action='Restore',
            target_type='System',
            details=f'Restored from backup: {backup_file}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Database restored successfully. Please log in again.'
        })
        
    except Exception as e:
        current_app.logger.error(f'Restore failed: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Restore failed: {str(e)}'
        }), 500


@bp.route('/backup/delete/<filename>', methods=['POST'])
@login_required
def delete_backup(filename):
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    backup_dir = get_backup_dir()
    backup_path = os.path.join(backup_dir, filename)
    
    try:
        if os.path.exists(backup_path):
            os.remove(backup_path)
            
            # Log the deletion
            log = AuditLog(
                admin_id=current_user.id,
                action='Delete Backup',
                target_type='System',
                details=f'Deleted backup: {filename}'
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Backup deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Backup not found'}), 404
    except Exception as e:
        current_app.logger.error(f'Error deleting backup: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500