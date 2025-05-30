import pymysql
from config import Config

def apply_migration():
    # Read the SQL file
    with open('updates/0004_add_first_login_column.sql', 'r') as f:
        sql_script = f.read()
    
    # Parse the database URL
    db_url = Config.SQLALCHEMY_DATABASE_URI
    # Extract connection details (this is a simple parser, adjust as needed)
    # Format: mysql+pymysql://username:password@host/database
    parts = db_url.replace('mysql+pymysql://', '').split('@')
    user_pass, host_db = parts[0].split(':'), parts[1].split('/')
    username = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ''
    host = host_db[0]
    database = host_db[1].split('?')[0]  # Remove any query parameters
    
    # Connect to the database
    connection = pymysql.connect(
        host=host,
        user=username,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with connection.cursor() as cursor:
            # Split the SQL script into individual statements
            statements = sql_script.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement:  # Skip empty statements
                    print(f"Executing: {statement}")
                    cursor.execute(statement)
            
            # Commit changes
            connection.commit()
            print("Database updated successfully!")
            
    except Exception as e:
        print(f"Error: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    apply_migration()
