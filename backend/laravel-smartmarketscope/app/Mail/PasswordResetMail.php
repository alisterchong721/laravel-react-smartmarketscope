<?php
// app/Mail/PasswordResetMail.php

namespace App\Mail;

use Illuminate\Bus\Queueable;
use Illuminate\Mail\Mailable;
use Illuminate\Queue\SerializesModels;

class PasswordResetMail extends Mailable
{
    use Queueable, SerializesModels;

    public $code;
    public $email;

    public function __construct($code, $email)
    {
        $this->code = $code;
        $this->email = $email;
    }

    public function build()
    {
        return $this->subject('Reset Your Password')
                    ->view('emails.password-reset')
                    ->with([
                        'code' => $this->code,
                        'expiresInMinutes' => 10
                    ]);
    }
}
