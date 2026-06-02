<?php

namespace Tests\Feature;

use App\Mail\PasswordResetMail;
use App\Models\PasswordReset;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Mail;
use Tests\TestCase;

class PasswordResetCodeTest extends TestCase
{
    use RefreshDatabase;

    public function test_forgot_password_rejects_unregistered_email(): void
    {
        Mail::fake();

        $this->postJson('/api/password/forgot', [
            'email' => 'missing@example.com',
        ])->assertNotFound()
            ->assertJsonPath('message', 'Email is not registered');

        Mail::assertNothingSent();
    }

    public function test_forgot_password_sends_code_for_registered_email(): void
    {
        Mail::fake();
        User::factory()->create(['email' => 'trader@example.com']);

        $this->postJson('/api/password/forgot', [
            'email' => 'trader@example.com',
        ])->assertAccepted()
            ->assertJsonPath('message', 'Password reset code sent to your email')
            ->assertJsonPath('data.email', 'trader@example.com');

        $this->assertDatabaseHas('password_reset_tokens', [
            'email' => 'trader@example.com',
        ]);

        Mail::assertSent(PasswordResetMail::class);
    }

    public function test_validate_code_and_reset_password(): void
    {
        Mail::fake();
        $user = User::factory()->create([
            'email' => 'reset@example.com',
            'password' => Hash::make('old-password'),
        ]);
        $code = null;

        $this->postJson('/api/password/forgot', [
            'email' => 'reset@example.com',
        ])->assertAccepted();

        Mail::assertSent(PasswordResetMail::class, function ($mail) use (&$code) {
            $code = $mail->code;

            return true;
        });

        $this->postJson('/api/password/validate-token', [
            'email' => 'reset@example.com',
            'code' => $code,
        ])->assertOk()
            ->assertJsonPath('message', 'Verification code is valid');

        $this->postJson('/api/password/reset', [
            'email' => 'reset@example.com',
            'code' => $code,
            'password' => 'new-password',
            'password_confirmation' => 'new-password',
        ])->assertOk()
            ->assertJsonPath('message', 'Password reset successfully');

        $this->assertTrue(Hash::check('new-password', $user->refresh()->password));
        $this->assertSame(0, PasswordReset::where('email', 'reset@example.com')->count());
    }
}
