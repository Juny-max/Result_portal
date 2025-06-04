# Student Result Portal

A comprehensive web application for managing and viewing student results, built with Python, Flask, and MySQL. This system provides features for administrators to manage students, programs, courses, and results, while allowing students to view their academic progress.

## 🚀 Quick Start

### For First-Time Users

1. **Prerequisites**
   - Python 3.8 or higher
   - MySQL Server 8.0+
   - Git (optional)
   - pip (Python package manager)

2. **Clone the Repository**
   ```bash
   git clone <your-repo-url>
   cd Result_portal
   ```

3. **Set Up Virtual Environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate it
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   # source venv/bin/activate
   ```

4. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   If you encounter any missing packages, install them manually:
   ```bash
   pip install flask flask-login flask-sqlalchemy flask-migrate flask-wtf flask-mail \
   pandas openpyxl xlsxwriter python-dotenv email-validator
   ```

5. **Environment Configuration**
   - Copy `.env.example` to `.env` and update with your settings:
     ```bash
     # Database Configuration
     DATABASE_URL=mysql+pymysql://username:password@localhost/result_portal
     SECRET_KEY=your-secret-key-here
     
     # Email Configuration
     MAIL_SERVER=smtp.gmail.com
     MAIL_PORT=465
     MAIL_USE_SSL=true
     MAIL_USE_TLS=false
     MAIL_USERNAME=your-email@gmail.com
     MAIL_PASSWORD=your-app-password
     MAIL_DEFAULT_SENDER=your-email@gmail.com
     MAIL_DEBUG=false
     ```

6. **Database Setup**
   - Create a MySQL database named `result_portal` (or your preferred name)
   - Run database migrations:
     ```bash
     flask db upgrade
     ```

7. **Run the Application**

   #### Recommended Method: Using Virtual Environment (Activate First)
   ```bash
   # Activate the virtual environment
   .\venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux
   
   # Set Flask app environment variable
   set FLASK_APP=run.py  # Windows
   # export FLASK_APP=run.py  # macOS/Linux
   
   # Run in development mode
   flask run
   ```
   
   #### Alternative Method: Direct Python Execution (Not Recommended for Development)
   ```bash
   # This method runs Python directly from the virtual environment
   # but doesn't activate the environment in your shell
   .\venv\Scripts\python.exe run.py
   ```
   > **Note**: The recommended method (activating the virtual environment first) is preferred because:
   > - It ensures all subsequent commands use the virtual environment
   > - It makes it clear which environment you're working in
   > - It's required for some Flask commands and extensions

8. **Create Admin Account**
   ```bash
   # With virtual environment activated, simply run:
   python create_admin.py
   ```
   - Follow the prompts to create an admin account
   - Make sure to use a strong password (at least 8 characters)

9. **Access the Application**
   - Open your browser and go to: http://localhost:5000
   - Log in with the admin credentials you just created
   - You'll be prompted to change your password on first login

## 🔧 Features

### Admin Features
- **Student Management**
  - Add, edit, archive, and restore student records
  - Bulk import students via CSV
  - Send welcome emails with login credentials
  - Reset student passwords

- **Academic Management**
  - Create and manage academic programs
  - Add and manage courses
  - Assign courses to programs
  - Enter and manage student results

- **Results & Reporting**
  - Upload results via Excel/CSV
  - Generate transcripts and reports
  - Export data to multiple formats (Excel, CSV, PDF)

### Student Features
- View personal information
- Check academic results
- Track academic progress
- Download official documents

### Security Features
- Secure user authentication
- Role-based access control
- Password hashing
- Audit logging
- Secure email notifications

## 📧 Email Notifications

The system sends automated emails for:
- New student account creation
- Password resets
- Important announcements
- Result publication

### Email Configuration
Update the following in your `.env` file:
```bash
# Email Settings
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_USE_SSL=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

## 🛠 Troubleshooting

### Common Issues

1. **Email Sending Issues**
   - Ensure you're using an App Password if 2FA is enabled on your email
   - Check SMTP settings (port 465 for SSL, 587 for TLS)
   - Verify email credentials in `.env`
   - Check spam/junk folder for test emails

