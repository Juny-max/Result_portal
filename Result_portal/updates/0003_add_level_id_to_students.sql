-- Add level_id column to students table
ALTER TABLE students ADD COLUMN level_id INT AFTER program_id;

-- Add foreign key constraint
ALTER TABLE students ADD CONSTRAINT fk_students_level_id FOREIGN KEY (level_id) REFERENCES levels(id);

-- Update existing students with level_id based on their current level
UPDATE students s
JOIN levels l ON s.level = l.name
SET s.level_id = l.id;

-- Drop the old level column
ALTER TABLE students DROP COLUMN level;
