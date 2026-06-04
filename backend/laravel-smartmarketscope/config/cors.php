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
        $origins = env('CORS_ALLOWED_ORIGINS')
            ?: env('FRONTEND_URL')
            ?: env('APP_URL')
            ?: 'https://smartmarketscope.xyz';

        return array_values(array_filter(array_map('trim', explode(',', $origins))));
    })(),

    'allowed_origins_patterns' => [],

    'allowed_headers' => ['*'],

    'exposed_headers' => [],

    'max_age' => 0,

    'supports_credentials' => false,

];
