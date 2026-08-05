SET @admin_password = '$2b$12$KmhZBS0Kfv8fnTic8hWSy.VkXHhxE1J3JNP2HEthl7YSF9JB8lvF2';

UPDATE users SET password = @admin_password WHERE username = 'admin';