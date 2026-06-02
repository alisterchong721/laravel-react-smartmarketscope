<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Sanctum\PersonalAccessToken;
use Tests\TestCase;

class IdleSessionTest extends TestCase
{
    use RefreshDatabase;

    public function test_login_token_gets_idle_expiry_deadline(): void
    {
        $user = User::factory()->create([
            'password' => 'password123',
        ]);

        $response = $this->postJson('/api/login', [
            'email' => $user->email,
            'password' => 'password123',
        ]);

        $response->assertOk();

        $token = PersonalAccessToken::query()->first();

        $this->assertNotNull($token);
        $this->assertTrue($token->expires_at->between(
            now()->addMinutes(34),
            now()->addMinutes(36)
        ));
    }

    public function test_keep_alive_extends_current_token_deadline(): void
    {
        $user = User::factory()->create();
        $plainToken = $user->createToken('auth_token', ['*'], now()->addMinute())->plainTextToken;

        $response = $this->withHeader('Authorization', "Bearer {$plainToken}")
            ->postJson('/api/session/keep-alive');

        $response->assertOk()
            ->assertJsonPath('data.warn_after_minutes', 30)
            ->assertJsonPath('data.grace_minutes', 5);

        $token = PersonalAccessToken::query()->first();

        $this->assertTrue($token->fresh()->expires_at->between(
            now()->addMinutes(34),
            now()->addMinutes(36)
        ));
    }

    public function test_logout_deletes_token_instead_of_extending_it(): void
    {
        $user = User::factory()->create();
        $plainToken = $user->createToken('auth_token', ['*'], now()->addMinutes(35))->plainTextToken;

        $response = $this->withHeader('Authorization', "Bearer {$plainToken}")
            ->postJson('/api/logout');

        $response->assertOk();

        $this->assertDatabaseCount('personal_access_tokens', 0);
    }
}
