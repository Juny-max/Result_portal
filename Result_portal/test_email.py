import os
from dotenv import load_dotenv
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv()

def test_email_config():
    print("Testing Email Configuration...")
    print("=" * 50)
    
    # Get email settings
    mail_server = os.getenv('MAIL_SERVER')
    mail_port = int(os.getenv('MAIL_PORT', 465))
    mail_username = os.getenv('MAIL_USERNAME')
    mail_password = os.getenv('MAIL_PASSWORD').strip('"\'')
    
    print(f"Mail Server: {mail_server}")
    print(f"Port: {mail_port}")
    print(f"Username: {mail_username}")
    print(f"Password: {'*' * len(mail_password) if mail_password else 'Not set'}")
    
    # Test SMTP connection
    print("\nTesting SMTP Connection...")
    try:
        context = ssl.create_default_context()
        
        # Connect to the server
        with smtplib.SMTP_SSL(mail_server, mail_port, context=context, timeout=20) as server:
            print(f"Connected to {mail_server}:{mail_port}")
            
            # Try to log in
            print("Attempting to login...")
            server.login(mail_username, mail_password)
            print("SUCCESS: Login successful!")
            
            # Test sending an email
            print("\nSending test email...")
            msg = MIMEMultipart()
            msg['From'] = mail_username
            msg['To'] = mail_username  # Send to self for testing
            msg['Subject'] = 'Test Email from Student Portal'
            
            body = """
            This is a test email from the Student Portal.
            
            If you're reading this, the email configuration is working correctly!
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server.send_message(msg)
            print("SUCCESS: Test email sent successfully!")
            
    except Exception as e:
        print("\nERROR:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        
        # Provide specific guidance for common errors
        if "Authentication failed" in str(e):
            print("\nAuthentication failed. Please check:")
            print("1. Your email password is correct")
            print("2. You're using an App Password if 2FA is enabled")
            print("3. The password doesn't contain any extra spaces or characters")
        elif "Connection refused" in str(e):
            print("\nConnection was refused. Please check:")
            print("1. The mail server address is correct")
            print("2. The port number is correct (465 for SSL, 587 for TLS)")
            print("3. Your firewall allows outbound connections on this port")
        elif "timed out" in str(e).lower():
            print("\nConnection timed out. Please check:")
            print("1. Your internet connection")
            print("2. The mail server is accessible from your network")
            print("3. No firewall is blocking the connection")

if __name__ == "__main__":
    test_email_config()
