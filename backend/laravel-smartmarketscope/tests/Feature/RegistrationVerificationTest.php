<?php

namespace Tests\Feature;

use App\Mail\RegistrationVerificationMail;
use App\Models\PendingUserRegistration;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Mail;
use Tests\TestCase;

class RegistrationVerificationTest extends TestCase
{
    use RefreshDatabase;

    public function test_register_sends_verification_code_without_creating_user(): void
    {
        Mail::fake();

        $response = $this->postJson('/api/register', [
            'email' => 'newtrader@example.com',
            'password' => 'password123',
            'password_confirmation' => 'password123',
        ]);

        $response->assertAccepted()
            ->assertJsonPath('message', 'Verification code sent to your email')
            ->assertJsonPath('data.email', 'newtrader@example.com');

        $this->assertDatabaseMissing('users', [
            'email' => 'newtrader@example.com',
        ]);

        $this->assertDatabaseHas('pending_user_registrations', [
            'email' => 'newtrader@example.com',
        ]);

        Mail::assertSent(RegistrationVerificationMail::class);
    }

    public function test_verify_registration_creates_user_and_returns_token(): void
    {
        Mail::fake();
        $verificationCode = null;

        $this->postJson('/api/register', [
            'email' => 'verified@example.com',
            'password' => 'password123',
            'password_confirmation' => 'password123',
        ])->assertAccepted();

        Mail::assertSent(RegistrationVerificationMail::class, function ($mail) use (&$verificationCode) {
            $verificationCode = $mail->code;

            return true;
        });

        $response = $this->postJson('/api/register/verify', [
            'email' => 'verified@example.com',
            'code' => $verificationCode,
        ]);

        $response->assertCreated()
            ->assertJsonPath('message', 'User registered successfully')
            ->assertJsonPath('data.user.email', 'verified@example.com')
            ->assertJsonStructure([
                'data' => [
                    'token',
                    'token_type',
                ],
            ]);

        $user = User::where('email', 'verified@example.com')->first();

        $this->assertNotNull($user);
        $this->assertNotNull($user->email_verified_at);
        $this->assertSame(0, PendingUserRegistration::where('email', 'verified@example.com')->count());
    }

    public function test_resend_registration_code_refreshes_code_after_cooldown(): void
    {
        Mail::fake();

        $this->postJson('/api/register', [
            'email' => 'resend@example.com',
            'password' => 'password123',
            'password_confirmation' => 'password123',
        ])->assertAccepted();

        $this->postJson('/api/register/resend', [
            'email' => 'resend@example.com',
        ])->assertAccepted()
            ->assertJsonPath('message', 'Verification code sent to your email')
            ->assertJsonPath('data.retry_after_seconds', 300);

        $this->postJson('/api/register/resend', [
            'email' => 'resend@example.com',
        ])->assertStatus(429);

        PendingUserRegistration::where('email', 'resend@example.com')->update([
            'updated_at' => now()->subMinutes(5),
        ]);

        $this->postJson('/api/register/resend', [
            'email' => 'resend@example.com',
        ])->assertAccepted()
            ->assertJsonPath('message', 'Verification code sent to your email')
            ->assertJsonPath('data.retry_after_seconds', 300);

        Mail::assertSent(RegistrationVerificationMail::class, 3);

        $sentCodes = Mail::sent(RegistrationVerificationMail::class)
            ->map(fn ($mail) => $mail->code)
            ->values();
        $firstCode = $sentCodes->get(0);
        $resentCode = $sentCodes->get(2);

        $this->assertNotSame($firstCode, $resentCode);
    }
}
