<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\Hash;
use Carbon\Carbon;
use App\Models\User;

class PasswordReset extends Model
{
    public $timestamps = false;
    public $incrementing = false;
    protected $keyType = 'string';
    protected $primaryKey = 'email';
    protected $table = 'password_reset_tokens';

    protected $fillable = [
        'email',
        'token',
        'created_at',
        'expires_at'
    ];

    protected $casts = [
        'created_at' => 'datetime',
        'expires_at' => 'datetime'
    ];

    /**
     * Create a password reset code for email.
     */
    public static function createCode($email, $code)
    {
        self::deleteByEmail($email);
        self::cleanupExpiredTokens();

        return self::create([
            'email' => $email,
            'token' => Hash::make($code),
            'created_at' => Carbon::now(),
            'expires_at' => Carbon::now()->addMinutes(10)
        ]);
    }

    public static function createToken($email)
    {
        $code = (string) random_int(100000, 999999);

        return self::createCode($email, $code);
    }

    /**
     * Find a valid reset record by email.
     */
    public static function findValidByEmail($email)
    {
        return self::where('email', $email)->valid()->first();
    }

    /**
     * Validate if code is valid.
     */
    public static function validateCode($email, $code)
    {
        $record = self::findValidByEmail($email);

        return $record && Hash::check($code, $record->token);
    }

    public static function validateToken($email, $token)
    {
        return self::validateCode($email, $token);
    }

    /**
     * Reset password using code.
     */
    public static function resetPassword($email, $code, $newPassword)
    {
        if (!self::validateCode($email, $code)) {
            return false;
        }

        $user = User::findByEmail($email);
        if (!$user) {
            self::deleteByEmail($email);

            return false;
        }

        $user->updatePassword($newPassword);
        self::deleteByEmail($email);

        return true;
    }

    /**
     * Delete tokens by email
     */
    public static function deleteByEmail($email)
    {
        return self::where('email', $email)->delete();
    }

    /**
     * Clean up expired tokens
     */
    public static function cleanupExpiredTokens()
    {
        return self::where('expires_at', '<', Carbon::now())->delete();
    }

    /**
     * Check if token is expired (instance method)
     */
    public function isExpired(): bool
    {
        return $this->expires_at && $this->expires_at->isPast();
    }

    /**
     * Scope to get valid (non-expired) tokens
     */
    public function scopeValid($query)
    {
        return $query->where(function ($q) {
            $q->where('expires_at', '>', Carbon::now())
              ->orWhereNull('expires_at');
        });
    }

    /**
     * Get token age in minutes
     */
    public function ageInMinutes()
    {
        return $this->created_at ? Carbon::now()->diffInMinutes($this->created_at) : null;
    }

    /**
     * Get minutes until expiration
     */
    public function expiresInMinutes()
    {
        if (!$this->expires_at) {
            return null;
        }
        
        $minutes = Carbon::now()->diffInMinutes($this->expires_at, false);
        return $minutes > 0 ? $minutes : 0;
    }
}
