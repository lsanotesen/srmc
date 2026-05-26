SET @admin_password = '$2b$12$EixZaYbB.rK4fl8x2q7Meu6Q6D2V5fF5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q';

UPDATE users SET password = @admin_password WHERE username = 'admin';