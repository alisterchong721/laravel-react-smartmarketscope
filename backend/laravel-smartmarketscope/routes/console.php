<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Schedule;
use App\Http\Service\NewsSentimentService;
use App\Http\Service\FundamentalScrapeService;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Artisan::command('news-sentiment:sync {--refresh}', function (NewsSentimentService $newsSentimentService) {
    $result = $newsSentimentService->syncLatestData((bool) $this->option('refresh'));

    $this->info(json_encode($result, JSON_PRETTY_PRINT));
})->purpose('Fetch, store, and queue analysis for the latest market news sentiment');

Schedule::command('news-sentiment:sync')->everyFifteenMinutes();

Schedule::command('queue:work --stop-when-empty --tries=3')
    ->everyMinute()
    ->withoutOverlapping()
    ->appendOutputTo('/tmp/smartmarketscope-queue.log');

Artisan::command('fundamental:sync-calendar {--periods=} {--impacts=}', function (FundamentalScrapeService $fundamentalScrapeService) {
    $periods = $this->option('periods')
        ? array_filter(array_map('trim', explode(',', $this->option('periods'))))
        : null;
    $impacts = $this->option('impacts')
        ? array_filter(array_map('trim', explode(',', $this->option('impacts'))))
        : null;

    $result = $fundamentalScrapeService->syncForexFactoryCalendar($periods, $impacts);

    $this->info(json_encode($result, JSON_PRETTY_PRINT));
})->purpose('Fetch and store high-impact economic calendar events from Forex Factory');

Schedule::command('fundamental:sync-calendar')
    ->everyFifteenMinutes()
    ->appendOutputTo('/tmp/smartmarketscope-fundamental-sync.log');

Artisan::command('fundamental:sync-actuals {--countries=} {--start-date=} {--end-date=}', function (FundamentalScrapeService $fundamentalScrapeService) {
    $countries = $this->option('countries')
        ? array_filter(array_map('trim', explode(',', $this->option('countries'))))
        : null;
    $startDate = $this->option('start-date') ? \Carbon\Carbon::parse($this->option('start-date')) : null;
    $endDate = $this->option('end-date') ? \Carbon\Carbon::parse($this->option('end-date')) : null;

    $result = $fundamentalScrapeService->syncCalendarActuals($countries, $startDate, $endDate);

    $this->info(json_encode($result, JSON_PRETTY_PRINT));
})->purpose('Fill missing actual values on Forex Factory calendar rows from a configured actual-value provider');

Schedule::command('fundamental:sync-actuals')
    ->everyFifteenMinutes()
    ->appendOutputTo('/tmp/smartmarketscope-fundamental-actuals.log');

Artisan::command('fundamental:import-calendar-csv {file}', function (FundamentalScrapeService $fundamentalScrapeService, string $file) {
    $result = $fundamentalScrapeService->importForexFactoryCsv($file);

    $this->info(json_encode($result, JSON_PRETTY_PRINT));
})->purpose('Import historical Forex Factory calendar rows from a CSV export');
