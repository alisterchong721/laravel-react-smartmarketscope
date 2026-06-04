<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class Cors
{
    public function handle(Request $request, Closure $next)
    {
        $response = $next($request);
        $configuredOrigins = config('cors.allowed_origins', []);
        $allowedOrigins = is_array($configuredOrigins)
            ? $configuredOrigins
            : explode(',', $configuredOrigins);
        $allowedOrigins = array_values(array_filter(array_map('trim', $allowedOrigins)));
        $origin = $request->headers->get('Origin');

        if ($origin && in_array($origin, $allowedOrigins, true)) {
            $response->headers->set('Access-Control-Allow-Origin', $origin);
        }

        $response->headers->set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
        $response->headers->set('Access-Control-Allow-Headers', 'Content-Type, Authorization');

        return $response;
    }
}
