-- Create levels table
CREATE TABLE IF NOT EXISTS levels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(20) NOT NULL UNIQUE,
    description VARCHAR(100),
    archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default levels
INSERT INTO levels (name, description) VALUES
('100', 'First Year'),
('200', 'Second Year'),
('300', 'Third Year'),
('400', 'Fourth Year');
