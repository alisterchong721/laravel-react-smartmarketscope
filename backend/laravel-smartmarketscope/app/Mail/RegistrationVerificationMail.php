<?php

namespace App\Mail;

use Illuminate\Bus\Queueable;
use Illuminate\Mail\Mailable;
use Illuminate\Queue\SerializesModels;

class RegistrationVerificationMail extends Mailable
{
    use Queueable, SerializesModels;

    public string $code;

    public function __construct(string $code)
    {
        $this->code = $code;
    }

    public function build()
    {
        return $this->subject('Verify Your Smart Market Scope Account')
            ->view('emails.registration-verification')
            ->with([
                'code' => $this->code,
                'expiresInMinutes' => 10,
            ]);
    }
}
