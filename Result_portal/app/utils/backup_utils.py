import os
import zipfile
import shutil
from datetime import datetime
from flask import current_app
import subprocess
import tempfile
import mysql.connector
from mysql.connector import Error
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_backup_dir():
    """Get or create backup directory"""
    backup_dir = os.path.join(current_app.root_path, '..', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir

def create_backup():
    """Create a backup of the database and important files"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = get_backup_dir()
    backup_name = f"backup_{timestamp}"
    backup_path = os.path.join(backup_dir, backup_name)
    
    try:
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Backup database
            db_config = current_app.config['SQLALCHEMY_DATABASE_URI']
            db_name = db_config.split('/')[-1].split('?')[0]
            db_user = db_config.split('//')[1].split(':')[0]
            db_pass = db_config.split(':')[2].split('@')[0]
            
            db_dump = os.path.join(temp_dir, 'database.sql')
            
            # Using mysql.connector to create database backup
            try:
                # Parse database connection details
                host = 'localhost'
                port = 3306  # Default MySQL port
                
                # Connect to MySQL server
                connection = mysql.connector.connect(
                    host=host,
                    port=port,
                    user=db_user,
                    password=db_pass,
                    database=db_name
                )
                
                # Get all tables in the database
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SHOW TABLES")
                tables = [table[f'Tables_in_{db_name}'] for table in cursor.fetchall()]
                
                # Write SQL dump to file
                with open(db_dump, 'w', encoding='utf-8') as f:
                    # Write header
                    f.write(f'-- MySQL dump 10.13  Distrib 9.1.0, for Win64 (x86_64)\n')
                    f.write(f'-- Host: {host}    Database: {db_name}\n')
                    f.write('-- ------------------------------------------------------\n\n')
                    f.write('/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n')
                    f.write('/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;\n')
                    f.write('/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;\n')
                    f.write('/*!40101 SET NAMES utf8mb4 */;\n\n')
                    
                    # Dump each table
                    for table in tables:
                        try:
                            # Get table structure
                            cursor.execute(f'SHOW CREATE TABLE `{table}`')
                            create_table = cursor.fetchone()
                            if create_table:
                                f.write(f'\n--\n-- Table structure for table `{table}`\n--\n\n')
                                f.write(f'{create_table["Create Table"]};\n\n')
                            
                            # Get table data
                            cursor.execute(f'SELECT * FROM `{table}`')
                            rows = cursor.fetchall()
                            
                            if rows:
                                f.write(f'--\n-- Dumping data for table `{table}`\n--\n\n')
                                
                                # Get column names
                                columns = list(rows[0].keys())
                                
                                # Write INSERT statements
                                for row in rows:
                                    values = []
                                    for col in columns:
                                        val = row[col]
                                        if val is None:
                                            values.append('NULL')
                                        elif isinstance(val, (int, float)):
                                            values.append(str(val))
                                        else:
                                            # Escape special characters and quote strings
                                            val = str(val).replace('\\', '\\\\').replace('\'', '\\\'')
                                            values.append(f"'{val}'")
                                    
                                    f.write(f'INSERT INTO `{table}` (`{", ".join(columns)}`) VALUES ({", ".join(values)});\n')
                                
                                f.write('\n')
                                
                        except Error as e:
                            logger.error(f'Error dumping table {table}: {str(e)}')
                            continue
                    
                    # Write footer
                    f.write('\n-- Dump completed on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\n')
                    f.write('/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;\n')
                    f.write('/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;\n')
                    f.write('/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;\n')
                
                # Verify the dump file was created
                if not os.path.exists(db_dump) or os.path.getsize(db_dump) == 0:
                    raise Exception('Database dump file was not created or is empty')
                
            except Error as e:
                error_msg = f'MySQL connection failed: {str(e)}'
                logger.error(error_msg)
                raise Exception(f'Database backup failed: {error_msg}')
            finally:
                if 'connection' in locals() and connection.is_connected():
                    cursor.close()
                    connection.close()
            
            # Create zip file
            backup_zip = f"{backup_path}.zip"
            with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(db_dump, 'database.sql')
                
                # Add important directories
                for root, dirs, files in os.walk('app/static'):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, 'app')
                        zipf.write(file_path, arcname)
                
                # Add .env file if exists
                if os.path.exists('.env'):
                    zipf.write('.env', '.env')
            
            return {
                'success': True,
                'filename': f"{backup_name}.zip",
                'path': backup_zip,
                'size': os.path.getsize(backup_zip),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def get_backup_files():
    """Get list of all backup files"""
    backup_dir = get_backup_dir()
    backups = []
    
    for file in os.listdir(backup_dir):
        if file.endswith('.zip'):
            file_path = os.path.join(backup_dir, file)
            backups.append({
                'name': file,
                'path': file_path,
                'size': os.path.getsize(file_path),
                'created_at': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    
    # Sort by creation time (newest first)
    return sorted(backups, key=lambda x: x['created_at'], reverse=True)

def restore_backup(backup_path):
    """Restore from a backup file"""
    try:
        # Extract backup to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(backup_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Restore database
            db_config = current_app.config['SQLALCHEMY_DATABASE_URI']
            db_name = db_config.split('/')[-1].split('?')[0]
            db_user = db_config.split('//')[1].split(':')[0]
            db_pass = db_config.split(':')[2].split('@')[0]
            
            db_dump = os.path.join(temp_dir, 'database.sql')
            
            # Using mysql to restore database
            cmd = [
                'mysql',
                f'--user={db_user}',
                f'--password={db_pass}',
                '--host=localhost',
                db_name
            ]
            
            with open(db_dump, 'r') as f:
                subprocess.run(cmd, stdin=f, check=True)
            
            # Restore static files if they exist
            static_backup = os.path.join(temp_dir, 'static')
            if os.path.exists(static_backup):
                static_dir = os.path.join('app', 'static')
                if os.path.exists(static_dir):
                    shutil.rmtree(static_dir)
                shutil.copytree(static_backup, static_dir)
            
            # Restore .env file if it exists
            env_backup = os.path.join(temp_dir, '.env')
            if os.path.exists(env_backup):
                shutil.copy2(env_backup, '.env')
            
            return {
                'success': True,
                'message': 'Restore completed successfully'
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
