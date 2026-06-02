<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Laravel\Sanctum\PersonalAccessToken;
use Symfony\Component\HttpFoundation\Response;

class ExtendIdleSession
{
    public function handle(Request $request, Closure $next): Response
    {
        $response = $next($request);

        $token = $request->user()?->currentAccessToken();

        if ($token instanceof PersonalAccessToken && $token->exists && $response->getStatusCode() < 400) {
            $token->forceFill([
                'expires_at' => now()->addMinutes(config('idle_session.expire_after_minutes')),
            ])->save();
        }

        return $response;
    }
}