2. **Database Connection Issues**
   - Verify MySQL service is running
   - Check database credentials in `.env`
   - Ensure the database exists and is accessible
   - Make sure the database user has proper permissions

3. **Module Not Found Errors**
   - Ensure virtual environment is activated
   - Run `pip install -r requirements.txt`
   - Check for any error messages during package installation

4. **Port Already in Use**
   ```bash
   # Find and terminate the process using the port (Windows):
   netstat -ano | findstr :5000
   taskkill /PID <PID> /F
   
   # Or run on a different port:
   flask run --port 5001
   ```

## 📂 Project Structure

```
Result_portal/
├── app/
│   ├── __init__.py         # Application factory and extensions
│   ├── admin/              # Admin routes and functionality
│   ├── auth/               # Authentication routes
│   ├── static/             # Static files (CSS, JS, images)
│   ├── templates/          # HTML templates
│   │   └── emails/         # Email templates
│   ├── models.py           # Database models
│   └── utils.py            # Utility functions
├── migrations/             # Database migrations
├── logs/                   # Application logs
├── .env                    # Environment variables
├── config.py               # Application configuration
├── requirements.txt        # Python dependencies
└── run.py                  # Application entry point
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with Flask
- Uses Bootstrap for frontend
- Powered by MySQL database
- Email notifications with Flask-Mail
- Modern UI/UX with responsive design

## 📚 Documentation

### Database Schema

#### Tables
- **users**: User accounts (admins and students)
- **students**: Student information
- **programs**: Academic programs
- **courses**: Course catalog
- **results**: Student results and grades
- **levels**: Academic levels (100, 200, etc.)
- **audit_logs**: System audit trail
- **notifications**: User notifications

#### Key Relationships
- Students belong to Programs
- Results are linked to Students and Courses
- Programs have many Courses through a many-to-many relationship

## 🛠 Development

### Setting Up Development Environment

1. **Install Development Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Run Tests**
   ```bash
   python -m pytest
   ```

3. **Code Style**
   ```bash
   # Run flake8
   flake8 .
   
   # Format code with black
   black .
   ```

4. **Debug Mode**
   ```bash
   set FLASK_DEBUG=1
   flask run
   ```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

### Running Tests
```bash
python -m pytest tests/
```

### Database Migrations
When making changes to models:
```bash
# Generate new migration
flask db migrate -m "description of changes"

# Apply migrations
flask db upgrade
```

### Linting
```bash
# Install linters
pip install flake8 black

# Run linter
flake8 app/


# Auto-format code
black app/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📧 Contact

For support or questions, please contact [Your Email].

---

### 3. Install Dependencies
Install all required Python packages:
```bash
pip install -r requirements.txt
```
If you get errors about missing packages, install them manually:
```bash
pip install flask flask_sqlalchemy flask_migrate flask_login flask_bootstrap flask_wtf python-dotenv pymysql cryptography
```

---

### 4. Set Up Environment Variables
Environment variables store your secrets and DB info.
- Copy `.env.example` to `.env` and edit with your credentials:
  ```bash
  cp .env.example .env
  ```
- Or create a `.env` file with:
  ```
  SECRET_KEY=your-secret-key-here
  DATABASE_URL=mysql+pymysql://root:yourpassword@localhost/student_result_portal
  ```
  Replace with your actual MySQL username, password, and database name.

---

### 5. Set the Flask App Environment Variable
This tells Flask how to find your app.
- **On Windows CMD:**
  ```cmd
  set FLASK_APP=app:create_app
  ```
- **On PowerShell:**
  ```powershell
  $env:FLASK_APP = "app:create_app"
  ```
- **On macOS/Linux:**
  ```bash
  export FLASK_APP=app:create_app
  ```

---

### 6. Initialize the Database (First Time Only)
Set up the database tables:
```bash
python -m flask db init
python -m flask db migrate
python -m flask db upgrade
```
#### If you add new fields to models (e.g., 'archived' to Student):
If you add a new field and are **not** using Flask-Migrate, run this SQL in your MySQL client:
```sql
ALTER TABLE students ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0;
```

---

### 7. How to Start the App (Anytime)
If you close everything and want to start again:
1. Open your terminal and go to your project folder:
   ```bash
   cd student_result_portal
   ```
