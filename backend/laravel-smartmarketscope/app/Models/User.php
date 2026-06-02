<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Laravel\Sanctum\HasApiTokens;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Str;
use Carbon\Carbon;

class User extends Authenticatable
{
    use HasFactory, HasApiTokens;

    protected $fillable = [
        'email',
        'password',
        'email_verified_at',
    ];

    protected $hidden = [
        'password',
        'remember_token'
    ];

    protected $casts = [
        'email_verified_at' => 'datetime',
        'password' => 'hashed'
    ];

     public function tradeRecords()
    {
        return $this->hasMany(TradeRecord::class, 'user_id');
    }

    /**
     * Find user by email
     */
    public static function findByEmail($email)
    {
        return self::where('email', $email)->first();
    }

    /**
     * Find user by ID
     */
    public static function findById($id)
    {
        return self::find($id);
    }

    /**
     * Check if user exists by email
     */
    public static function existsByEmail($email)
    {
        return self::where('email', $email)->exists();
    }

    /**
     * Create a new user
     */
    public static function createUser($email, $password, $emailVerifiedAt = null)
    {
        return self::create([
            'email' => $email,
            'password' => $password,
            'email_verified_at' => $emailVerifiedAt
        ]);
    }

    /**
     * Update user password
     */
    public function updatePassword($newPassword)
    {
        $this->password = $newPassword;
        return $this->save();
    }

    /**
     * Revoke all tokens (logout from all devices)
     */
    public function revokeAllTokens()
    {
        return $this->tokens()->delete();
    }

    /**
     * Revoke specific token by ID
     */
    public function revokeToken($tokenId)
    {
        return $this->tokens()->where('id', $tokenId)->delete();
    }

    /**
     * Get active tokens count
     */
    public function activeTokensCount()
    {
        return $this->tokens()->count();
    }

    /**
     * Create password reset token for this user
     */
    public function createPasswordResetToken()
    {
        // Delete any existing tokens first
        PasswordReset::deleteByEmail($this->email);

        // Create new token via PasswordReset model
        return PasswordReset::createToken($this->email);
    }

    /**
     * Validate password reset token for this user
     */
    public function validatePasswordResetToken($token)
    {
        return PasswordReset::validateToken($this->email, $token);
    }

    /**
     * Reset password using token
     */
    public function resetPasswordWithToken($token, $newPassword)
    {
        return PasswordReset::resetPassword($this->email, $token, $newPassword);
    }
}
