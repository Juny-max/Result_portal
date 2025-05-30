from flask import render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Student, Result, Course, Program, AuditLog, Level, Notification

# Import the blueprint from the package's __init__.py
from . import bp

@bp.route('/notifications')
@login_required
def notifications():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    student = current_user.student
    if not student:
        flash('Student profile not found', 'danger')
        return redirect(url_for('main.index'))
    
    # Get all notifications for display
    notifications = Notification.query.filter_by(
        user_id=student.user_id
    ).order_by(Notification.created_at.desc()).all()
    
    # Get unread count for the badge
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return render_template('student/notifications.html', 
                         notifications=notifications,
                         unread_count=unread_count)

@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first()
    
    if notification and not notification.is_read:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Notification not found or already read'}), 404

@bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    updated = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Marked {updated} notifications as read'
    })

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
        
    student = current_user.student
    if not student:
        flash('Student profile not found', 'danger')
        return redirect(url_for('main.index'))
    
    # Get all results for the student, ordered by academic year and semester
    results = Result.query.filter_by(student_id=student.id).order_by(
        Result.academic_year.desc(), Result.semester.desc()
    ).all()
    
    # Calculate overall CGPA (all results)
    overall_cgpa = calculate_gpa(results)
    
    # Calculate current semester GPA (most recent semester)
    current_semester_results = []
    current_semester_gpa = "N/A"
    
    if results:
        # Get the most recent academic year and semester
        current_year = results[0].academic_year
        current_semester = results[0].semester
        current_semester_results = [
            r for r in results 
            if r.academic_year == current_year and r.semester == current_semester
        ]
        current_semester_gpa = calculate_gpa(current_semester_results)
    
    # Calculate level CGPA (all results from current level)
    level_cgpa = "N/A"
    if student.level_id:
        level_results = [
            r for r in results 
            if hasattr(r, 'student_level_id') and r.student_level_id == student.level_id
        ]
        level_cgpa = calculate_gpa(level_results)
    
    # Get unread notifications count for the badge
    unread_notifications_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    
    return render_template('student/dashboard.html',
                          title='Dashboard',
                          semester_gpa=current_semester_gpa,  # Fixed variable name to match template
                          level_cgpa=level_cgpa,
                          overall_cgpa=overall_cgpa,
                          results=results,
                          unread_notifications_count=unread_notifications_count)

def calculate_gpa(results):
    if not results:
        return "N/A"
    
    # Define grade to grade point conversion based on your grading system
    def get_grade_point(grade=None, score=None):
        if grade:
            grade_to_point = {
                'A': 4.00,
                'A-': 3.85,
                'B+': 3.50,
                'B': 3.00,
                'C+': 2.50,
                'C': 2.00,
                'D': 1.50,
                'E': 1.00,
                'F': 0.00
            }
            return grade_to_point.get(grade, 0)
        elif score is not None:
            if score >= 80:
                return 4.00  # A
            elif score >= 70:
                return 3.85  # A-
            elif score >= 65:
                return 3.50  # B+
            elif score >= 60:
                return 3.00  # B
            elif score >= 55:
                return 2.50  # C+
            elif score >= 50:
                return 2.00  # C
            elif score >= 45:
                return 1.50  # D
            elif score >= 40:
                return 1.00  # E
            else:
                return 0.00  # F
        return 0.00
    
    total_credit_hours = 0
    total_quality_points = 0
    
    for r in results:
        # Get credit hours (make sure this attribute exists)
        credit_hours = getattr(r.course, 'credit_hours', 0)
        if credit_hours == 0:
            continue
            
        # Determine grade point based on either grade or score
        if hasattr(r, 'grade') and r.grade:
            grade_point = get_grade_point(grade=r.grade)
        elif hasattr(r, 'score'):
            grade_point = get_grade_point(score=r.score)
        else:
            continue  # Skip if neither grade nor score is available
        
        total_credit_hours += credit_hours
        total_quality_points += grade_point * credit_hours
    
    if total_credit_hours == 0:
        return "N/A"
    
    return round(total_quality_points / total_credit_hours, 2)

@bp.route('/results')
@login_required
def view_results():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    student = current_user.student
    if not student:
        flash('Student profile not found', 'danger')
        return redirect(url_for('main.index'))
    
    # Get all results for the student, ordered by level, then academic year, then semester
    results = Result.query.filter_by(student_id=student.id).join(
        Level, Result.student_level_id == Level.id
    ).order_by(
        Level.name, Result.academic_year, Result.semester
    ).all()
    
    # Group results by level
    results_by_level = {}
    levels = set()
    
    for result in results:
        level_id = result.student_level_id or student.level_id  # Fallback to current level if not set
        level = Level.query.get(level_id)
        
        if not level:
            continue
            
        if level_id not in results_by_level:
            results_by_level[level_id] = {
                'level': level,
                'results': [],
                'gpa': 0.0
            }
            levels.add(level)
            
        results_by_level[level_id]['results'].append(result)
    
    # Calculate GPA for each level
    level_gpas = {}
    for level_id, data in results_by_level.items():
        level_results = data['results']
        gpa = calculate_gpa(level_results)
        results_by_level[level_id]['gpa'] = gpa
        level_gpas[level_id] = gpa
    
    # Calculate overall CGPA
    overall_cgpa = calculate_gpa(results)
    
    # Organize results by level, then year, then semester
    organized = {}
    for level_id, data in results_by_level.items():
        level_name = data['level'].name
        organized[level_name] = {}
        
        for result in data['results']:
            year = str(result.academic_year)
            semester = result.semester
            
            if year not in organized[level_name]:
                organized[level_name][year] = {}
                
            if semester not in organized[level_name][year]:
                organized[level_name][year][semester] = []
                
            organized[level_name][year][semester].append(result)
    
    # Get distinct levels for the template
    levels = sorted(levels, key=lambda x: x.name)
    
    return render_template(
        'student/results.html',
        title='My Results',
        results=results,
        results_by_level=results_by_level,
        organized=organized,
        levels=levels,
        level_gpas=level_gpas,
        overall_cgpa=overall_cgpa,
        Level=Level  # Pass the Level model to the template
    )