2. Activate your virtual environment:
   - Windows CMD: `venv\Scripts\activate`
   - PowerShell: `.\venv\Scripts\Activate.ps1`
   - macOS/Linux: `source venv/bin/activate`
3. Set the Flask app environment variable (see Step 5).
4. Start the server:
   ```bash
   python run.py
   # or
   python -m flask run
   ```
5. Visit [http://127.0.0.1:5000/](http://127.0.0.1:5000/) in your browser.

---

### 8. Create an Admin Account
To create an admin account, you'll need to run a Python script in the Flask shell. Follow these steps:

1. Make sure your virtual environment is activated and all dependencies are installed.
2. Set the Flask app environment variable if you haven't already:
   ```bash
   # On Windows CMD:
   set FLASK_APP=app:create_app
   
   # On PowerShell:
   $env:FLASK_APP = "app:create_app"
   
   # On macOS/Linux:
   export FLASK_APP=app:create_app
   ```
3. Open the Flask shell by running:
   ```bash
   python -m flask shell
   ```
4. In the Flask shell, copy and paste the following code (make sure to replace `your_secure_password` with a strong password):
   ```python
   from app import create_app, db
   from app.models import User
   from werkzeug.security import generate_password_hash

   app = create_app()
   with app.app_context():
       admin = User(
           username='admin',
           email='admin@example.com',
           password_hash=generate_password_hash('your_secure_password', method='pbkdf2:sha256'),
           user_type='admin'
       )
       db.session.add(admin)
       db.session.commit()
       print("Admin account created successfully!")
   ```
5. Type `exit()` to exit the Flask shell.

You can now log in to the admin dashboard using the credentials you just created.

### 9. Accessing Routes
- Home: `/`
- Auth: `/auth/login`, `/auth/register`
- Admin: `/admin/dashboard`
- Student: `/student/dashboard`

---

### Troubleshooting
- If you get `flask is not recognized`, activate your virtual environment and use `python -m flask ...`.
- If you get `ModuleNotFoundError`, install the missing package with `pip install <package-name>` inside your virtual environment.
- If you get import errors related to blueprints or your app, double-check the `FLASK_APP` setting and your `__init__.py` files.

---

## Features

- Secure user authentication (login/logout)
- Role-based access control (Admin/Student)
- Student profile management
- Course and program management
- Result upload and management
- Student dashboard with GPA calculations
- Admin dashboard with student management
- Secure file uploads for results
- Audit logging for admin actions
- Professional UI/UX with:
  - Modern gradient backgrounds
  - Animated floating shapes
  - Consistent iconography
  - Responsive design
  - Clean, centered layouts
  - Subtle footer on main pages
  - Modern card designs with shadows
  - Bootstrap 5 with custom styling
  - Smooth animations and transitions for all major pages

### Modern Admin Result Entry Workflow
- **Step-by-step Filtering:** Admins now enter results using a multi-step process:
  1. **Select Program**: Choose the student's program of study.
  2. **Select Level**: Choose the academic level (100, 200, 300, 400).
  3. **Select Student**: Only students in the chosen program and level are shown.
  4. **Select Course**: Courses are shown after a student is selected.
  5. **Enter Result Details**: Fill in score, semester, academic year, and remarks.
- **Modern Professional UI:** The form is responsive, visually clear, and disables fields until prerequisites are selected, preventing errors and confusion.
- **Scalable for Large Institutions:** The filtering workflow ensures admins can efficiently locate the right student and course, even in large datasets.

#### Usage Example (Admin Result Entry)
1. Go to the **Enter Result** page in the admin dashboard.
2. Select a Program. The Level dropdown is enabled.
3. Select a Level. The Student dropdown is enabled and only shows students in that program & level.
4. Select a Student. The Course dropdown is enabled.
5. Enter the result details and submit.

If no students or courses are available for the selected filters, the system will notify you.

## .env.example

A `.env.example` file is included for sharing the required environment variable structure. Copy it to `.env` and fill in your secrets.

## Forms and Templates

This project uses WTForms for form handling and includes templates for authentication, admin, and student modules. See the `forms.py` and `templates/` directories for examples and extend as needed.

---

For any issues, please check your environment variables, database connection, and installed dependencies.

For help with authentication, admin dashboard, or other features, open an issue or contact the maintainer.
