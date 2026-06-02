<?php
// php artisan route:clear 
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

// Controller
use App\Http\Controllers\AuthController;
use App\Http\Controllers\FundamentalDataController;
use App\Http\Controllers\PasswordResetController;
use App\Http\Controllers\FundamentalScrapeController;
use App\Http\Controllers\TradeRecordsController;
use App\Http\Controllers\RetailSentimentController;
use App\Http\Controllers\CotReportController;
use App\Http\Controllers\NewsSentimentController;
use App\Http\Controllers\OverviewDashboardController;
use App\Http\Controllers\ChatbotController;
use App\Http\Controllers\SeasonalityAnalysisController;


// Public Routes
Route::post('/register', [AuthController::class, 'register']);
Route::post('/register/resend', [AuthController::class, 'resendRegistrationCode']);
Route::post('/register/verify', [AuthController::class, 'verifyRegistration']);
Route::post('/login', [AuthController::class, 'login']);



// Protected routes with valid token
Route::middleware('auth:sanctum')->group(function () {
    Route::post('/logout', [AuthController::class, 'logout']);
    Route::post('/logout-all', [AuthController::class, 'logoutAll']);
    Route::post('/session/keep-alive', [AuthController::class, 'keepAlive']);
    Route::get('/me', [AuthController::class, 'me']);
    Route::post('/chatbot/message', [ChatbotController::class, 'message']);
});

Route::prefix('password')->group(function () {
    Route::post('/forgot', [PasswordResetController::class, 'forgotPassword']);
    Route::post('/reset', [PasswordResetController::class, 'resetPassword']);
    Route::post('/validate-token', [PasswordResetController::class, 'validateToken']);
});

// get fundamental data
Route::prefix('fundamental')->group(function () {
    Route::get('/view', [FundamentalScrapeController::class, 'viewData']);
    Route::post('/store', [FundamentalScrapeController::class, 'storeData']);
    Route::post('/sync-calendar', [FundamentalScrapeController::class, 'syncCalendar']);
    Route::get('/calendar', [FundamentalScrapeController::class, 'calendar']);

    // Get one row 
    Route::get('/view-country-data', [FundamentalDataController::class, 'getCountryLatestEvent']);
    Route::get('/view-event-country-data', [FundamentalDataController::class, 'getEventCountryLatestData']);
    Route::get('/pair/{pair}', [FundamentalDataController::class, 'calculatePairImpact']);
});

Route::prefix('tradeRecords')->group(function () {
    Route::post('/create', [TradeRecordsController::class, 'createTrade']);

    // PUT /api/trades/update
    Route::post('/update', [TradeRecordsController::class, 'updateTrade']);

    // DELETE /api/trades/delete
    Route::post('/delete', [TradeRecordsController::class, 'deleteTrade']);

    // GET /api/trades/get
    Route::get('/get', [TradeRecordsController::class, 'findTrade']);

    // GET /api/trades/get-by-user
    Route::get('/get-by-user', [TradeRecordsController::class, 'findTradeByUser']);

    // GET /api/trades/all
    Route::get('/all', [TradeRecordsController::class, 'getAllTrades']);
});

Route::prefix('retail-sentiment')->group(function () {
    Route::get('/', [RetailSentimentController::class, 'index']);
    Route::get('/filters', [RetailSentimentController::class, 'filters']);
});

Route::prefix('cot-sentiment')->group(function () {
    Route::get('/', [CotReportController::class, 'index']);
    Route::get('/filters', [CotReportController::class, 'filters']);
});

Route::prefix('news-sentiment')->group(function () {
    Route::get('/', [NewsSentimentController::class, 'index']);
    Route::get('/filters', [NewsSentimentController::class, 'filters']);
    Route::get('/source-news', [NewsSentimentController::class, 'sourceNews']);
    Route::get('/fetched-news', [NewsSentimentController::class, 'fetchedNews']);
    Route::post('/sync', [NewsSentimentController::class, 'sync']);
});

Route::prefix('overview-dashboard')->group(function () {
    Route::get('/', [OverviewDashboardController::class, 'index']);
    Route::get('/filters', [OverviewDashboardController::class, 'filters']);
});

Route::prefix('seasonality')->group(function () {
    Route::get('/', [SeasonalityAnalysisController::class, 'index']);
});
