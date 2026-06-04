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
        $fromAddress = config('mail.from.address') ?: 'no-reply@smartmarketscope.xyz';
        $fromName = config('mail.from.name') ?: config('app.name', 'Smart Market Scope');

        return $this->from($fromAddress, $fromName)
            ->subject('Verify Your Smart Market Scope Account')
            ->view('emails.registration-verification')
            ->with([
                'code' => $this->code,
                'expiresInMinutes' => 10,
            ]);
    }
}
