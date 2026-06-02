<?php

use App\Http\Controllers\SiteCheckController;
use Illuminate\Support\Facades\Route;

Route::get('/', fn () => response()->json([
    'success' => true,
    'message' => 'SmartMarketScope API is running',
]));

// The {encodedUrl} parameter will match everything after /check-site/
Route::get('/check-site/{url}', [SiteCheckController::class, 'check'])
     ->where('url', '.*');
