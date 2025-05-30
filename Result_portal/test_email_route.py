from app import create_app, db
from app.models import User, Student
from flask import render_template_string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def test_email():
    app = create_app()
    with app.app_context():
        try:
            # Get email settings
            mail_server = app.config['MAIL_SERVER']
            mail_port = app.config['MAIL_PORT']
            mail_username = app.config['MAIL_USERNAME']
            mail_password = app.config['MAIL_PASSWORD'].strip('"\'')
            
            # Create a test message
            recipient = 'junyappteam@gmail.com'  # Change this to your test email
            subject = 'Test Email from Student Portal'
            
            # Create message container
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = mail_username
            msg['To'] = recipient
            
            # Create the body of the message (a plain-text and an HTML version)
            text = """\
            Hi,
            This is a test email from the Student Portal.
            """
            
            html = """\
            <html>
              <body>
                <p>Hi,<br>
                   This is a <b>test email</b> from the <a href="#">Student Portal</a>.
                </p>
              </body>
            </html>
            """
            
            # Record the MIME types of both parts - text/plain and text/html
            part1 = MIMEText(text, 'plain')
            part2 = MIMEText(html, 'html')
            
            # Attach parts into message container
            msg.attach(part1)
            msg.attach(part2)
            
            # Send the email
            with smtplib.SMTP_SSL(mail_server, mail_port, timeout=20) as server:
                server.login(mail_username, mail_password)
                server.send_message(msg)
                
            return "Test email sent successfully!"
            
        except Exception as e:
            return f"Error sending test email: {str(e)}"

if __name__ == "__main__":
    result = test_email()
    print(result)
