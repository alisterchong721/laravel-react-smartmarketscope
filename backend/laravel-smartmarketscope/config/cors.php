<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Cross-Origin Resource Sharing (CORS) Configuration
    |--------------------------------------------------------------------------
    |
    | This configuration allows your React frontend to access your Laravel API.
    |
    */

    'paths' => ['api/*'],

    'allowed_methods' => ['*'],

    'allowed_origins' => (function () {
        $originSources = [
            env('CORS_ALLOWED_ORIGINS'),
            env('FRONTEND_URL'),
            env('APP_URL'),
            'https://smartmarketscope.xyz',
            'https://www.smartmarketscope.xyz',
        ];

        $origins = [];

        foreach ($originSources as $originSource) {
            foreach (explode(',', (string) $originSource) as $origin) {
                $origin = trim($origin);

                if ($origin !== '') {
                    $origins[] = $origin;
                }
            }
        }

        return array_values(array_unique($origins));
    })(),

    'allowed_origins_patterns' => [],

    'allowed_headers' => ['*'],

    'exposed_headers' => [],

    'max_age' => 0,

    'supports_credentials' => false,

];
