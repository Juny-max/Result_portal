-- Add first_login column to users table
ALTER TABLE users 
ADD COLUMN first_login TINYINT(1) NOT NULL DEFAULT 1
COMMENT 'Flag to indicate if user needs to change password on first login';

-- Update existing users to have first_login = 0
UPDATE users SET first_login = 0;
