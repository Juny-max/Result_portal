import os
import sys
from werkzeug.security import generate_password_hash

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

def create_admin_user(username, email, password):
    """
    Create an admin user with the given credentials.
    """
    app = create_app()
    
    with app.app_context():
        # Check if admin already exists
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            print(f"Error: An admin with username '{username}' or email '{email}' already exists.")
            return False
        
        # Create admin user
        admin = User(
            username=username,
            email=email,
            user_type='admin',
            first_login=True
        )
        admin.set_password(password)
        
        try:
            db.session.add(admin)
            db.session.commit()
            print(f"Admin user '{username}' created successfully!")
            print(f"Email: {email}")
            print("Please log in and change your password immediately.")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error creating admin user: {str(e)}")
            return False

if __name__ == '__main__':
    print("=== Create Admin User ===")
    
    # Get user input
    username = input("Enter admin username: ").strip()
    email = input("Enter admin email: ").strip()
    
    while True:
        password = input("Enter admin password: ").strip()
        confirm = input("Confirm admin password: ").strip()
        
        if password != confirm:
            print("Error: Passwords do not match. Please try again.")
        elif len(password) < 8:
            print("Error: Password must be at least 8 characters long.")
        else:
            break
    
    create_admin_user(username, email, password)
