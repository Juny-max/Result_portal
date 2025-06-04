from flask import render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm, ChangePasswordForm
from app.models import User, Student, AuditLog

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        # Strip whitespace from input
        user_input = form.username.data.strip()
        password_input = form.password.data
        
        user = User.query.filter((User.username == user_input) | (User.email == user_input)).first()
        
        if user is None:
            flash('No user found with that username or email.', 'danger')
            return redirect(url_for('auth.login'))
            
        if not user.check_password(password_input):
            flash('Password is incorrect for this account.', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user)
        
        # Log login event
        from app.models import LoginHistory
        login_record = LoginHistory(user_id=user.id, ip_address=request.remote_addr)
        db.session.add(login_record)
        
        # Check if it's the user's first login
        if user.first_login:
            db.session.commit()  # Commit login record before redirecting
            return redirect(url_for('auth.change_password'))
            
        db.session.commit()
        
        next_page = request.args.get('next')
        
        if not next_page or urlparse(next_page).netloc != '':
            # Redirect to appropriate dashboard based on user type
            next_page = url_for('admin.dashboard' if user.is_admin() else 'student.dashboard')
        
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check for duplicate username or email
        existing_user = User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first()
        if existing_user:
            flash('Username or email already exists. Please choose another.', 'danger')
            return render_template('auth/register.html', title='Register', form=form)

        # Check for duplicate index number
        existing_student = Student.query.filter_by(index_number=form.index_number.data).first()
        if existing_student:
            flash('Index number already exists. Please check your details or contact admin.', 'danger')
            return render_template('auth/register.html', title='Register', form=form)

        user = User(
            username=form.username.data,
            email=form.email.data,
            user_type='student'
        )
        user.set_password(form.password.data)
        print('DEBUG REGISTRATION: Password entered:', form.password.data)
        print('DEBUG REGISTRATION: Generated hash:', user.password_hash)
        db.session.add(user)
        db.session.flush()  # Assigns user.id for the foreign key

        student = Student(
            user=user,
            index_number=form.index_number.data,
            full_name=form.full_name.data,
            program=form.program.data,
            level=form.level.data
        )
        db.session.add(student)
        db.session.commit()
        flash('Congratulations, you are now a registered student!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form)

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if not current_user.first_login:
        return redirect(url_for('admin.dashboard' if current_user.is_admin() else 'student.dashboard'))
    
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        # Verify current password
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # Update password using the set_password method
        current_user.set_password(form.new_password.data)
        current_user.first_login = False  # Mark as not first login anymore
        
        # Log the password change
        log = AuditLog(
            admin_id=current_user.id,
            action='Password Changed',
            target_type='User',
            target_id=current_user.id,
            details='User changed their password on first login'
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Your password has been updated successfully!', 'success')
        return redirect(url_for('admin.dashboard' if current_user.is_admin() else 'student.dashboard'))
    
    return render_template('auth/change_password.html', title='Change Password', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))