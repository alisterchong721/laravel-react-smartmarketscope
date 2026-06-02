<!-- resources/views/emails/password-reset.blade.php -->
<!DOCTYPE html>
<html>
<head>
    <title>Password Reset</title>
</head>
<body>
    <h2>Password Reset Request</h2>
    <p>Use the verification code below to reset your password.</p>

    <p style="font-size: 28px; font-weight: bold; letter-spacing: 4px;">{{ $code }}</p>

    <p>This code will expire in {{ $expiresInMinutes }} minutes.</p>
    <p>If you didn't request this, please ignore this email.</p>
</body>
</html>
