<?php

namespace App\Models;

use Carbon\Carbon;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\Hash;

class PendingUserRegistration extends Model
{
    protected $fillable = [
        'email',
        'password',
        'code_hash',
        'resend_count',
        'expires_at',
    ];

    protected $casts = [
        'expires_at' => 'datetime',
    ];

    public static function createFor(string $email, string $password, string $code): self
    {
        self::where('email', $email)->delete();
        self::where('expires_at', '<=', Carbon::now())->delete();

        return self::create([
            'email' => $email,
            'password' => Hash::make($password),
            'code_hash' => Hash::make($code),
            'resend_count' => 0,
            'expires_at' => Carbon::now()->addMinutes(10),
        ]);
    }

    public function isExpired(): bool
    {
        return $this->expires_at->isPast();
    }

    public function codeMatches(string $code): bool
    {
        return Hash::check($code, $this->code_hash);
    }

    public function canResendCode(): bool
    {
        if ($this->resend_count < 1) {
            return true;
        }

        return !$this->updated_at || $this->updated_at->lte(Carbon::now()->subMinutes(5));
    }

    public function secondsUntilResend(): int
    {
        if ($this->canResendCode()) {
            return 0;
        }

        return max(0, Carbon::now()->diffInSeconds($this->updated_at->copy()->addMinutes(5), false));
    }

    public function refreshCode(string $code): bool
    {
        $this->code_hash = Hash::make($code);
        $this->resend_count++;
        $this->expires_at = Carbon::now()->addMinutes(10);

        return $this->save();
    }
}
